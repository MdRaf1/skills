"""Tests for skills/continue-work/scripts/session_digest.py.

Every fixture is synthetic. Shapes follow transcripts written by Claude Code
2.1.x and Codex CLI 0.167; no real conversation content is used.

Run from the repository root:
    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "continue-work" / "scripts" / "session_digest.py"


def load_module():
    sys.dont_write_bytecode = True  # keep __pycache__ out of the packaged skill folder
    spec = importlib.util.spec_from_file_location("session_digest", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["session_digest"] = module
    spec.loader.exec_module(module)
    return module


sd = load_module()

PROJECT = "/work/proj"
_counter = [0]


def _id(prefix="id"):
    _counter[0] += 1
    return f"{prefix}-{_counter[0]:04d}"


def write_jsonl(path: Path, rows) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


# ---------------------------------------------------------------- Claude Code

def cc_base(ts, sid="cc-1", cwd=PROJECT):
    return {"uuid": _id("u"), "timestamp": ts, "sessionId": sid, "cwd": cwd,
            "isSidechain": False, "version": "2.1.322"}


def cc_user(text, ts, **extra):
    row = cc_base(ts, **{k: extra.pop(k) for k in ("sid", "cwd") if k in extra})
    row.update({"type": "user", "message": {"role": "user", "content": text}})
    row.update(extra)
    return row


def cc_text(text, ts, model="claude-test-1", **extra):
    row = cc_base(ts, **{k: extra.pop(k) for k in ("sid", "cwd") if k in extra})
    row.update({"type": "assistant", "message": {
        "role": "assistant", "model": model,
        "content": [{"type": "text", "text": text}]}})
    row.update(extra)
    return row


def cc_api_error(text, ts, status=502, **extra):
    return cc_text(text, ts, model="<synthetic>", isApiErrorMessage=True,
                   apiErrorStatus=status, error="unknown", **extra)


def cc_tool_use(name, tool_input, call_id, ts, **extra):
    row = cc_base(ts, **{k: extra.pop(k) for k in ("sid", "cwd") if k in extra})
    row.update({"type": "assistant", "message": {
        "role": "assistant", "model": "claude-test-1",
        "content": [{"type": "tool_use", "id": call_id, "name": name, "input": tool_input}]}})
    return row


def cc_tool_result(call_id, content, ts, is_error=False, **extra):
    row = cc_base(ts, **{k: extra.pop(k) for k in ("sid", "cwd") if k in extra})
    row.update({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": call_id, "content": content, "is_error": is_error}]}})
    return row


def cc_file(tmp: Path, rows, sid="cc-1", slug="-work-proj") -> Path:
    head = [{"type": "mode", "mode": "default", "sessionId": sid},
            {"type": "permission-mode", "permissionMode": "default", "sessionId": sid}]
    return write_jsonl(tmp / "claude" / "projects" / slug / f"{sid}.jsonl", head + rows)


# ---------------------------------------------------------------------- Codex

def cx_meta(sid, ts, cwd=PROJECT, **extra):
    payload = {"id": sid, "session_id": sid, "timestamp": ts, "cwd": cwd,
               "cli_version": "0.167.0", "source": "cli", "thread_source": "user",
               "base_instructions": "x" * 50}
    payload.update(extra)
    return {"timestamp": ts, "type": "session_meta", "payload": payload}


def cx_item(item, ts):
    return {"timestamp": ts, "type": "event_msg",
            "payload": {"type": "item_completed", "item": dict(item, id=_id("item"))}}


def cx_user(text, ts):
    return cx_item({"type": "UserMessage", "content": [{"type": "text", "text": text}]}, ts)


def cx_agent(text, ts, phase="final_answer"):
    return cx_item({"type": "AgentMessage", "phase": phase,
                    "content": [{"type": "Text", "text": text}]}, ts)


def cx_exec(command, output, ts, exit_code=0):
    return cx_item({"type": "CommandExecution", "command": ["/bin/bash", "-lc", command],
                    "aggregated_output": output, "exit_code": exit_code,
                    "status": "completed" if exit_code == 0 else "failed"}, ts)


def cx_file_change(path, ts, kind="add"):
    return cx_item({"type": "FileChange", "status": "completed",
                    "changes": {path: {"type": kind, "content": "data"}}}, ts)


def cx_event(kind, ts, **payload):
    return {"timestamp": ts, "type": "event_msg", "payload": dict(payload, type=kind)}


def cx_file(tmp: Path, name: str, rows, day="2026/01/02") -> Path:
    return write_jsonl(tmp / "codex" / "sessions" / day / f"rollout-{name}.jsonl", rows)


GATEWAY = ('{"error":{"message":"The requested item was created under a different '
           'Azure OpenAI resource."}}')


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.claude_dir = self.tmp / "claude"
        self.codex_dir = self.tmp / "codex"

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *argv, env=None):
        out, err = io.StringIO(), io.StringIO()
        args = list(argv) + ["--claude-dir", str(self.claude_dir), "--codex-dir", str(self.codex_dir)]
        saved = {k: os.environ.get(k) for k in ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")}
        for key in saved:
            os.environ.pop(key, None)
        os.environ.update(env or {})
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = sd.main(args)
        finally:
            for key, value in saved.items():
                os.environ.pop(key, None)
                if value is not None:
                    os.environ[key] = value
        return code, out.getvalue(), err.getvalue()


# ------------------------------------------------------------ parsing: Claude

class ClaudeParsingTests(TempDirCase):
    def test_real_prompts_are_kept_and_harness_noise_is_not(self):
        path = cc_file(self.tmp, [
            cc_user("<local-command-caveat>Caveat: ignore</local-command-caveat>", "2026-01-02T10:00:00Z", isMeta=True),
            cc_user("<command-name>/model</command-name>\n<command-message>model</command-message>\n<command-args></command-args>", "2026-01-02T10:00:01Z"),
            cc_user("<local-command-stdout>Set model</local-command-stdout>", "2026-01-02T10:00:02Z"),
            cc_user("Add retry logic to fetch.py", "2026-01-02T10:01:00Z"),
            cc_text("Done. Added three retries.", "2026-01-02T10:02:00Z"),
        ])
        session = sd.parse_session([path], "claude-code")
        prompts = [e.text for e in session.events if e.kind == "user"]
        self.assertEqual(prompts, ["Add retry logic to fetch.py"])
        self.assertEqual([e.name for e in session.events if e.kind == "command"], ["/model"])
        self.assertEqual(session.id, "cc-1")
        self.assertEqual(session.cwd, PROJECT)

    def test_skill_invocation_with_arguments_is_a_user_prompt(self):
        path = cc_file(self.tmp, [
            cc_user("<command-message>deploy-check</command-message>\n<command-name>/deploy-check</command-name>\n<command-args>staging only</command-args>", "2026-01-02T10:00:00Z"),
            cc_text("Checked staging.", "2026-01-02T10:01:00Z"),
        ])
        session = sd.parse_session([path], "claude-code")
        self.assertEqual([e.text for e in session.events if e.kind == "user"], ["/deploy-check staging only"])

    def test_tool_call_is_paired_with_its_result(self):
        path = cc_file(self.tmp, [
            cc_user("run the tests", "2026-01-02T10:00:00Z"),
            cc_tool_use("Bash", {"command": "pytest -q"}, "call-1", "2026-01-02T10:00:05Z"),
            cc_tool_result("call-1", "3 passed", "2026-01-02T10:00:09Z"),
            cc_tool_use("Bash", {"command": "false"}, "call-2", "2026-01-02T10:00:10Z"),
            cc_tool_result("call-2", [{"type": "text", "text": "exit 1"}], "2026-01-02T10:00:11Z", is_error=True),
        ])
        tools = [e for e in sd.parse_session([path], "claude-code").events if e.kind == "tool"]
        self.assertEqual([(t.name, t.result, t.ok) for t in tools],
                         [("Bash", "3 passed", True), ("Bash", "exit 1", False)])

    def test_compaction_summary_is_captured(self):
        path = cc_file(self.tmp, [
            cc_user("start the migration", "2026-01-02T10:00:00Z"),
            cc_text("Working on it.", "2026-01-02T10:01:00Z"),
            cc_user("This session is being continued. Summary: migrated 4 of 9 tables.", "2026-01-02T11:00:00Z", isCompactSummary=True),
            cc_text("Continuing with table 5.", "2026-01-02T11:01:00Z"),
        ])
        session = sd.parse_session([path], "claude-code")
        compactions = [e.text for e in session.events if e.kind == "compaction"]
        self.assertEqual(len(compactions), 1)
        self.assertIn("migrated 4 of 9 tables", compactions[0])
        self.assertEqual([e.text for e in session.events if e.kind == "user"], ["start the migration"])

    def test_recorded_reasoning_notes_are_kept_and_empty_ones_are_not(self):
        def thinking(text, ts):
            row = cc_base(ts)
            row.update({"type": "assistant", "message": {"role": "assistant", "model": "claude-test-1", "content": [
                {"type": "thinking", "thinking": text, "signature": "sig" * 40}]}})
            return row
        path = cc_file(self.tmp, [
            cc_user("upgrade the lockfile", "2026-01-02T10:00:00Z"),
            thinking("", "2026-01-02T10:00:01Z"),
            thinking("Prerequisites confirmed; cloning the repo next.", "2026-01-02T10:00:02Z"),
            cc_tool_use("Bash", {"command": "git clone x"}, "c1", "2026-01-02T10:00:03Z"),
        ])
        session = sd.parse_session([path], "claude-code")
        self.assertEqual([e.text for e in session.events if e.kind == "thinking"],
                         ["Prerequisites confirmed; cloning the repo next."])
        self.assertEqual(sd.analyze_ending(session)["state"], "in_flight")
        digest = sd.render_digest(session)
        report = digest.split("## What the agent reported", 1)[1].split("\n## ", 1)[0]
        self.assertIn("Prerequisites confirmed; cloning the repo next.", report)
        self.assertNotIn("sigsigsig", digest)

    def test_sidechain_and_bulk_records_are_ignored(self):
        path = cc_file(self.tmp, [
            cc_user("main prompt", "2026-01-02T10:00:00Z"),
            dict(cc_user("subagent prompt", "2026-01-02T10:00:01Z"), isSidechain=True),
            {"type": "attachment", "attachment": {"type": "skill_listing", "content": "x" * 5000}},
            {"type": "api-request-blob", "hash": "h", "message": {"big": "y" * 5000}},
            cc_text("main answer", "2026-01-02T10:00:02Z"),
        ])
        session = sd.parse_session([path], "claude-code")
        self.assertEqual([(e.kind, e.text) for e in session.events],
                         [("user", "main prompt"), ("assistant", "main answer")])

    def test_corrupt_lines_do_not_stop_parsing(self):
        path = cc_file(self.tmp, [cc_user("first", "2026-01-02T10:00:00Z")])
        with path.open("a", encoding="utf-8") as handle:
            handle.write('{"type": "user", "message": {"content": "trunc\n')
            handle.write(json.dumps(cc_text("after the bad line", "2026-01-02T10:00:05Z")) + "\n")
        session = sd.parse_session([path], "claude-code")
        self.assertEqual([e.text for e in session.events], ["first", "after the bad line"])


# ------------------------------------------------------------- parsing: Codex

class CodexParsingTests(TempDirCase):
    def test_items_become_prompts_answers_commands_and_file_changes(self):
        path = cx_file(self.tmp, "a", [
            cx_meta("cx-1", "2026-01-02T10:00:00Z"),
            cx_user("Build the report", "2026-01-02T10:00:01Z"),
            cx_agent("Reading inputs first.", "2026-01-02T10:00:02Z", phase="commentary"),
            cx_exec("ls state", "a.json\n", "2026-01-02T10:00:03Z"),
            cx_file_change("/work/proj/report.md", "2026-01-02T10:00:04Z"),
            cx_agent("Report written to report.md.", "2026-01-02T10:00:05Z"),
            cx_event("task_complete", "2026-01-02T10:00:06Z", last_agent_message="Report written to report.md."),
        ])
        session = sd.parse_session([path], "codex")
        self.assertEqual(session.id, "cx-1")
        self.assertEqual(session.cwd, PROJECT)
        self.assertEqual([(e.kind, e.text or e.name) for e in session.events], [
            ("user", "Build the report"),
            ("assistant", "Reading inputs first."),
            ("tool", "shell"),
            ("tool", "file_change"),
            ("assistant", "Report written to report.md."),
        ])
        shell = session.events[2]
        self.assertEqual((shell.input, shell.result.strip(), shell.ok), ("ls state", "a.json", True))
        self.assertEqual(session.events[3].meta["files"], ["/work/proj/report.md"])

    def test_failed_turn_records_the_gateway_error(self):
        path = cx_file(self.tmp, "a", [
            cx_meta("cx-1", "2026-01-02T10:00:00Z"),
            cx_user("continue", "2026-01-02T10:00:01Z"),
            cx_event("task_complete", "2026-01-02T10:00:02Z", last_agent_message=None,
                     error={"message": GATEWAY}),
        ])
        session = sd.parse_session([path], "codex")
        errors = [e.text for e in session.events if e.kind == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("different Azure OpenAI resource", errors[0])

    def test_compaction_message_and_abort_are_captured(self):
        path = cx_file(self.tmp, "a", [
            cx_meta("cx-1", "2026-01-02T10:00:00Z"),
            cx_user("long task", "2026-01-02T10:00:01Z"),
            {"timestamp": "2026-01-02T10:30:00Z", "type": "compacted",
             "payload": {"message": "Summary so far: 12 files converted.", "replacement_history": []}},
            cx_event("turn_aborted", "2026-01-02T10:31:00Z", reason="interrupted"),
        ])
        kinds = {e.kind: e.text for e in sd.parse_session([path], "codex").events}
        self.assertIn("12 files converted", kinds["compaction"])
        self.assertIn("abort", kinds)

    def test_unfinished_function_call_is_kept_as_a_pending_tool(self):
        path = cx_file(self.tmp, "a", [
            cx_meta("cx-1", "2026-01-02T10:00:00Z"),
            cx_user("push it", "2026-01-02T10:00:01Z"),
            {"timestamp": "2026-01-02T10:00:02Z", "type": "response_item", "payload": {
                "type": "custom_tool_call", "name": "exec", "call_id": "c1",
                "input": "tools.exec_command({cmd:'git push origin main'})"}},
        ])
        tools = [e for e in sd.parse_session([path], "codex").events if e.kind == "tool"]
        self.assertEqual(len(tools), 1)
        self.assertIsNone(tools[0].result)
        self.assertIn("git push origin main", tools[0].input)

    def test_finished_exec_wrapper_is_not_duplicated_next_to_its_commands(self):
        path = cx_file(self.tmp, "a", [
            cx_meta("cx-1", "2026-01-02T10:00:00Z"),
            cx_user("check", "2026-01-02T10:00:01Z"),
            {"timestamp": "2026-01-02T10:00:02Z", "type": "response_item", "payload": {
                "type": "custom_tool_call", "name": "exec", "call_id": "c1", "input": "tools.exec_command({cmd:'pwd'})"}},
            cx_exec("pwd", "/work/proj\n", "2026-01-02T10:00:03Z"),
            {"timestamp": "2026-01-02T10:00:04Z", "type": "response_item", "payload": {
                "type": "custom_tool_call_output", "call_id": "c1",
                "output": [{"type": "input_text", "text": "Script completed"}]}},
        ])
        tools = [e for e in sd.parse_session([path], "codex").events if e.kind == "tool"]
        self.assertEqual([(t.name, t.input) for t in tools], [("shell", "pwd")])

    def test_inter_agent_envelope_is_reduced_to_its_payload(self):
        path = cx_file(self.tmp, "a", [
            cx_meta("cx-1", "2026-01-02T10:00:00Z"),
            cx_user("go", "2026-01-02T10:00:01Z"),
            {"timestamp": "2026-01-02T10:00:02Z", "type": "response_item", "payload": {
                "type": "agent_message", "author": "/root/impl", "recipient": "/root", "content": [
                    {"type": "input_text", "text": "Message Type: FINAL_ANSWER\nTask name: /root\nSender: /root/impl\nPayload:\nAll ten verifier groups pass."},
                    {"type": "encrypted_content", "encrypted_content": "gAAAAAxyz"}]}},
        ])
        workers = [e for e in sd.parse_session([path], "codex").events if e.kind == "worker"]
        self.assertEqual(len(workers), 1)
        self.assertIn("All ten verifier groups pass.", workers[0].text)
        self.assertNotIn("Message Type", workers[0].text)
        self.assertEqual(workers[0].name, "/root/impl")

    def test_legacy_rollout_without_items_still_yields_the_conversation(self):
        path = cx_file(self.tmp, "a", [
            cx_meta("cx-old", "2026-01-02T10:00:00Z"),
            cx_event("user_message", "2026-01-02T10:00:01Z", message="fix the parser"),
            {"timestamp": "2026-01-02T10:00:02Z", "type": "response_item", "payload": {
                "type": "function_call", "name": "shell", "call_id": "c1",
                "arguments": json.dumps({"command": ["bash", "-lc", "make test"]})}},
            {"timestamp": "2026-01-02T10:00:03Z", "type": "response_item", "payload": {
                "type": "function_call_output", "call_id": "c1", "output": "ok"}},
            cx_event("agent_message", "2026-01-02T10:00:04Z", message="Parser fixed."),
        ])
        session = sd.parse_session([path], "codex")
        self.assertEqual([(e.kind, e.text or e.name) for e in session.events],
                         [("user", "fix the parser"), ("tool", "shell"), ("assistant", "Parser fixed.")])
        self.assertEqual(session.events[1].result, "ok")


# ------------------------------------------------------- turns and the ending

class EndingTests(TempDirCase):
    def ending(self, rows, tool="claude-code"):
        path = cc_file(self.tmp, rows) if tool == "claude-code" else cx_file(self.tmp, "a", rows)
        return sd.analyze_ending(sd.parse_session([path], tool))

    def test_answered_last_prompt_is_a_clean_ending(self):
        ending = self.ending([
            cc_user("rename the module", "2026-01-02T10:00:00Z"),
            cc_text("Renamed.", "2026-01-02T10:01:00Z"),
        ])
        self.assertEqual(ending["state"], "clean")
        self.assertEqual(ending["unanswered"], [])
        self.assertEqual(ending["in_flight"], [])

    def test_retries_that_only_hit_api_errors_collapse_into_one_unanswered_prompt(self):
        rows = [cc_user("first task", "2026-01-02T09:00:00Z"), cc_text("First task done.", "2026-01-02T09:05:00Z")]
        for minute, text in enumerate(["Now add the exporter and tests",
                                       "Now add the exporter and tests",
                                       "Now add the exporter, and tests"]):
            rows.append(cc_user(text, f"2026-01-02T10:0{minute}:00Z"))
            rows.append(cc_api_error("API Error: 502 Bad Gateway", f"2026-01-02T10:0{minute}:01Z"))
        ending = self.ending(rows)
        self.assertEqual(ending["state"], "unanswered")
        self.assertEqual(len(ending["unanswered"]), 1)
        self.assertEqual(ending["unanswered"][0]["attempts"], 3)
        self.assertEqual(ending["unanswered"][0]["text"], "Now add the exporter, and tests")
        self.assertIn("502", ending["unanswered"][0]["error"])
        self.assertEqual(ending["last_worked_turn"], 1)

    def test_error_after_real_work_is_a_failed_ending(self):
        ending = self.ending([
            cc_user("refactor billing", "2026-01-02T10:00:00Z"),
            cc_tool_use("Edit", {"file_path": "/work/proj/billing.py", "old_string": "a", "new_string": "b"}, "c1", "2026-01-02T10:00:05Z"),
            cc_tool_result("c1", "ok", "2026-01-02T10:00:06Z"),
            cc_api_error("API Error: 400 invalid signature in thinking block", "2026-01-02T10:00:07Z", status=400),
        ])
        self.assertEqual(ending["state"], "failed")
        self.assertEqual(ending["last_worked_turn"], 1)
        self.assertIn("invalid signature", ending["errors"][-1])

    def test_tool_call_without_result_is_in_flight(self):
        ending = self.ending([
            cc_user("deploy", "2026-01-02T10:00:00Z"),
            cc_tool_use("Bash", {"command": "git push origin main"}, "c1", "2026-01-02T10:00:05Z"),
        ])
        self.assertEqual(ending["state"], "in_flight")
        self.assertEqual([e.name for e in ending["in_flight"]], ["Bash"])

    def test_tool_result_without_a_reply_is_cut_off(self):
        ending = self.ending([
            cc_user("investigate", "2026-01-02T10:00:00Z"),
            cc_tool_use("Bash", {"command": "ls"}, "c1", "2026-01-02T10:00:05Z"),
            cc_tool_result("c1", "a b c", "2026-01-02T10:00:06Z"),
        ])
        self.assertEqual(ending["state"], "cut_off")

    def test_user_interrupt_is_reported(self):
        ending = self.ending([
            cc_user("long job", "2026-01-02T10:00:00Z"),
            cc_tool_use("Bash", {"command": "sleep 600"}, "c1", "2026-01-02T10:00:05Z"),
            cc_tool_result("c1", "interrupted", "2026-01-02T10:00:30Z", is_error=True),
            cc_user([{"type": "text", "text": "[Request interrupted by user for tool use]"}], "2026-01-02T10:00:31Z"),
        ])
        self.assertEqual(ending["state"], "interrupted")

    def test_codex_gateway_failure_after_work_is_failed(self):
        ending = self.ending([
            cx_meta("cx-1", "2026-01-02T10:00:00Z"),
            cx_user("implement the plan", "2026-01-02T10:00:01Z"),
            cx_exec("ls", "x", "2026-01-02T10:00:02Z"),
            cx_event("task_complete", "2026-01-02T10:00:03Z", last_agent_message=None, error={"message": GATEWAY}),
            cx_user("The error was the gateway. Continue.", "2026-01-02T10:01:00Z"),
            cx_event("task_complete", "2026-01-02T10:01:01Z", last_agent_message=None, error={"message": GATEWAY}),
        ], tool="codex")
        self.assertEqual(ending["state"], "unanswered")
        self.assertEqual(ending["last_worked_turn"], 1)
        self.assertEqual(ending["unanswered"][0]["text"], "The error was the gateway. Continue.")

    def test_queued_prompt_that_was_never_sent_is_reported(self):
        ending = self.ending([
            cc_user("first", "2026-01-02T10:00:00Z"),
            {"type": "queue-operation", "operation": "enqueue", "content": "also update the changelog",
             "timestamp": "2026-01-02T10:00:10Z", "sessionId": "cc-1"},
            cc_api_error("API Error: 502", "2026-01-02T10:00:20Z"),
        ])
        self.assertEqual(ending["queued_undelivered"], ["also update the changelog"])


# ------------------------------------------------------------------ discovery

class DiscoveryTests(TempDirCase):
    def test_only_sessions_started_in_this_project_are_listed(self):
        cc_file(self.tmp, [cc_user("mine", "2026-01-02T10:00:00Z")], sid="cc-mine")
        cc_file(self.tmp, [cc_user("other", "2026-01-02T10:00:00Z", sid="cc-other", cwd="/work/other")],
                sid="cc-other", slug="-work-other")
        cx_file(self.tmp, "a", [cx_meta("cx-mine", "2026-01-02T09:00:00Z"), cx_user("mine", "2026-01-02T09:00:01Z")])
        cx_file(self.tmp, "b", [cx_meta("cx-other", "2026-01-02T09:00:00Z", cwd="/elsewhere"), cx_user("x", "2026-01-02T09:00:01Z")])
        refs = sd.discover(PROJECT, self.claude_dir, self.codex_dir)
        self.assertEqual(sorted(r.id for r in refs), ["cc-mine", "cx-mine"])

    def test_claude_project_folder_is_found_even_when_its_name_is_unexpected(self):
        cc_file(self.tmp, [cc_user("mine", "2026-01-02T10:00:00Z", sid="cc-odd")], sid="cc-odd", slug="hashed-folder-name")
        refs = sd.discover(PROJECT, self.claude_dir, self.codex_dir)
        self.assertEqual([r.id for r in refs], ["cc-odd"])

    def test_codex_rollouts_sharing_an_id_are_one_session_in_time_order(self):
        cx_file(self.tmp, "2026-01-02T12-00-00-cx-1", [
            cx_meta("cx-1", "2026-01-02T12:00:00Z"), cx_user("second part", "2026-01-02T12:00:01Z")])
        cx_file(self.tmp, "2026-01-02T10-00-00-cx-1", [
            cx_meta("cx-1", "2026-01-02T10:00:00Z"), cx_user("first part", "2026-01-02T10:00:01Z")])
        refs = sd.discover(PROJECT, self.claude_dir, self.codex_dir)
        self.assertEqual(len(refs), 1)
        session = sd.parse_session(refs[0].paths, refs[0].tool)
        self.assertEqual([e.text for e in session.events if e.kind == "user"], ["first part", "second part"])

    def test_codex_subagent_threads_attach_to_their_parent(self):
        cx_file(self.tmp, "root", [cx_meta("cx-root", "2026-01-02T10:00:00Z"), cx_user("go", "2026-01-02T10:00:01Z")])
        cx_file(self.tmp, "child", [
            cx_meta("cx-child", "2026-01-02T10:05:00Z", thread_source="subagent",
                    source={"subagent": {"thread_spawn": {"parent_thread_id": "cx-root", "agent_path": "/root/research"}}}),
            cx_agent("Agent errored", "2026-01-02T10:06:00Z")])
        refs = sd.discover(PROJECT, self.claude_dir, self.codex_dir)
        self.assertEqual([r.id for r in refs], ["cx-root"])
        self.assertEqual([(c.id, c.label) for c in refs[0].children], [("cx-child", "/root/research")])

    def test_previous_session_is_the_newest_one_that_is_not_current(self):
        old = cc_file(self.tmp, [cc_user("old", "2026-01-01T10:00:00Z", sid="cc-old")], sid="cc-old")
        dead = cc_file(self.tmp, [cc_user("dead", "2026-01-02T10:00:00Z", sid="cc-dead")], sid="cc-dead")
        live = cc_file(self.tmp, [cc_user("/continue-work", "2026-01-02T11:00:00Z", sid="cc-live")], sid="cc-live")
        for seconds, path in ((1000, old), (2000, dead), (3000, live)):
            os.utime(path, (seconds, seconds))
        refs = sd.discover(PROJECT, self.claude_dir, self.codex_dir)
        self.assertEqual([r.id for r in refs], ["cc-live", "cc-dead", "cc-old"])
        self.assertEqual(sd.pick_previous(refs, {"cc-live"}).id, "cc-dead")

    def test_sessions_without_any_conversation_are_not_candidates(self):
        dead = cc_file(self.tmp, [cc_user("real work", "2026-01-02T10:00:00Z", sid="cc-dead")], sid="cc-dead")
        setup = cc_file(self.tmp, [
            cc_user("<command-name>/mcp</command-name>\n<command-args></command-args>", "2026-01-02T11:00:00Z", sid="cc-setup")],
            sid="cc-setup")
        os.utime(dead, (2000, 2000))
        os.utime(setup, (3000, 3000))
        refs = sd.discover(PROJECT, self.claude_dir, self.codex_dir)
        self.assertEqual(sd.pick_previous(refs, set()).id, "cc-dead")


# --------------------------------------------------------------------- digest

class DigestTests(TempDirCase):
    def session(self, rows):
        return sd.parse_session([cc_file(self.tmp, rows)], "claude-code")

    def test_every_user_prompt_appears_verbatim(self):
        digest = sd.render_digest(self.session([
            cc_user("Use tabs, never spaces, in this repo.", "2026-01-02T10:00:00Z"),
            cc_text("Understood.", "2026-01-02T10:00:10Z"),
            cc_user("Now port utils.py to the new API.", "2026-01-02T10:01:00Z"),
            cc_text("Ported.", "2026-01-02T10:02:00Z"),
        ]))
        self.assertIn("Use tabs, never spaces, in this repo.", digest)
        self.assertIn("Now port utils.py to the new API.", digest)
        self.assertIn("Ported.", digest)

    def test_digest_names_files_changed_and_commands_run(self):
        digest = sd.render_digest(self.session([
            cc_user("fix it", "2026-01-02T10:00:00Z"),
            cc_tool_use("Edit", {"file_path": "/work/proj/src/app.py", "old_string": "a", "new_string": "b"}, "c1", "2026-01-02T10:00:01Z"),
            cc_tool_result("c1", "ok", "2026-01-02T10:00:02Z"),
            cc_tool_use("Bash", {"command": "pytest tests/test_app.py"}, "c2", "2026-01-02T10:00:03Z"),
            cc_tool_result("c2", "1 failed", "2026-01-02T10:00:04Z", is_error=True),
        ]))
        self.assertIn("/work/proj/src/app.py", digest)
        self.assertIn("pytest tests/test_app.py", digest)

    def test_outward_facing_commands_are_flagged_with_their_outcome(self):
        digest = sd.render_digest(self.session([
            cc_user("ship it", "2026-01-02T10:00:00Z"),
            cc_tool_use("Bash", {"command": "git push origin main"}, "c1", "2026-01-02T10:00:01Z"),
        ]))
        section = digest.split("## Verify before repeating", 1)[1].split("\n## ", 1)[0]
        self.assertIn("git push origin main", section)
        self.assertIn("NO RESULT RECORDED", section)

    def test_markdown_inside_a_prompt_cannot_break_the_digest_outline(self):
        digest = sd.render_digest(self.session([
            cc_user("# My directive\n## Part one\n---\ndo the thing", "2026-01-02T10:00:00Z"),
            cc_text("## Result\nDone.", "2026-01-02T10:00:10Z"),
        ]))
        lines = digest.splitlines()
        self.assertNotIn("# My directive", lines)
        self.assertNotIn("## Part one", lines)
        self.assertNotIn("## Result", lines)
        self.assertIn("> # My directive", lines)
        self.assertIn("> do the thing", lines)

    def test_files_written_by_shell_redirection_are_listed(self):
        digest = sd.render_digest(self.session([
            cc_user("write notes", "2026-01-02T10:00:00Z"),
            cc_tool_use("Bash", {"command": "cat > notes/plan.md <<'EOF'\nhello\nEOF\necho done >> logs/run.log 2>/dev/null"}, "c1", "2026-01-02T10:00:01Z"),
            cc_tool_result("c1", "", "2026-01-02T10:00:02Z"),
        ]))
        ledger = digest.split("## Work ledger", 1)[1].split("\n## ", 1)[0]
        self.assertRegex(ledger, r"(?m)^- notes/plan\.md \(")
        self.assertRegex(ledger, r"(?m)^- logs/run\.log \(")
        self.assertNotRegex(ledger, r"(?m)^- /dev/null")

    def test_worker_that_reports_after_the_session_stopped_is_called_out(self):
        path = cx_file(self.tmp, "a", [
            cx_meta("cx-1", "2026-01-02T10:00:00Z"),
            cx_user("implement the adapters", "2026-01-02T10:00:01Z"),
            cx_item({"type": "SubAgentActivity", "kind": "started", "agent_path": "/root/impl", "agent_thread_id": "t1"}, "2026-01-02T10:00:02Z"),
            cx_event("task_complete", "2026-01-02T10:00:03Z", last_agent_message=None, error={"message": GATEWAY}),
            cx_item({"type": "SubAgentActivity", "kind": "completed", "agent_path": "/root/impl", "agent_thread_id": "t1"}, "2026-01-02T10:20:00Z"),
        ])
        digest = sd.render_digest(sd.parse_session([path], "codex"))
        ending = digest.split("## How the session ended", 1)[1].split("\n## ", 1)[0]
        self.assertIn("/root/impl", ending)
        self.assertIn("after the session stopped", ending)

    def test_read_only_lookalikes_are_not_flagged_but_real_writes_are(self):
        def verify_section(*commands):
            rows = [cc_user("go", "2026-01-02T10:00:00Z")]
            for n, command in enumerate(commands):
                rows.append(cc_tool_use("Bash", {"command": command}, f"c{n}", "2026-01-02T10:00:01Z"))
                rows.append(cc_tool_result(f"c{n}", "ok", "2026-01-02T10:00:02Z"))
            digest = sd.render_digest(self.session(rows))
            return digest.split("## Verify before repeating", 1)[1].split("\n## ", 1)[0]
        harmless = verify_section("curl -sS -D - -o out.json https://api.example.com/user",
                                  "git tag -l; git remote -v", "git tag", "git log --oneline | head")
        self.assertIn("No pushes", harmless)
        data_only = verify_section("python3 - <<'EOF'\nprint('git push origin main')\nEOF")
        self.assertIn("No pushes", data_only)
        piped_to_shell = verify_section("bash <<'EOF'\ngit push origin main\nEOF")
        self.assertIn("git push origin main", piped_to_shell)
        risky = verify_section("curl -sS -X POST https://api.example.com/repos -d '{}'",
                               "git tag v1.2.0", "git -C sub push origin main")
        for fragment in ("-X POST", "git tag v1.2.0", "git -C sub push origin main"):
            self.assertIn(fragment, risky)

    def test_no_line_is_too_long_for_a_file_reader_and_wrapping_loses_no_words(self):
        prompt = " ".join(f"word{n}" for n in range(1500))  # one line of about 11,000 characters
        digest = sd.render_digest(self.session([
            cc_user(prompt, "2026-01-02T10:00:00Z"),
            cc_tool_use("Bash", {"command": "echo " + "x" * 5000}, "c1", "2026-01-02T10:00:01Z"),
            cc_tool_result("c1", "r" * 5000, "2026-01-02T10:00:02Z"),
            cc_text("Done. " + "sentence here. " * 400, "2026-01-02T10:00:03Z"),
        ]))
        self.assertLessEqual(max(len(line) for line in digest.splitlines()), 1600)
        section = digest.split("## User prompts", 1)[1].split("\n## ", 1)[0]
        quoted = " ".join(line.lstrip("> ") for line in section.splitlines() if line.startswith(">"))
        self.assertIn(prompt, " ".join(quoted.split()))

    def test_last_todo_list_is_shown(self):
        digest = sd.render_digest(self.session([
            cc_user("plan and do", "2026-01-02T10:00:00Z"),
            cc_tool_use("TodoWrite", {"todos": [
                {"content": "Write parser", "status": "completed"},
                {"content": "Wire CLI", "status": "in_progress"},
                {"content": "Docs", "status": "pending"}]}, "c1", "2026-01-02T10:00:01Z"),
            cc_tool_result("c1", "ok", "2026-01-02T10:00:02Z"),
        ]))
        self.assertIn("Wire CLI", digest)
        self.assertIn("in_progress", digest)

    def test_long_session_stays_within_budget_and_keeps_both_ends(self):
        rows = [cc_user("FIRST-PROMPT set up the project", "2026-01-02T08:00:00Z")]
        for n in range(400):
            rows.append(cc_tool_use("Bash", {"command": f"echo step {n} " + "x" * 300}, f"c{n}", "2026-01-02T09:00:00Z"))
            rows.append(cc_tool_result(f"c{n}", "y" * 3000, "2026-01-02T09:00:01Z"))
            rows.append(cc_text(f"progress note {n} " + "z" * 500, "2026-01-02T09:00:02Z"))
        rows.append(cc_user("LAST-PROMPT finish the changelog", "2026-01-02T12:00:00Z"))
        rows.append(cc_api_error("API Error: 502 Bad Gateway", "2026-01-02T12:00:01Z"))
        digest = sd.render_digest(self.session(rows), budget=30000)
        self.assertLessEqual(len(digest), 33000)
        self.assertIn("FIRST-PROMPT set up the project", digest)
        self.assertIn("LAST-PROMPT finish the changelog", digest)
        self.assertIn("progress note 399", digest)
        self.assertIn("502 Bad Gateway", digest)

    def test_oversized_prompt_is_shortened_with_a_pointer_to_the_full_text(self):
        huge = "HEAD-MARK " + "p" * 60000 + " TAIL-MARK"
        digest = sd.render_digest(self.session([
            cc_user(huge, "2026-01-02T10:00:00Z"),
            cc_text("ok", "2026-01-02T10:00:10Z"),
        ]), budget=20000)
        self.assertIn("HEAD-MARK", digest)
        self.assertIn("TAIL-MARK", digest)
        self.assertRegex(digest, r"show --event \d+")
        self.assertLessEqual(len(digest), 22000)

    def test_secrets_are_masked_by_default(self):
        rows = [
            cc_user("my key is sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789 keep it safe", "2026-01-02T10:00:00Z"),
            cc_tool_use("Bash", {"command": "export PRIVATE_KEY=5JabcDEFghiJKLmnoPQRstuVWXyz1234567890abcdEFGH && echo ghp_abcdefghijklmnopqrstuvwxyz0123456789"}, "c1", "2026-01-02T10:00:01Z"),
            cc_tool_result("c1", "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcDEF123456", "2026-01-02T10:00:02Z"),
        ]
        digest = sd.render_digest(self.session(rows))
        for secret in ("AbCdEfGhIjKlMnOpQrStUvWxYz0123456789", "5JabcDEFghiJKLmnoPQRstuVWXyz1234567890abcdEFGH",
                       "ghp_abcdefghijklmnopqrstuvwxyz0123456789", "eyJzdWIiOiIxMjM0NTY3ODkwIn0"):
            self.assertNotIn(secret, digest)
        self.assertIn("[REDACTED", digest)
        self.assertIn("keep it safe", digest)

    def test_ending_section_tells_the_reader_what_was_left_unanswered(self):
        digest = sd.render_digest(self.session([
            cc_user("do A", "2026-01-02T10:00:00Z"),
            cc_text("A is done.", "2026-01-02T10:01:00Z"),
            cc_user("now do B", "2026-01-02T10:02:00Z"),
            cc_api_error("API Error: 502 Bad Gateway", "2026-01-02T10:02:01Z"),
        ]))
        ending = digest.split("## How the session ended", 1)[1].split("\n## ", 1)[0]
        self.assertIn("now do B", ending)
        self.assertIn("502 Bad Gateway", ending)
        self.assertIn("never answered", ending)


# ------------------------------------------------------------------------ CLI

class CliTests(TempDirCase):
    def seed(self):
        dead = cc_file(self.tmp, [
            cc_user("Build the importer", "2026-01-02T10:00:00Z", sid="cc-dead"),
            cc_tool_use("Bash", {"command": "echo " + "q" * 5000 + " END-OF-COMMAND"}, "c1", "2026-01-02T10:00:01Z"),
            cc_tool_result("c1", "ok", "2026-01-02T10:00:02Z"),
            cc_api_error("API Error: 502 Bad Gateway", "2026-01-02T10:00:03Z"),
        ], sid="cc-dead")
        live = cc_file(self.tmp, [cc_user("/continue-work", "2026-01-02T11:00:00Z", sid="cc-live")], sid="cc-live")
        os.utime(dead, (2000, 2000))
        os.utime(live, (3000, 3000))

    def test_digest_defaults_to_the_previous_session_not_the_current_one(self):
        self.seed()
        code, out, _ = self.run_cli("digest", "--cwd", PROJECT, env={"CLAUDE_CODE_SESSION_ID": "cc-live"})
        self.assertEqual(code, 0)
        self.assertIn("cc-dead", out)
        self.assertIn("Build the importer", out)

    def test_newer_session_that_only_holds_an_unanswered_prompt_is_skipped_but_reported(self):
        worked = cc_file(self.tmp, [
            cc_user("Build the importer", "2026-01-02T10:00:00Z", sid="cc-worked"),
            cc_tool_use("Bash", {"command": "ls"}, "c1", "2026-01-02T10:00:01Z"),
            cc_tool_result("c1", "ok", "2026-01-02T10:00:02Z"),
            cc_text("Importer half done.", "2026-01-02T10:00:03Z"),
            cc_api_error("API Error: 502 Bad Gateway", "2026-01-02T10:00:04Z"),
        ], sid="cc-worked")
        stub = cc_file(self.tmp, [
            cc_user("carry on with the importer and add CSV support", "2026-01-02T10:30:00Z", sid="cc-stub"),
            cc_api_error("API Error: 502 Bad Gateway", "2026-01-02T10:30:01Z"),
        ], sid="cc-stub")
        live = cc_file(self.tmp, [cc_user("/continue-work", "2026-01-02T11:00:00Z", sid="cc-live")], sid="cc-live")
        for seconds, path in ((2000, worked), (2500, stub), (3000, live)):
            os.utime(path, (seconds, seconds))
        code, out, _ = self.run_cli("digest", "--cwd", PROJECT, env={"CLAUDE_CODE_SESSION_ID": "cc-live"})
        self.assertEqual(code, 0)
        self.assertIn("Importer half done.", out)
        self.assertIn("cc-stub", out)
        self.assertIn("carry on with the importer and add CSV support", out)

    def test_without_a_known_session_id_the_session_that_invoked_the_skill_is_not_recovered(self):
        import time
        dead = cc_file(self.tmp, [
            cc_user("Build the importer", "2026-01-02T10:00:00Z", sid="cc-dead"),
            cc_text("Importer half done.", "2026-01-02T10:00:03Z"),
        ], sid="cc-dead")
        live = cc_file(self.tmp, [
            cc_user("$continue-work pick up the importer", "2026-01-02T11:00:00Z", sid="cc-live"),
            cc_tool_use("Bash", {"command": "ls"}, "c1", "2026-01-02T11:00:01Z"),
            cc_tool_result("c1", "ok", "2026-01-02T11:00:02Z"),
        ], sid="cc-live")
        now = time.time()
        os.utime(dead, (now - 600, now - 600))
        os.utime(live, (now - 2, now - 2))
        code, out, _ = self.run_cli("digest", "--cwd", PROJECT)
        self.assertEqual(code, 0)
        self.assertIn("Importer half done.", out)
        self.assertIn("# Session digest: claude-code cc-dead", out)
        self.assertNotIn("# Session digest: claude-code cc-live", out)
        self.assertIn("cc-live was taken to be the conversation you are in now", out)

    def big_session(self, sid, prompt, marker, seconds, start="2026-01-02T08:00:00Z"):
        rows = [cc_user(prompt, start, sid=sid)]
        for n in range(20):
            rows.append(cc_tool_use("Bash", {"command": f"step {n}"}, f"{sid}-c{n}", start, sid=sid))
            rows.append(cc_tool_result(f"{sid}-c{n}", "ok", start, sid=sid))
            rows.append(cc_text(f"{marker} note {n}", start, sid=sid))
        rows.append(cc_api_error("API Error: 502 Bad Gateway", start, sid=sid))
        path = cc_file(self.tmp, rows, sid=sid)
        os.utime(path, (seconds, seconds))
        return path

    def test_short_follow_up_attempts_are_digested_together_with_the_last_substantial_session(self):
        self.big_session("cc-big", "Implement the importer end to end", "BIG-WORK", 2000)
        attempt = cc_file(self.tmp, [
            cc_user("/continue-work the gateway died, keep going", "2026-01-02T10:30:00Z", sid="cc-attempt"),
            cc_tool_use("Bash", {"command": "git status"}, "a1", "2026-01-02T10:30:01Z", sid="cc-attempt"),
            cc_tool_result("a1", "clean", "2026-01-02T10:30:02Z", sid="cc-attempt"),
            cc_api_error("API Error: 502 Bad Gateway", "2026-01-02T10:30:03Z", sid="cc-attempt"),
        ], sid="cc-attempt")
        live = cc_file(self.tmp, [cc_user("/continue-work", "2026-01-02T11:00:00Z", sid="cc-live")], sid="cc-live")
        os.utime(attempt, (2500, 2500))
        os.utime(live, (3000, 3000))
        code, out, _ = self.run_cli("digest", "--cwd", PROJECT, env={"CLAUDE_CODE_SESSION_ID": "cc-live"})
        self.assertEqual(code, 0)
        self.assertIn("2 sessions", out)
        self.assertIn("Implement the importer end to end", out)
        self.assertIn("BIG-WORK note 19", out)
        self.assertIn("the gateway died, keep going", out)
        self.assertLess(out.index("# Session digest: claude-code cc-big"),
                        out.index("# Session digest: claude-code cc-attempt"))

    def test_substantial_latest_session_is_digested_alone_and_older_ones_are_only_indexed(self):
        self.big_session("cc-older", "Design the schema", "OLDER-WORK", 1000, start="2026-01-01T08:00:00Z")
        self.big_session("cc-newer", "Implement the importer end to end", "NEWER-WORK", 2000)
        code, out, _ = self.run_cli("digest", "--cwd", PROJECT)
        self.assertEqual(code, 0)
        self.assertIn("NEWER-WORK note 19", out)
        self.assertNotIn("OLDER-WORK", out)
        index = out.split("## Earlier sessions in this project", 1)[1]
        self.assertIn("cc-older", index)
        self.assertIn("Design the schema", index)

    def test_number_of_sessions_can_be_forced(self):
        self.big_session("cc-older", "Design the schema", "OLDER-WORK", 1000, start="2026-01-01T08:00:00Z")
        self.big_session("cc-newer", "Implement the importer end to end", "NEWER-WORK", 2000)
        code, out, _ = self.run_cli("digest", "--cwd", PROJECT, "--sessions", "2")
        self.assertEqual(code, 0)
        self.assertIn("OLDER-WORK note 19", out)
        self.assertIn("NEWER-WORK note 19", out)

    def test_digest_of_several_sessions_states_that_credentials_were_masked(self):
        self.big_session("cc-big", "Implement the importer end to end", "BIG-WORK", 2000)
        attempt = cc_file(self.tmp, [
            cc_user("keep going, token=abcdefghijklmnop123", "2026-01-02T10:30:00Z", sid="cc-attempt"),
            cc_api_error("API Error: 502 Bad Gateway", "2026-01-02T10:30:03Z", sid="cc-attempt"),
        ], sid="cc-attempt")
        os.utime(attempt, (2500, 2500))
        code, out, _ = self.run_cli("digest", "--cwd", PROJECT)
        self.assertEqual(code, 0)
        self.assertIn("2 sessions", out)
        self.assertNotIn("abcdefghijklmnop123", out)
        self.assertNotIn("best-effort basis: no", out)

    def long_session(self):
        rows = [cc_user("FIRST-PROMPT set up the project", "2026-01-02T08:00:00Z", sid="cc-long")]
        for n in range(300):
            rows.append(cc_tool_use("Bash", {"command": f"echo step {n} " + "x" * 200}, f"c{n}", "2026-01-02T09:00:00Z", sid="cc-long"))
            rows.append(cc_tool_result(f"c{n}", "y" * 2000, "2026-01-02T09:00:01Z", sid="cc-long"))
            rows.append(cc_text(f"progress note {n} " + "z" * 600, "2026-01-02T09:00:02Z", sid="cc-long"))
        rows.append(cc_user("LAST-PROMPT finish the changelog", "2026-01-02T12:00:00Z", sid="cc-long"))
        rows.append(cc_api_error("API Error: 502 Bad Gateway", "2026-01-02T12:00:01Z", sid="cc-long"))
        cc_file(self.tmp, rows, sid="cc-long")

    def test_long_digest_arrives_in_parts_that_each_fit_a_tool_result(self):
        self.long_session()
        code, first, _ = self.run_cli("digest", "--cwd", PROJECT, "--budget", "60000", "--part-size", "20000")
        self.assertEqual(code, 0)
        self.assertLessEqual(len(first), 20000)
        total = int(re.search(r"part 1 of (\d+)", first).group(1))
        self.assertGreaterEqual(total, 3)
        self.assertIn("FIRST-PROMPT set up the project", first)
        self.assertRegex(first.strip().splitlines()[-1], r"digest .*--part 2")
        self.assertNotIn("[End of digest]", first)
        bodies = [first]
        for number in range(2, total + 1):
            code, part, _ = self.run_cli("digest", "--cwd", PROJECT, "--budget", "60000", "--part-size", "20000",
                                         "--part", str(number))
            self.assertEqual(code, 0)
            self.assertLessEqual(len(part), 20000)
            self.assertIn(f"part {number} of {total}", part)
            bodies.append(part)
        self.assertEqual(bodies[-1].strip().splitlines()[-1], "[End of digest]")
        self.assertIn("progress note 299", bodies[-1])
        code, whole, _ = self.run_cli("digest", "--cwd", PROJECT, "--budget", "60000", "--part", "all")
        self.assertEqual(code, 0)
        self.assertNotRegex(whole, r"part \d+ of \d+")
        self.assertEqual(whole.strip().splitlines()[-1], "[End of digest]")
        for line in whole.splitlines()[:-1]:
            self.assertTrue(any(line in body for body in bodies), line[:80])

    def test_short_digest_is_one_part_and_says_where_it_ends(self):
        self.seed()
        code, out, _ = self.run_cli("digest", "--cwd", PROJECT, "--session", "cc-dead")
        self.assertEqual(code, 0)
        self.assertNotRegex(out, r"part \d+ of \d+")
        self.assertEqual(out.strip().splitlines()[-1], "[End of digest]")

    def test_asking_for_a_part_that_does_not_exist_is_an_error(self):
        self.seed()
        code, out, err = self.run_cli("digest", "--cwd", PROJECT, "--session", "cc-dead", "--part", "7")
        self.assertEqual(code, 2)
        self.assertIn("only 1 part", out + err)

    def test_show_can_page_through_a_long_field(self):
        self.seed()
        session = sd.parse_session([self.claude_dir / "projects" / "-work-proj" / "cc-dead.jsonl"], "claude-code")
        index = next(e.i for e in session.events if e.kind == "tool")
        code, start, _ = self.run_cli("show", "--cwd", PROJECT, "--session", "cc-dead", "--event", str(index),
                                      "--max-chars", "1000")
        self.assertEqual(code, 0)
        self.assertNotIn("END-OF-COMMAND", start)
        self.assertIn("--offset 1000", start)
        code, rest, _ = self.run_cli("show", "--cwd", PROJECT, "--session", "cc-dead", "--event", str(index),
                                     "--max-chars", "6000", "--offset", "1000")
        self.assertIn("END-OF-COMMAND", rest)

    def test_digest_accepts_a_session_id_prefix(self):
        self.seed()
        code, out, _ = self.run_cli("digest", "--cwd", PROJECT, "--session", "cc-de")
        self.assertEqual(code, 0)
        self.assertIn("Build the importer", out)

    def test_digest_reports_missing_sessions_with_exit_code_2(self):
        code, out, err = self.run_cli("digest", "--cwd", PROJECT)
        self.assertEqual(code, 2)
        self.assertIn("No previous session", out + err)

    def test_list_marks_the_current_session(self):
        self.seed()
        code, out, _ = self.run_cli("list", "--cwd", PROJECT, env={"CLAUDE_CODE_SESSION_ID": "cc-live"})
        self.assertEqual(code, 0)
        live_line = next(line for line in out.splitlines() if "cc-live" in line)
        dead_line = next(line for line in out.splitlines() if "cc-dead" in line)
        self.assertIn("current", live_line)
        self.assertNotIn("current", dead_line)

    def test_show_prints_one_event_in_full(self):
        self.seed()
        _, digest, _ = self.run_cli("digest", "--cwd", PROJECT, "--session", "cc-dead", "--budget", "6000")
        self.assertNotIn("END-OF-COMMAND", digest)
        session = sd.parse_session([self.claude_dir / "projects" / "-work-proj" / "cc-dead.jsonl"], "claude-code")
        index = next(e.i for e in session.events if e.kind == "tool")
        code, out, _ = self.run_cli("show", "--cwd", PROJECT, "--session", "cc-dead", "--event", str(index))
        self.assertEqual(code, 0)
        self.assertIn("END-OF-COMMAND", out)

    def test_search_returns_matching_event_numbers(self):
        self.seed()
        code, out, _ = self.run_cli("search", "importer", "--cwd", PROJECT, "--session", "cc-dead")
        self.assertEqual(code, 0)
        self.assertRegex(out, r"#\d+ .*user.*Build the importer")

    def test_script_only_reads_and_offers_no_option_that_writes_files(self):
        self.seed()
        before = sorted(str(p) for p in self.tmp.rglob("*"))
        with self.assertRaises(SystemExit):
            self.run_cli("digest", "--cwd", PROJECT, "--session", "cc-dead", "--out", str(self.tmp / "digest.md"))
        for command in (["list"], ["digest"], ["search", "importer"], ["show", "--event", "0"]):
            self.run_cli(*command, "--cwd", PROJECT, "--session", "cc-dead")
        self.assertEqual(sorted(str(p) for p in self.tmp.rglob("*")), before)

    def test_digest_of_an_explicit_transcript_file(self):
        path = cx_file(self.tmp, "x", [
            cx_meta("cx-9", "2026-01-02T10:00:00Z", cwd="/somewhere/else"),
            cx_user("Summarise the logs", "2026-01-02T10:00:01Z"),
            cx_agent("Summary written.", "2026-01-02T10:00:02Z"),
        ])
        code, out, _ = self.run_cli("digest", "--file", str(path))
        self.assertEqual(code, 0)
        self.assertIn("Summarise the logs", out)
        self.assertIn("codex", out)


if __name__ == "__main__":
    unittest.main()
