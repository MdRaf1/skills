#!/usr/bin/env python3
"""Rebuild the working context of a previous coding-agent session.

Claude Code and Codex already keep every session on disk as a JSONL transcript.
This script finds the previous session for a project and prints a bounded
digest of it: every user prompt, how the session ended, what was changed, and
the final stretch of activity. A fresh session can read that digest and carry
on, which is the point when the old session can no longer be resumed.

    session_digest.py list   [--cwd DIR] [--all]
    session_digest.py digest [--session ID | --file PATH] [--sessions N] [--budget N] [--part N|all]
    session_digest.py show   --event N[-M] [--session ID | --file PATH] [--offset N]
    session_digest.py search REGEX [--session ID | --file PATH]

Standard library only. It reads transcripts and prints; it never writes, deletes or sends anything.
Checked against transcripts written by Claude Code 2.1.322 and Codex CLI 0.167.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import difflib
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

DEFAULT_BUDGET = 66_000
# Agent harnesses cut long tool output short (Claude Code keeps about 30,000 characters), so a
# digest is printed in parts that each fit comfortably.
PART_SIZE = 22_000
END_MARK = "[End of digest]"
SIGNIFICANT = ("assistant", "tool", "error", "abort")
CURRENT_ID_ENV = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID")
# Codex wrappers whose effects are already recorded as CommandExecution/FileChange items.
# A session with fewer agent messages and tool calls than this is treated as a short retry.
THIN_SESSION = 25
ITEM_BACKED = {"exec", "shell", "local_shell", "exec_command", "unified_exec", "write_stdin", "apply_patch"}


@dataclasses.dataclass
class Event:
    i: int
    kind: str  # user | assistant | thinking | tool | error | compaction | note | queued | abort | command | worker
    ts: str | None = None
    text: str = ""
    name: str | None = None
    input: object = None
    result: str | None = None
    ok: bool | None = None
    meta: dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Session:
    tool: str
    id: str | None = None
    cwd: str | None = None
    paths: list = dataclasses.field(default_factory=list)
    events: list = dataclasses.field(default_factory=list)
    started: str | None = None
    ended: str | None = None
    models: list = dataclasses.field(default_factory=list)
    title: str | None = None


@dataclasses.dataclass
class SessionRef:
    tool: str
    id: str
    cwd: str | None
    paths: list
    started: str | None = None
    last_activity: float = 0.0
    label: str | None = None
    parent: str | None = None
    children: list = dataclasses.field(default_factory=list)
    _session: Session | None = None

    def session(self) -> Session:
        if self._session is None:
            self._session = parse_session(self.paths, self.tool, include_sidechain=bool(self.parent))
            self._session.id = self.id  # the id sessions are looked up by
        return self._session

    def prompts(self) -> list:
        return [e for e in self.session().events if e.kind == "user"]

    def work(self) -> int:
        return sum(1 for e in self.session().events if e.kind in ("assistant", "tool"))


@dataclasses.dataclass
class Turn:
    index: int
    prompt: Event | None
    events: list

    @property
    def work(self) -> int:
        return sum(1 for e in self.events if e.kind in ("assistant", "tool"))

    @property
    def outcome(self) -> str:
        significant = [e for e in self.events if e.kind in SIGNIFICANT]
        if not significant:
            return "no_response"
        last = significant[-1]
        if last.kind == "error":
            return "error"
        if last.kind == "abort":
            return "interrupted"
        if last.kind == "tool":
            return "in_flight" if last.result is None else "cut_off"
        return "answered"


# ------------------------------------------------------------------ utilities

def _flatten(content) -> str:
    """Plain text of a message or tool result that may be a string, list or dict."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                kind = block.get("type")
                if isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif kind in ("image", "input_image"):
                    parts.append("[image]")
                elif kind == "encrypted_content":
                    parts.append("[encrypted]")
                elif "content" in block:
                    parts.append(_flatten(block["content"]))
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        for key in ("text", "output", "content", "message"):
            if key in content:
                return _flatten(content[key])
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def _rows(path: Path):
    """Yield parsed JSON objects, skipping lines that are not valid JSON objects."""
    try:
        handle = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def _norm_path(value) -> str:
    return os.path.normcase(os.path.normpath(str(value))) if value else ""


def _same_or_inside(candidate, root) -> bool:
    """True when candidate is root or a directory below it."""
    if not candidate or not root:
        return False
    for a, b in ((candidate, root), (os.path.realpath(str(candidate)), os.path.realpath(str(root)))):
        a, b = _norm_path(a), _norm_path(b)
        if a == b or a.startswith(b.rstrip("/\\") + os.sep):
            return True
    return False


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _head(text: str, limit: int) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: max(limit, 1)] + f" …[+{len(text) - limit} chars]"


def _clip(text: str, limit: int, pointer: str = "") -> str:
    """Keep the start and the end of a long text and say what was left out."""
    text = text or ""
    limit = max(int(limit), 80)
    if len(text) <= limit:
        return text
    keep = max(limit - 70 - len(pointer), 60)
    head, tail = int(keep * 0.7), keep - int(keep * 0.7)
    return f"{text[:head]} …[{len(text) - keep} chars omitted{pointer}]… {text[-tail:]}"


def _quote(text: str, indent: str = "") -> str:
    """Blockquote verbatim text so its own headings and rules cannot be mistaken for the digest's."""
    return "\n".join(f"{indent}> {line}".rstrip() for line in (text or "").splitlines()) or f"{indent}>"


def _short_ts(ts) -> str:
    return str(ts)[:19].replace("T", " ") if ts else "?"


def _similar(a: str, b: str) -> bool:
    a, b = _squash(a), _squash(b)
    if a == b:
        return True
    return difflib.SequenceMatcher(None, a[:4000], b[:4000]).ratio() >= 0.9


# ------------------------------------------------------------------ redaction

_REDACTIONS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[REDACTED private key]"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), "[REDACTED key]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "[REDACTED token]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "[REDACTED token]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"), "[REDACTED token]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED key]"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"), "[REDACTED key]"),
    (re.compile(r"\b(?:tvly|fc|exa)-[A-Za-z0-9_\-]{16,}"), "[REDACTED key]"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{6,}"), "[REDACTED jwt]"),
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=\-]{16,}"), r"\1 [REDACTED]"),
    (re.compile(r"\[\s*(?:\d{1,3}\s*,\s*){31,}\d{1,3}\s*\]"), "[REDACTED byte array]"),
    (re.compile(r"(://)[^/\s:@]+:[^/\s:@]+@"), r"\1[REDACTED]@"),
    (re.compile(
        r"(?i)\b([A-Za-z0-9_\-]*(?:api[_\-]?key|secret|token|passw(?:or)?d|private[_\-]?key|mnemonic|seed[_\-]?phrase)"
        r"[A-Za-z0-9_\-]*[\"']?\s*[=:]\s*[\"']?)([^\s\"'`,;\\]{8,})"), r"\1[REDACTED]"),
]


def redact(text: str) -> str:
    """Best-effort masking of credentials. It cannot recognise every secret."""
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


# -------------------------------------------------------- Claude Code parsing

_TAG = {name: re.compile(rf"<{name}>(.*?)</{name}>", re.S)
        for name in ("command-name", "command-args", "local-command-stdout", "bash-input", "bash-stdout", "bash-stderr")}


def _tag(name: str, text: str):
    match = _TAG[name].search(text)
    return match.group(1).strip() if match else None


def _parse_claude(paths, include_sidechain=False) -> Session:
    session = Session(tool="claude-code", paths=[Path(p) for p in paths])
    events: list[Event] = []
    pending: dict[str, Event] = {}
    rows = []
    for path in session.paths:
        for row in _rows(path):
            if row.get("type") in ("user", "assistant", "system", "queue-operation", "summary"):
                rows.append(row)
            if session.cwd is None and row.get("cwd"):
                session.cwd = row["cwd"]
            if row.get("sessionId"):
                session.id = row["sessionId"]  # a resumed transcript can start with rows of the session it continues
    if session.paths and not session.id:
        session.id = session.paths[0].stem

    def add(kind, row, **fields) -> Event:
        event = Event(i=len(events), kind=kind, ts=row.get("timestamp"), **fields)
        events.append(event)
        return event

    def next_is_local_stdout(position: int) -> bool:
        for later in rows[position + 1: position + 6]:
            if later.get("isMeta") or later.get("type") not in ("user", "system"):
                continue
            text = later.get("content") if later.get("type") == "system" else later.get("message", {}).get("content")
            return isinstance(text, str) and "<local-command-stdout>" in text
        return False

    def last_command():
        for event in reversed(events[-4:]):
            if event.kind == "command":
                return event
        return None

    def user_text(text: str, row, position: int):
        stripped = text.strip()
        if not stripped or row.get("isMeta"):
            return
        if stripped.startswith("[Request interrupted by user"):
            add("abort", row, text=stripped)
        elif "<command-name>" in stripped:
            name = _tag("command-name", stripped) or "/?"
            args = _tag("command-args", stripped) or ""
            # Built-in commands record <command-name> first and are followed by their output.
            # Skills and custom commands record <command-message> first and are real prompts.
            message_first = -1 < stripped.find("<command-message>") < stripped.find("<command-name>")
            if row.get("type") == "system" or next_is_local_stdout(position) or not (message_first or args):
                add("command", row, name=name, text=f"{name} {args}".strip())
            else:
                add("user", row, text=f"{name} {args}".strip())
        elif stripped.startswith("<local-command-stdout>"):
            command = last_command()
            if command is not None and command.result is None:
                command.result = _tag("local-command-stdout", stripped) or ""
        elif stripped.startswith("<bash-input>"):
            add("command", row, name="!", text="! " + (_tag("bash-input", stripped) or ""))
        elif stripped.startswith("<bash-stdout>") or stripped.startswith("<bash-stderr>"):
            command = last_command()
            if command is not None and command.result is None:
                command.result = "\n".join(filter(None, (_tag("bash-stdout", stripped), _tag("bash-stderr", stripped))))
        elif stripped.startswith("<local-command-caveat>"):
            return
        elif stripped.startswith("<system-reminder>") and stripped.endswith("</system-reminder>"):
            return
        elif stripped.startswith("<task-notification>"):
            add("note", row, text=stripped)
        else:
            add("user", row, text=text.strip("\n"))

    for position, row in enumerate(rows):
        kind = row.get("type")
        if row.get("isSidechain") and not include_sidechain:
            continue
        if row.get("timestamp"):
            session.started = session.started or row["timestamp"]
            session.ended = row["timestamp"]
        if kind == "summary":
            session.title = row.get("summary") or session.title
        elif kind == "queue-operation":
            if row.get("operation") == "enqueue" and isinstance(row.get("content"), str) and row["content"].strip():
                add("queued", row, text=row["content"].strip())
        elif kind == "system":
            content = row.get("content")
            subtype = row.get("subtype")
            if subtype == "local_command" and isinstance(content, str):
                user_text(content, row, position)
            elif subtype == "compact_boundary":
                add("note", row, text="Context was compacted here.")
            elif subtype == "api_error":
                detail = content if isinstance(content, str) else json.dumps(row.get("error") or row.get("cause") or {}, ensure_ascii=False)
                add("note", row, text=f"API error, retried: {detail}")
            elif subtype == "informational" and isinstance(content, str) and content.strip():
                add("note", row, text=content.strip())
        elif kind == "user":
            content = row.get("message", {}).get("content")
            if row.get("isCompactSummary"):
                add("compaction", row, text=_flatten(content))
            elif isinstance(content, str):
                user_text(content, row, position)
            elif isinstance(content, list):
                texts, images = [], 0
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_result":
                        call = pending.pop(block.get("tool_use_id"), None)
                        if call is not None:
                            call.result = _flatten(block.get("content"))
                            call.ok = not block.get("is_error")
                    elif block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif block.get("type") == "image":
                        images += 1
                if texts or images:
                    joined = "\n".join(texts) + (f"\n[+{images} image(s) attached]" if images else "")
                    user_text(joined, row, position)
        elif kind == "assistant":
            message = row.get("message", {})
            model = message.get("model")
            if model and model != "<synthetic>" and model not in session.models:
                session.models.append(model)
            for block in message.get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and block.get("text", "").strip():
                    if row.get("isApiErrorMessage"):
                        status = row.get("apiErrorStatus")
                        suffix = f" (HTTP {status})" if status and str(status) not in block["text"] else ""
                        add("error", row, text=block["text"].strip() + suffix)
                    else:
                        add("assistant", row, text=block["text"].strip())
                elif block.get("type") == "thinking" and str(block.get("thinking") or "").strip():
                    add("thinking", row, text=block["thinking"].strip())
                elif block.get("type") == "tool_use":
                    event = add("tool", row, name=block.get("name"), input=block.get("input"))
                    if block.get("id"):
                        pending[block["id"]] = event
    session.events = events
    return session


# -------------------------------------------------------------- Codex parsing

def _codex_meta(path: Path):
    for row in _rows(path):
        if row.get("type") == "session_meta" and isinstance(row.get("payload"), dict):
            return row["payload"]
        return None
    return None


def _codex_command(command) -> str:
    if isinstance(command, list):
        if len(command) >= 3 and command[1] in ("-lc", "-c"):
            return str(command[2])
        return " ".join(str(part) for part in command)
    return str(command or "")


def _unwrap_error(message) -> str:
    text = _flatten(message)
    try:
        inner = json.loads(text)
    except ValueError:
        return text
    if isinstance(inner, dict):
        error = inner.get("error", inner)
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
    return text


def _parse_codex(paths) -> Session:
    session = Session(tool="codex", paths=[Path(p) for p in paths])
    metas = {path: (_codex_meta(path) or {}) for path in session.paths}
    session.paths.sort(key=lambda p: (str(metas[p].get("timestamp") or ""), p.name))
    events: list[Event] = []
    pending: dict[str, Event] = {}
    seen_lines: set[int] = set()
    has_items = False

    def add(kind, row, **fields) -> Event:
        event = Event(i=0, kind=kind, ts=row.get("timestamp"), **fields)
        events.append(event)
        return event

    for path in session.paths:
        for row in _rows(path):
            fingerprint = hash(json.dumps(row, sort_keys=True))
            if fingerprint in seen_lines:
                continue
            seen_lines.add(fingerprint)
            kind = row.get("type")
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            if row.get("timestamp"):
                session.started = session.started or row["timestamp"]
                session.ended = row["timestamp"]
            if kind == "session_meta":
                session.id = session.id or payload.get("id") or payload.get("session_id")
                session.cwd = session.cwd or payload.get("cwd")
                continue
            model = payload.get("model") or (payload.get("thread_settings") or {}).get("model")
            if isinstance(model, str) and model not in session.models:
                session.models.append(model)
            if kind == "compacted":
                add("compaction", row, text=_flatten(payload.get("message")))
            elif kind == "event_msg":
                sub = payload.get("type")
                if sub == "item_completed":
                    has_items = True
                    item = payload.get("item") or {}
                    item_type = item.get("type")
                    if item_type == "UserMessage":
                        text = "\n".join(c.get("text", "") for c in item.get("content") or []
                                         if isinstance(c, dict) and isinstance(c.get("text"), str))
                        if text.strip():
                            add("user", row, text=text.strip("\n"), meta={"src": "event"})
                    elif item_type == "AgentMessage":
                        text = _flatten(item.get("content"))
                        if text.strip():
                            add("assistant", row, text=text.strip(), meta={"src": "event", "phase": item.get("phase")})
                    elif item_type == "CommandExecution":
                        code = item.get("exit_code")
                        add("tool", row, name="shell", input=_codex_command(item.get("command")),
                            result=_flatten(item.get("aggregated_output")),
                            ok=(code == 0) if code is not None else item.get("status") == "completed",
                            meta={"exit_code": code})
                    elif item_type == "FileChange":
                        changes = item.get("changes") or {}
                        add("tool", row, name="file_change",
                            input={p: (c or {}).get("type") if isinstance(c, dict) else None for p, c in changes.items()},
                            result=_squash(f"{item.get('stdout') or ''} {item.get('stderr') or ''}"),
                            ok=item.get("status") == "completed", meta={"files": list(changes)})
                    elif item_type == "McpToolCall":
                        result = item.get("result") if item.get("result") is not None else item.get("error")
                        add("tool", row, name=f"mcp:{item.get('server')}.{item.get('tool')}", input=item.get("arguments"),
                            result=_flatten(result), ok=item.get("status") == "completed")
                    elif item_type == "Reasoning":
                        text = _flatten(item.get("summary_text"))
                        if text.strip():
                            add("thinking", row, text=text.strip())
                    elif item_type == "SubAgentActivity":
                        add("worker", row, name=item.get("agent_path"), text=f"{item.get('kind')} {item.get('agent_path')}",
                            meta={"thread": item.get("agent_thread_id"), "state": item.get("kind")})
                elif sub == "user_message" and str(payload.get("message") or "").strip():
                    add("user", row, text=str(payload["message"]).strip("\n"), meta={"src": "event"})
                elif sub == "agent_message" and str(payload.get("message") or "").strip():
                    add("assistant", row, text=str(payload["message"]).strip(), meta={"src": "event"})
                elif sub == "agent_reasoning" and str(payload.get("text") or "").strip():
                    add("thinking", row, text=str(payload["text"]).strip())
                elif sub == "task_complete" and payload.get("error"):
                    add("error", row, text=_unwrap_error(payload["error"]))
                elif sub == "turn_aborted":
                    add("abort", row, text=f"Turn aborted: {payload.get('reason') or 'unknown reason'}")
                elif sub in ("error", "stream_error") and payload.get("message"):
                    add("error", row, text=_unwrap_error(payload["message"]))
            elif kind == "response_item":
                sub = payload.get("type")
                if sub == "message" and payload.get("role") in ("user", "assistant"):
                    text = _flatten(payload.get("content"))
                    if text.strip():
                        add(payload["role"], row, text=text.strip(), meta={"src": "response", "phase": payload.get("phase")})
                elif sub in ("function_call", "custom_tool_call", "local_shell_call"):
                    name = payload.get("name") or sub
                    if payload.get("namespace"):
                        name = f"{payload['namespace']}.{name}"
                    raw = payload.get("arguments") if sub == "function_call" else payload.get("input")
                    if sub == "local_shell_call":
                        raw = _codex_command((payload.get("action") or {}).get("command"))
                    value = raw
                    if sub == "function_call" and isinstance(raw, str):
                        try:
                            value = json.loads(raw)
                        except ValueError:
                            value = raw
                    if isinstance(value, dict) and name in ("shell", "local_shell", "exec_command") and value.get("command"):
                        value = _codex_command(value["command"])
                    event = add("tool", row, name=name, input=value, meta={"src": "response"})
                    if payload.get("call_id"):
                        pending[payload["call_id"]] = event
                elif sub in ("function_call_output", "custom_tool_call_output", "local_shell_call_output"):
                    call = pending.pop(payload.get("call_id"), None)
                    if call is not None:
                        output = payload.get("output")
                        if isinstance(output, str):
                            try:
                                decoded = json.loads(output)
                            except ValueError:
                                decoded = None
                            if isinstance(decoded, dict) and "output" in decoded:
                                code = (decoded.get("metadata") or {}).get("exit_code")
                                call.ok = (code == 0) if code is not None else None
                                output = decoded["output"]
                        call.result = _flatten(output)
                elif sub == "agent_message":
                    text = _flatten([c for c in payload.get("content") or []
                                     if isinstance(c, dict) and c.get("type") != "encrypted_content"])
                    kind_of = re.search(r"Message Type:\s*(\w+)", text)
                    body = text.split("Payload:", 1)[1].strip() if "Payload:" in text else text.strip()
                    label = "final answer" if kind_of and kind_of.group(1) == "FINAL_ANSWER" else "message"
                    add("worker", row, name=payload.get("author"),
                        text=f"{payload.get('author')} {label} to {payload.get('recipient')}: {body or '[encrypted]'}")

    primary_roles = {e.kind for e in events if e.meta.get("src") == "event"}
    kept = []
    for event in events:
        src = event.meta.get("src")
        if src == "response" and event.kind in ("user", "assistant"):
            if event.kind in primary_roles:
                continue  # the same message is already present as a completed item
            if event.kind == "user" and event.text.lstrip().startswith("<"):
                continue  # injected context, not something the user typed
        if src == "response" and event.kind == "tool" and has_items and event.result is not None \
                and str(event.name).split(".")[-1] in ITEM_BACKED:
            continue
        kept.append(event)
    for index, event in enumerate(kept):
        event.i = index
    session.events = kept
    if session.paths and not session.id:
        session.id = session.paths[0].stem
    return session


def detect_tool(path: Path) -> str:
    for row in _rows(path):
        if row.get("type") == "session_meta" or ("payload" in row and "timestamp" in row):
            return "codex"
        return "claude-code"
    return "claude-code"


def parse_session(paths, tool: str, include_sidechain: bool = False) -> Session:
    paths = [Path(p) for p in paths]
    if tool == "codex":
        return _parse_codex(paths)
    return _parse_claude(paths, include_sidechain=include_sidechain)


# ------------------------------------------------------------------ discovery

def _claude_probe(path: Path):
    """Return (cwd, first timestamp) from the start of a Claude Code transcript."""
    cwd = started = None
    for count, row in enumerate(_rows(path)):
        cwd = cwd or row.get("cwd")
        started = started or row.get("timestamp")
        if (cwd and started) or count > 400:
            break
    return cwd, started


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _discover_claude(cwd, claude_dir: Path) -> list:
    refs = []
    projects = Path(claude_dir) / "projects"
    if not projects.is_dir():
        return refs
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(cwd)) if cwd else None
    for folder in sorted(p for p in projects.iterdir() if p.is_dir()):
        files = sorted(folder.glob("*.jsonl"), key=_mtime, reverse=True)
        if not files:
            continue
        if cwd is not None and folder.name != slug:
            # A project folder holds one working directory; probing its newest files is enough.
            if not any(_same_or_inside(_claude_probe(f)[0], cwd) for f in files[:2]):
                continue
        for file in files:
            session_cwd, started = _claude_probe(file)
            if cwd is not None and session_cwd and not _same_or_inside(session_cwd, cwd):
                continue
            ref = SessionRef(tool="claude-code", id=file.stem, cwd=session_cwd, paths=[file],
                             started=started, last_activity=_mtime(file))
            side = file.with_suffix("") / "subagents"
            if side.is_dir():
                for child in sorted(side.glob("*.jsonl"), key=_mtime):
                    ref.children.append(SessionRef(tool="claude-code", id=child.stem, cwd=session_cwd, paths=[child],
                                                   last_activity=_mtime(child), label=child.stem, parent=ref.id))
            refs.append(ref)
    return refs


def _discover_codex(cwd, codex_dir: Path, days) -> list:
    sessions = Path(codex_dir) / "sessions"
    if not sessions.is_dir():
        return []
    files = list(sessions.rglob("rollout-*.jsonl"))
    if days:
        cutoff = time.time() - days * 86400
        recent = [f for f in files if _mtime(f) >= cutoff]
        files = recent or files
    grouped: dict[str, SessionRef] = {}
    for file in files:
        meta = _codex_meta(file)
        if not meta:
            continue
        sid = meta.get("id") or meta.get("session_id")
        if not sid or (cwd is not None and not _same_or_inside(meta.get("cwd"), cwd)):
            continue
        source = meta.get("source") if isinstance(meta.get("source"), dict) else {}
        spawn = (source.get("subagent") or {}).get("thread_spawn") or {}
        parent = meta.get("parent_thread_id") or spawn.get("parent_thread_id")
        if meta.get("thread_source") != "subagent" and not spawn:
            parent = None
        ref = grouped.get(sid)
        if ref is None:
            ref = grouped[sid] = SessionRef(tool="codex", id=sid, cwd=meta.get("cwd"), paths=[],
                                            started=meta.get("timestamp"), parent=parent,
                                            label=spawn.get("agent_path") or meta.get("agent_path"))
        ref.paths.append(file)
        ref.started = min(filter(None, (ref.started, meta.get("timestamp"))), default=None)
        ref.last_activity = max(ref.last_activity, _mtime(file))
    roots = []
    for ref in grouped.values():
        ref.paths.sort(key=lambda p: p.name)
        if ref.parent is None:
            roots.append(ref)
        elif ref.parent in grouped:
            grouped[ref.parent].children.append(ref)
    for ref in roots:
        ref.children.sort(key=lambda child: child.last_activity)
    return roots


def discover(cwd, claude_dir, codex_dir, days=None) -> list:
    """Sessions recorded for this working directory, newest activity first. cwd=None lists everything."""
    refs = _discover_claude(cwd, Path(claude_dir)) + _discover_codex(cwd, Path(codex_dir), days)
    refs.sort(key=lambda ref: ref.last_activity, reverse=True)
    return refs


def _invoked_recovery(ref: SessionRef) -> bool:
    """A live session that was opened just to run this skill, judged from its transcript."""
    events = ref.session().events
    prompts = [e for e in events if e.kind == "user"]
    if not prompts or "continue-work" not in prompts[-1].text.lower():
        return False
    after = events[prompts[-1].i + 1:]
    if any(e.kind == "error" for e in after):
        return False
    return time.time() - ref.last_activity < 600


def choose_chain(refs, current_ids, sessions=None, max_sessions=4):
    """Pick what to recover: (sessions oldest first, session assumed to be the live one, older sessions).

    The newest session is always included. While it is thin, the one before it is added too, so a
    string of short failed retries still leads back to the session that did the real work.
    """
    current_ids = {c for c in current_ids if c}
    candidates = [r for r in refs if r.id not in current_ids]
    assumed = None
    if not current_ids and candidates and _invoked_recovery(candidates[0]):
        assumed, candidates = candidates[0], candidates[1:]
    chain, older = [], []
    remaining = iter(candidates)
    for ref in remaining:
        if not ref.prompts():
            continue
        chain.append(ref)
        if len(chain) >= (sessions or max_sessions) or (not sessions and ref.work() >= THIN_SESSION):
            break
    for ref in remaining:
        if len(older) >= 8:
            break
        if ref.prompts():
            older.append(ref)
    chain.reverse()
    return chain, assumed, older


def pick_previous(refs, current_ids):
    """The most recent session that is not the live one and holds a conversation."""
    chain = choose_chain(refs, current_ids)[0]
    return chain[-1] if chain else None


# --------------------------------------------------------- turns and endings

def build_turns(events) -> list:
    turns = [Turn(index=0, prompt=None, events=[])]
    for event in events:
        if event.kind == "user":
            turns.append(Turn(index=len(turns), prompt=event, events=[]))
        else:
            turns[-1].events.append(event)
    return turns


def analyze_ending(session: Session) -> dict:
    turns = build_turns(session.events)
    result = {"state": "empty", "unanswered": [], "in_flight": [], "errors": [], "queued_undelivered": [],
              "last_worked_turn": None, "last_worked_outcome": None, "turns": turns}
    if not session.events:
        return result
    trailing = []
    position = len(turns) - 1
    while position >= 0 and turns[position].prompt is not None and turns[position].work == 0:
        trailing.append(turns[position])
        position -= 1
    trailing.reverse()
    worked = [t for t in turns if t.work > 0]
    last_worked = worked[-1] if worked else None
    if last_worked is not None:
        result["last_worked_turn"] = last_worked.index
        result["last_worked_outcome"] = last_worked.outcome
        result["in_flight"] = [e for e in last_worked.events if e.kind == "tool" and e.result is None]
    scope = ([last_worked] if last_worked else []) + trailing
    result["errors"] = [e.text for t in scope for e in t.events if e.kind == "error"]
    for turn in trailing:
        error = next((e.text for e in reversed(turn.events) if e.kind == "error"), None)
        groups = result["unanswered"]
        if groups and _similar(groups[-1]["text"], turn.prompt.text):
            groups[-1].update(text=turn.prompt.text, event=turn.prompt.i, error=error or groups[-1]["error"],
                              attempts=groups[-1]["attempts"] + 1)
        else:
            groups.append({"text": turn.prompt.text, "event": turn.prompt.i, "error": error, "attempts": 1})
    for event in session.events:
        if event.kind != "queued":
            continue
        later = [_squash(e.text) for e in session.events[event.i + 1:] if e.kind in ("user", "command")]
        wanted = _squash(event.text)
        if not any(text == wanted or text.startswith(wanted) for text in later):
            result["queued_undelivered"].append(event.text)
    if trailing:
        result["state"] = "unanswered"
    else:
        result["state"] = {"answered": "clean", "error": "failed", "interrupted": "interrupted",
                           "in_flight": "in_flight", "cut_off": "cut_off"}.get(turns[-1].outcome, "empty")
    return result


# --------------------------------------------------------------- work ledger

_RISKY = re.compile(
    r"\bgit\s+(?:-C\s+\S+\s+)?(?:push|commit|merge|rebase|cherry-pick|revert|reset\s+--hard|clean\s+-"
    r"|tag\s+(?:-[asdfm]\b|[^-\s;|&]))"
    r"|\bgh\s+(?:pr|release|repo|issue|workflow|gist)\s+(?:create|merge|close|delete|edit|comment|run|review)"
    r"|\bgh\s+api\b.*(?:-X|--method)\s*(?:POST|PUT|PATCH|DELETE)"
    r"|\b(?:npm|pnpm|yarn|cargo|gem|poetry|uv|bun)\s+publish\b|\btwine\s+upload\b"
    r"|\bdocker\s+push\b|\bkubectl\s+(?:apply|delete|rollout|scale|patch)\b|\bhelm\s+(?:install|upgrade|uninstall)\b"
    r"|\bterraform\s+(?:apply|destroy)\b|\b(?:vercel|netlify|wrangler|flyctl|fly|railway|firebase|serverless|sls)\b.*\b(?:deploy|publish)\b"
    r"|\b(?:aws|gcloud|az)\s+.*\b(?:create|delete|deploy|put|update|rm)\b"
    r"|\bcurl\b.*(?:-X|--request)\s*(?:POST|PUT|PATCH|DELETE)|\bcurl\b.*\s(?-i:-d|--data\S*|-F|--form)\s"
    r"|\b(?:alembic|prisma|knex|sequelize|flyway|liquibase|manage\.py|rails|rake)\b.*\bmigrat"
    r"|\b(?:DROP|TRUNCATE)\s+(?:TABLE|DATABASE)\b|\bDELETE\s+FROM\b"
    r"|\brm\s+-[A-Za-z]*r|\bmkfs\b|\bdd\s+if="
    r"|\bsolana\s+(?:transfer|program\s+deploy|airdrop)\b|\bspl-token\s+(?:transfer|mint|burn)\b|\banchor\s+deploy\b"
    r"|\bcast\s+send\b|\bforge\s+script\b.*--broadcast|\bsendmail\b", re.I)
_RISKY_TOOL = re.compile(r"(?i)(send|create|delete|update|post|publish|deploy|merge|push|transfer|order|submit|"
                         r"pay|purchase|trash|reply|forward|write)")


def _command_of(event: Event):
    if event.kind != "tool":
        return None
    if event.name in ("Bash", "shell", "exec", "local_shell", "exec_command"):
        if isinstance(event.input, dict):
            return str(event.input.get("command") or event.input.get("cmd") or "")
        return str(event.input or "")
    return None


def _files_of(event: Event) -> list:
    if event.kind != "tool":
        return []
    if event.meta.get("files"):
        return list(event.meta["files"])
    if event.name in ("Write", "Edit", "MultiEdit", "NotebookEdit") and isinstance(event.input, dict):
        path = event.input.get("file_path") or event.input.get("notebook_path")
        return [str(path)] if path else []
    return []


_HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")
_REDIRECT = re.compile(r"(?<![0-9&>])>{1,2}\s*(\"[^\"\n]+\"|'[^'\n]+'|[^\s;&|<>()]+)")


_SHELL_READER = re.compile(r"\b(?:bash|sh|zsh|ssh|psql|mysql|sqlite3|kubectl)\b")


def _without_heredocs(command: str, keep_shell_input: bool = False) -> str:
    """Drop here-document bodies, which are data. With keep_shell_input, keep the ones a shell or database reads."""
    kept, closing, keeping = [], None, False
    for line in (command or "").splitlines():
        if closing is not None:
            if line.strip() == closing:
                closing = None
            elif keeping:
                kept.append(line)
            continue
        kept.append(line)
        marker = _HEREDOC.search(line)
        if marker:
            closing = marker.group(1)
            keeping = keep_shell_input and bool(_SHELL_READER.search(line[: marker.start()]))
    return "\n".join(kept)


def _shell_targets(command: str) -> list:
    """Files a shell command writes through > or >>. Best effort."""
    targets = []
    for match in _REDIRECT.finditer(_without_heredocs(command)):
        target = match.group(1).strip("\"'")
        if target.startswith("/dev/") or not re.fullmatch(r"[\w./~+@%-]+", target) or not re.search(r"[A-Za-z]", target):
            continue
        if target not in targets:
            targets.append(target)
    return targets


def _status(event: Event) -> str:
    if event.result is None:
        return "NO RESULT RECORDED"
    if event.ok is True:
        return "ok"
    if event.ok is False:
        code = event.meta.get("exit_code")
        return f"FAILED (exit {code})" if code is not None else "FAILED"
    return "result recorded"


def _brief(event: Event, limit: int) -> str:
    """One-line description of what a tool call was asked to do."""
    value = event.input
    if isinstance(value, dict):
        for key in ("command", "cmd", "file_path", "notebook_path", "path", "pattern", "query", "url",
                    "description", "skill", "prompt"):
            if value.get(key):
                extra = f" ({_squash(str(value['description']))})" if key == "command" and value.get("description") else ""
                return _head(_squash(str(value[key])), limit) + extra
        value = json.dumps(value, ensure_ascii=False)
    return _head(_squash(re.sub(r"gAAAA[A-Za-z0-9_\-=]{40,}", "[encrypted]", str(value or ""))), limit)


def _is_risky(event: Event) -> bool:
    command = _command_of(event)
    if command is not None:
        return bool(_RISKY.search(_without_heredocs(command, keep_shell_input=True)))
    name = str(event.name or "")
    return event.kind == "tool" and name.startswith("mcp") and bool(_RISKY_TOOL.search(name.split("__")[-1].split(".")[-1]))


def _plan_lines(events) -> list:
    """The most recent todo list or plan the agent recorded."""
    for event in reversed(events):
        if event.kind != "tool" or not isinstance(event.input, dict):
            continue
        if event.name == "TodoWrite" and isinstance(event.input.get("todos"), list):
            return [f"- [{t.get('status', '?')}] {t.get('content', '')}" for t in event.input["todos"] if isinstance(t, dict)]
        if str(event.name).endswith("update_plan") and isinstance(event.input.get("plan"), list):
            return [f"- [{s.get('status', '?')}] {s.get('step', '')}" for s in event.input["plan"] if isinstance(s, dict)]
        if event.name == "ExitPlanMode" and event.input.get("plan"):
            return _clip(str(event.input["plan"]), 4000).splitlines()
    return []


# ------------------------------------------------------------------ rendering

_STATE_TEXT = {
    "clean": "The last prompt was answered and nothing was left running. Continue from the last answer.",
    "failed": "The session stopped on an error while the agent was working. The work in the last turn is unfinished.",
    "unanswered": "The newest prompt(s) were never answered. Treat the last one as the active request.",
    "in_flight": "The transcript stops while a tool call was still running. Its outcome is unknown; check its effects.",
    "cut_off": "The transcript stops right after a tool result, before the agent replied. The turn is unfinished.",
    "interrupted": "The user interrupted the last turn. Do not assume the interrupted step should be redone.",
    "empty": "The transcript holds no conversation.",
}
_OUTCOME_TEXT = {"answered": "answered", "error": "stopped on an error", "interrupted": "interrupted",
                 "in_flight": "tool call still running", "cut_off": "cut off before a reply",
                 "no_response": "no response"}


def _script_call() -> str:
    path = str(Path(__file__).resolve())
    return f'python3 "{path}"' if " " in path else f"python3 {path}"


def _fit(items, cap, big, small):
    """Give the first and the last three items room, squeeze the rest, and drop the middle if still too long.

    items: list of text lengths. Returns {index: limit} for the items to show.
    """
    count = len(items)
    favoured = {0} | {i for i in range(count - 3, count) if i >= 0}
    limits = {i: (big if i in favoured else small) for i in range(count)}
    keep = list(range(count))
    while len(keep) > 4 and sum(min(items[i], limits[i]) + 60 for i in keep) > cap:
        del keep[1]  # drop the oldest of the middle items first
    return {i: limits[i] for i in keep}


def render_digest(session: Session, budget: int = DEFAULT_BUDGET, redact_output: bool = True,
                  children=(), note: str | None = None, masked: bool | None = None) -> str:
    budget = max(int(budget), 4000)
    events = session.events
    ending = analyze_ending(session)
    turns = ending["turns"]
    call = _script_call()
    ref = f"--session {session.id}" if session.id else f'--file "{session.paths[0]}"'
    counts = {kind: sum(1 for e in events if e.kind == kind) for kind in ("user", "assistant", "thinking", "tool", "error")}
    out = [
        f"# Session digest: {session.tool} {session.id or '(unknown id)'}",
        "",
        "Rebuilt from the transcript on disk. It is a condensed record, not the conversation itself.",
        "",
        f"- Working directory: {session.cwd or 'unknown'}",
        f"- First record: {_short_ts(session.started)} · last record: {_short_ts(session.ended)} (transcript timestamps, UTC)",
        f"- Model(s): {', '.join(session.models) or 'not recorded'}",
        f"- Contents: {counts['user']} user prompts, {counts['assistant']} agent messages, "
        f"{counts['thinking']} agent working notes, {counts['tool']} tool calls, {counts['error']} errors, "
        f"{len(events)} events",
        f"- Transcript file(s): {'; '.join(str(p) for p in session.paths)}",
        f"- Any event in full: `{call} show {ref} --event N` · find events: `{call} search {ref} REGEX`",
        f"- Credentials are masked on a best-effort basis: {'yes' if (redact_output if masked is None else masked) else 'no'}",
    ]
    if note:
        out.append(f"- Note: {note}")

    out += ["", "## How the session ended", "", _STATE_TEXT[ending["state"]]]
    if ending["last_worked_turn"] is not None:
        turn = turns[ending["last_worked_turn"]]
        prompt = _head(_squash(turn.prompt.text), 300) if turn.prompt else "(before any prompt)"
        out.append(f"- Last turn with agent work: turn {turn.index}, {_OUTCOME_TEXT[turn.outcome]}. Prompt: \"{prompt}\"")
    for event in ending["in_flight"][:8]:
        out.append(f"- Still running at the end: #{event.i} {event.name}: {_brief(event, 300)} -> NO RESULT RECORDED")
    seen_errors = []
    for error in reversed(ending["errors"]):
        if error not in seen_errors:
            seen_errors.append(error)
    for error in reversed(seen_errors[:3]):
        out.append(f"- Error: {_head(_squash(error), 600)}")
    for group in ending["unanswered"][-3:]:
        tries = f", sent {group['attempts']} times" if group["attempts"] > 1 else ""
        out.append(f"- Prompt that was never answered (#{group['event']}{tries}):")
        out.append("")
        out.append(_quote(_clip(group["text"], min(3000, budget // 14), f"; full text: show --event {group['event']}")))
        out.append("")
    significant = [e for e in events if e.kind in SIGNIFICANT]
    if significant and significant[-1].kind == "error":
        for event in events[significant[-1].i + 1:]:
            if event.kind == "worker":
                out.append(f"- A worker reported after the session stopped (#{event.i}, {_short_ts(event.ts)}): "
                           f"{_head(_squash(event.text), 400)}. Check what it wrote.")
    for text in ending["queued_undelivered"][-5:]:
        out.append(f"- Typed while the agent was busy and never delivered: \"{_head(_squash(text), 500)}\"")
    prompt_turns = [t for t in turns if t.prompt is not None]
    out += ["", "## User prompts (verbatim, in order)", ""]
    if not prompt_turns:
        out.append("None recorded.")
    cap = int(budget * 0.30)
    limits = _fit([len(t.prompt.text) for t in prompt_turns], cap, big=max(int(cap * 0.22), 600), small=max(int(cap * 0.03), 240))
    if sum(len(t.prompt.text) + 60 for t in prompt_turns) <= cap:
        limits = {i: len(t.prompt.text) for i, t in enumerate(prompt_turns)}
    previous = -1
    for index in sorted(limits):
        if index - previous > 1:
            first, last = prompt_turns[previous + 1].prompt.i, prompt_turns[index - 1].prompt.i
            out += [f"_{index - previous - 1} prompt(s) omitted here (events #{first} to #{last}); use show or search._", ""]
        previous = index
        turn = prompt_turns[index]
        final = turn is turns[-1]
        outcome = _OUTCOME_TEXT[turn.outcome] if final or turn.outcome in ("answered", "error", "no_response") else "interrupted"
        out.append(f"### Turn {turn.index} · #{turn.prompt.i} · {_short_ts(turn.prompt.ts)} · {outcome}")
        out.append("")
        out.append(_quote(_clip(turn.prompt.text, limits[index], f"; full text: show --event {turn.prompt.i}")))
        out.append("")

    compactions = [e for e in events if e.kind == "compaction"]
    if compactions:
        latest = compactions[-1]
        out += ["## Latest compaction summary", "",
                f"Written by the previous agent at #{latest.i} ({_short_ts(latest.ts)}); "
                f"{len(compactions)} compaction(s) in total. Events before it may be missing detail.", "",
                _quote(_clip(latest.text, int(budget * 0.10), f"; full text: show --event {latest.i}")), ""]

    out += ["## What the agent reported at the end of each turn", ""]
    reports = []
    for turn in prompt_turns:
        said = [e for e in turn.events if e.kind == "assistant"]
        final_answers = [e for e in said if e.meta.get("phase") == "final_answer"]
        notes = [e for e in turn.events if e.kind == "thinking"]
        reports.append((turn, (final_answers or said or notes or [None])[-1]))
    cap = int(budget * 0.14)
    limits = _fit([len(r.text) if r else 20 for _, r in reports], cap, big=max(int(cap * 0.28), 500), small=400)
    if len(limits) < len(reports):
        out.append(f"_{len(reports) - len(limits)} earlier turn(s) omitted; use show or search._")
    for index in sorted(limits):
        turn, report = reports[index]
        if report is None:
            out.append(f"- Turn {turn.index}: no agent message ({_OUTCOME_TEXT[turn.outcome]}).")
        else:
            body = _clip(report.text, limits[index], f"; full text: show --event {report.i}")
            origin = ", from the agent's working notes" if report.kind == "thinking" else ""
            out.append(f"- Turn {turn.index} (#{report.i}{origin}, {_OUTCOME_TEXT[turn.outcome]}):")
            out.append(_quote(body, "  "))
    if not reports:
        out.append("None recorded.")

    out += ["", "## Work ledger", ""]
    files: dict[str, list] = {}
    for event in events:
        written = [(path, "edit tool") for path in _files_of(event)]
        written += [(path, "shell redirect") for path in _shell_targets(_command_of(event) or "")]
        for path, how in written:
            entry = files.setdefault(path, [0, event.i, how])
            entry[0] += 1
            entry[1] = event.i
    if files:
        out.append(f"Files written or edited ({len(files)}), most recent first:")
        for path, (count, last, how) in sorted(files.items(), key=lambda kv: -kv[1][1])[:60]:
            out.append(f"- {path} ({how}, x{count}, last #{last})")
        if len(files) > 60:
            out.append(f"- ... and {len(files) - 60} more")
    else:
        out.append("Files written or edited: none recorded.")
    out.append("Scripts and other commands can change files without appearing in this list. "
               "The working tree itself is the authority.")
    commands = [e for e in events if _command_of(e) is not None]
    if commands:
        failed = sum(1 for e in commands if e.ok is False)
        out += ["", f"Shell commands: {len(commands)} run, {failed} failed. Most recent {min(len(commands), 20)}:"]
        for event in commands[-20:]:
            out.append(f"- #{event.i} `{_head(_squash(_command_of(event)), 240)}` -> {_status(event)}")
    workers: dict[str, str] = {}
    for event in events:
        if event.kind == "worker" and event.name:
            workers[event.name] = _head(_squash(event.text), 260)
        elif event.kind == "tool" and event.name in ("Agent", "Task") and isinstance(event.input, dict):
            label = str(event.input.get("description") or event.input.get("subagent_type") or f"agent #{event.i}")
            workers[label] = f"#{event.i} {_status(event)}"
    for child in children:
        workers.pop(child.label or child.id, None)
    if workers or children:
        out += ["", "Workers started by this session. A worker can keep running after the turn that started it, "
                    "so go by its last report and by what is on disk, not by when the session stopped:"]
        for label, state in list(workers.items())[-20:]:
            out.append(f"- {label}: {state}")
        for child in list(children)[-12:]:
            child_events = child.session().events
            last = next((e for e in reversed(child_events) if e.kind in ("error", "assistant")), None)
            state = f"{last.kind}: {_head(_squash(last.text), 220)}" if last else "no messages"
            out.append(f"- {child.label or child.id} (own transcript: --session {child.id}), last write "
                       f"{_short_ts(_iso(child.last_activity))} UTC, last {state}")
    plan = _plan_lines(events)
    if plan:
        out += ["", "Latest plan or todo list recorded by the agent:"] + plan[:40]
    other: dict[str, int] = {}
    for event in events:
        if event.kind == "tool" and _command_of(event) is None and not _files_of(event):
            other[str(event.name)] = other.get(str(event.name), 0) + 1
    if other:
        top = sorted(other.items(), key=lambda kv: -kv[1])[:15]
        out += ["", "Other tools used: " + ", ".join(f"{name} x{count}" for name, count in top)]
    local = [e for e in events if e.kind == "command"]
    if local:
        out += ["", "Commands the user ran directly: " + ", ".join(_head(_squash(e.text), 80) for e in local[-12:])]

    risky = [e for e in events if _is_risky(e)]
    out += ["", "## Verify before repeating", ""]
    if risky:
        out.append("These calls can change things outside the working tree or cannot be undone. "
                   "Check the real outcome before running any of them again.")
        for event in risky[-30:]:
            out.append(f"- #{event.i} {_short_ts(event.ts)} {event.name}: `{_brief(event, 260)}` -> {_status(event)}")
    else:
        out.append("No pushes, publishes, deployments, migrations, deletions or similar calls were recognised. "
                   "The check is pattern-based, so read the final stretch as well.")

    text = "\n".join(out)
    remaining = max(budget - len(text) - 160, 1500)
    tail = []
    for event in reversed(events):
        line = _tail_line(event)
        if len(line) > remaining and tail:
            break
        tail.append(_head(line, remaining))
        remaining -= len(line) + 1
        if remaining <= 0:
            break
    tail.reverse()
    out += ["", "## Final stretch (oldest first, ends where the transcript ends)", ""]
    if tail and len(tail) < len(events):
        out.append(f"_{len(events) - len(tail)} earlier events not shown here._")
    out += tail or ["No events."]
    text = "\n".join(out) + "\n"
    return redact(text) if redact_output else text


def _need(session: Session) -> int:
    """Rough size of a digest that leaves nothing out."""
    return 3500 + sum(min(len(e.text) + len(str(e.input or "")) + len(e.result or ""), 3000) + 40 for e in session.events)


def render_recovery(chain, budget: int = DEFAULT_BUDGET, redact_output: bool = True, note: str | None = None,
                    older=()) -> str:
    """Digest one session, or several consecutive ones (oldest first) within one overall budget."""
    budget = max(int(budget), 4000)
    shares = {}
    left, waiting = budget, sorted(chain, key=lambda ref: _need(ref.session()))
    while waiting:  # small sessions get what they need, the rest share what is left
        ref = waiting.pop(0)
        shares[ref.id] = max(min(_need(ref.session()), left // (len(waiting) + 1)), 4000)
        left = max(left - shares[ref.id], 0)
    parts = []
    if len(chain) > 1:
        lines = [f"# Recovery digest: {len(chain)} sessions, oldest first", "",
                 "The most recent session was short, so the sessions before it are included. "
                 "The last one below is the most recent: its ending is the current state.", ""]
        for number, ref in enumerate(chain, 1):
            state = analyze_ending(ref.session())["state"]
            lines.append(f"{number}. {ref.tool} {ref.id}: last write {_short_ts(_iso(ref.last_activity))} UTC, "
                         f"{len(ref.prompts())} prompts, {ref.work()} agent messages and tool calls, ended: {state}")
        parts.append("\n".join(lines) + "\n")
    for ref in chain:
        parts.append(render_digest(ref.session(), budget=shares[ref.id], redact_output=False, children=ref.children,
                                   note=note if ref is chain[-1] else None, masked=redact_output))
    if older:
        call = _script_call()
        lines = ["## Earlier sessions in this project", "",
                 f"Not included above. Digest one with `{call} digest --session ID`.", ""]
        for ref in older:
            first = ref.prompts()[0]
            lines.append(f"- {ref.tool} {ref.id}: started {_short_ts(ref.started)}, last write "
                         f"{_short_ts(_iso(ref.last_activity))} UTC, {len(ref.prompts())} prompts, {ref.work()} agent "
                         f"messages and tool calls. First prompt: \"{_head(_squash(first.text), 200)}\"")
        parts.append("\n".join(lines) + "\n")
    text = "\n---\n\n".join(parts)
    return redact(text) if redact_output else text


def _tail_line(event: Event) -> str:
    stamp = f"#{event.i} {_short_ts(event.ts)[11:]}"
    if event.kind == "user":
        return f"{stamp} USER: {_head(_squash(event.text), 300)} (full text above)"
    if event.kind == "assistant":
        body = _clip(event.text, 2500, f"; show --event {event.i}")
        return f"{stamp} AGENT: {body}" if "\n" not in body else f"{stamp} AGENT:\n{_quote(body, '  ')}"
    if event.kind == "thinking":
        return f"{stamp} AGENT NOTE: {_clip(_squash(event.text), 700)}"
    if event.kind == "tool":
        result = "" if event.result is None else f" | {_clip(_squash(event.result), 500)}"
        return f"{stamp} TOOL {event.name}: {_brief(event, 400)} -> {_status(event)}{result}"
    if event.kind == "error":
        return f"{stamp} ERROR: {_head(_squash(event.text), 700)}"
    if event.kind == "compaction":
        return f"{stamp} COMPACTION: context was summarised here (see the summary above)"
    return f"{stamp} {event.kind.upper()}: {_head(_squash(event.text), 300)}"


def _iso(seconds: float) -> str:
    return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _window(value: str, max_chars: int, offset: int) -> str:
    """A slice of a long field, with a note on how to read the rest."""
    piece = value[offset: offset + max_chars]
    before = f"[from character {offset}] " if offset else ""
    left = len(value) - offset - len(piece)
    after = f" [+{left} more characters: add --offset {offset + max_chars}]" if left > 0 else ""
    return f"{before}{piece}{after}"


def render_event(event: Event, max_chars: int, offset: int = 0) -> str:
    lines = [f"#{event.i} {event.kind} {event.ts or ''} {event.name or ''}".rstrip()]
    if event.text:
        lines += ["text:", _window(event.text, max_chars, offset)]
    if event.input is not None:
        value = event.input if isinstance(event.input, str) else json.dumps(event.input, ensure_ascii=False, indent=2)
        lines += ["input:", _window(value, max_chars, offset)]
    if event.kind == "tool":
        lines += [f"status: {_status(event)}"]
        if event.result is not None:
            lines += ["result:", _window(event.result, max_chars, offset)]
    elif event.result:
        lines += ["output:", _window(event.result, max_chars, offset)]
    return "\n".join(lines)


def paginate(text: str, part_size: int) -> list:
    """Split a digest at line ends into parts that leave room for a header and a footer."""
    room = max(int(part_size) - 700, 1000)
    parts, current, size = [], [], 0
    for line in text.splitlines():
        pieces = [line[i: i + room] for i in range(0, len(line), room)] or [""]
        for piece in pieces:
            if current and size + len(piece) + 1 > room:
                parts.append("\n".join(current))
                current, size = [], 0
            current.append(piece)
            size += len(piece) + 1
    if current:
        parts.append("\n".join(current))
    return parts or [""]


# ------------------------------------------------------------------------ CLI

def _current_ids(args) -> set:
    ids = {os.environ.get(name) for name in CURRENT_ID_ENV}
    ids.update(args.current or [])
    return {value for value in ids if value}


def _resolve(args):
    """Return (sessions oldest first, note, older sessions). Raises LookupError with a message for the user."""
    if args.file:
        path = Path(args.file)
        if not path.is_file():
            raise LookupError(f"No such transcript file: {path}")
        tool = args.tool or detect_tool(path)
        return [SessionRef(tool=tool, id=parse_session([path], tool).id or path.stem, cwd=None, paths=[path],
                           last_activity=_mtime(path))], None, []
    cwd = os.path.abspath(args.cwd or os.getcwd())
    refs = discover(cwd, args.claude_dir, args.codex_dir, days=args.days)
    if args.session:
        for pool in (refs, None):
            if pool is None:
                pool = discover(None, args.claude_dir, args.codex_dir)
            flat = pool + [child for ref in pool for child in ref.children]
            exact = [r for r in flat if r.id == args.session]
            matches = exact or [r for r in flat if r.id.startswith(args.session)]
            if len(matches) == 1:
                return [matches[0]], None, []
            if len(matches) > 1:
                raise LookupError("Session id is ambiguous: " + ", ".join(f"{r.tool} {r.id}" for r in matches[:8]))
        raise LookupError(f"No session matches '{args.session}'. Run `list --all` to see what exists.")
    chain, assumed, older = choose_chain(refs, _current_ids(args), sessions=getattr(args, "sessions", None))
    if not chain:
        raise LookupError(
            f"No previous session found for {cwd}.\n"
            f"Looked in {Path(args.claude_dir) / 'projects'} and {Path(args.codex_dir) / 'sessions'}.\n"
            "If the project folder was moved or renamed, or the work happened on another machine, run "
            "`list --all`, pass `--session ID`, or pass a transcript with `--file PATH`.")
    note = None
    if assumed is not None:
        note = (f"session {assumed.id} was taken to be the conversation you are in now, because its last prompt "
                "invoked continue-work. If that is wrong, pass --session explicitly.")
    elif not _current_ids(args):
        note = ("the current session could not be identified. If this digest describes the conversation you are in "
                "now, run `list` and pass the right id with --session.")
    return chain, note, older


def cmd_list(args) -> int:
    cwd = None if args.all else os.path.abspath(args.cwd or os.getcwd())
    refs = discover(cwd, args.claude_dir, args.codex_dir, days=args.days)
    if not refs:
        print(f"No sessions found for {cwd or 'any project'}.")
        return 2
    current = _current_ids(args)
    print(f"Sessions for {cwd or 'all projects'}, newest activity first:")
    for position, ref in enumerate(refs[: args.limit]):
        mark = "  [current session]" if ref.id in current else ""
        line = f"{ref.id}  {ref.tool}  started {_short_ts(ref.started)}  last write {_short_ts(_iso(ref.last_activity))} UTC{mark}"
        if cwd is None:
            line += f"  cwd {ref.cwd}"
        print(line)
        if position < args.detail:
            prompts = ref.prompts()
            ending = analyze_ending(ref.session())
            print(f"    {len(prompts)} prompts, {ref.work()} agent messages and tool calls, "
                  f"{len(ref.children)} worker transcripts, ended: {ending['state']}")
            if prompts:
                print(f"    first prompt: {redact(_head(_squash(prompts[0].text), 160))}")
            if len(prompts) > 1:
                print(f"    last prompt:  {redact(_head(_squash(prompts[-1].text), 160))}")
    if len(refs) > args.limit:
        print(f"... {len(refs) - args.limit} older sessions not shown (raise --limit).")
    return 0


def cmd_digest(args) -> int:
    chain, note, older = _resolve(args)
    text = render_recovery(chain, budget=args.budget, redact_output=not args.no_redact, note=note, older=older)
    if args.part == "all":
        print(text.rstrip("\n"))
        print(END_MARK)
        return 0
    parts = paginate(text, args.part_size)
    try:
        number = int(args.part)
    except ValueError:
        raise LookupError("--part takes a number or 'all'.") from None
    if not 1 <= number <= len(parts):
        raise LookupError(f"This digest has only {len(parts)} part{'s' if len(parts) != 1 else ''}.")
    if len(parts) > 1:
        print(f"[Digest part {number} of {len(parts)}. Read every part before acting.]")
    print(parts[number - 1])
    if number < len(parts):
        rest, skip = [], False
        for value in args.argv:
            if skip or value.startswith("--part="):
                skip = False
            elif value == "--part":
                skip = True
            else:
                rest.append(value)
        command = " ".join([_script_call()] + [shlex.quote(value) for value in rest] + ["--part", str(number + 1)])
        print(f"[End of part {number} of {len(parts)}. Next: {command}]")
    else:
        print(END_MARK)
    return 0


def cmd_show(args) -> int:
    ref = _resolve(args)[0][-1]
    events = ref.session().events
    wanted = []
    for spec in args.event:
        low, _, high = spec.partition("-")
        wanted += range(int(low), int(high or low) + 1)
    for index in wanted:
        if not 0 <= index < len(events):
            print(f"#{index}: no such event (the session has {len(events)}, numbered from 0)")
            continue
        text = render_event(events[index], args.max_chars, args.offset)
        print(text if args.no_redact else redact(text))
        print()
    return 0


def cmd_search(args) -> int:
    ref = _resolve(args)[0][-1]
    pattern = re.compile(args.pattern, re.I)
    hits = 0
    for event in ref.session().events:
        haystack = "\n".join(str(part) for part in (
            event.text, event.name or "",
            event.input if isinstance(event.input, str) else json.dumps(event.input, ensure_ascii=False) if event.input else "",
            event.result or ""))
        match = pattern.search(haystack)
        if not match:
            continue
        snippet = _squash(haystack[max(match.start() - 100, 0): match.end() + 160])
        line = f"#{event.i} {event.kind} {_short_ts(event.ts)}: {snippet}"
        print(line if args.no_redact else redact(line))
        hits += 1
        if hits >= args.limit:
            print(f"... stopped at {args.limit} matches (raise --limit).")
            break
    if not hits:
        print("No matches.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    home = Path.home()
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--cwd", help="project directory (default: the current directory)")
    common.add_argument("--session", help="session id or unique prefix")
    common.add_argument("--file", help="read this transcript file instead of looking one up")
    common.add_argument("--tool", choices=("claude-code", "codex"), help="format of --file (default: detected)")
    common.add_argument("--current", action="append", help="id of the session you are in, so it is never chosen")
    common.add_argument("--claude-dir", default=os.environ.get("CLAUDE_CONFIG_DIR") or str(home / ".claude"))
    common.add_argument("--codex-dir", default=os.environ.get("CODEX_HOME") or str(home / ".codex"))
    common.add_argument("--days", type=int, default=45, help="how far back to look for Codex sessions first")
    common.add_argument("--no-redact", action="store_true", help="do not mask credentials")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", parents=[common], help="list sessions recorded for this project")
    listing.add_argument("--all", action="store_true", help="list sessions of every project")
    listing.add_argument("--limit", type=int, default=15)
    listing.add_argument("--detail", type=int, default=6, help="how many sessions to summarise")
    listing.set_defaults(run=cmd_list)
    digest = commands.add_parser("digest", parents=[common], help="print the digest of the previous session")
    digest.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="approximate total size in characters")
    digest.add_argument("--part", default="1", help="which part to print (default 1), or 'all' for everything at once")
    digest.add_argument("--part-size", type=int, default=PART_SIZE, help="largest size of one part in characters")
    digest.add_argument("--sessions", type=int, help="digest exactly this many of the most recent sessions")
    digest.set_defaults(run=cmd_digest)
    show = commands.add_parser("show", parents=[common], help="print events in full")
    show.add_argument("--event", action="append", required=True, help="event number or range such as 40-45")
    show.add_argument("--max-chars", type=int, default=6000, help="how much of each field to print")
    show.add_argument("--offset", type=int, default=0, help="skip this many characters of each field")
    show.set_defaults(run=cmd_show)
    search = commands.add_parser("search", parents=[common], help="find events matching a regular expression")
    search.add_argument("pattern")
    search.add_argument("--limit", type=int, default=40)
    search.set_defaults(run=cmd_search)
    return parser


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
    args = build_parser().parse_args(argv)
    args.argv = list(sys.argv[1:] if argv is None else argv)
    try:
        return args.run(args)
    except LookupError as error:
        print(str(error).strip("'\""), file=sys.stderr)
        return 2
    except re.error as error:
        print(f"Invalid regular expression: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
