# Continue Work: setup and daily use

`continue-work` lets a fresh session pick up where a dead one stopped. It reads the dead session's transcript from disk, checks it against the working tree and any saved checkpoint, and carries on.

## What is in the folder

- `SKILL.md`: the recovery procedure the agent follows.
- `scripts/session_digest.py`: the transcript reader. Python 3, standard library only. It reads and prints; it never writes, deletes or sends anything.
- `templates/continuation.json`, `templates/continuation-handover.md`: an empty checkpoint and its handover.
- `snippets/AGENTS.md`: standing rules that make an agent keep the checkpoint current.
- `snippets/gitignore.txt`: ignore rules for the private state.
- `agents/openai.yaml`: Codex presentation and its explicit-invocation policy.

## Install

Copy the whole folder into your tool's skills directory. For every project on this machine:

| Tool | Folder |
|---|---|
| Claude Code | `~/.claude/skills/continue-work/` |
| Codex | `~/.agents/skills/continue-work/` |

Project-level folders (`.claude/skills/`, `.agents/skills/`) work too. Other tools are listed in the repository's installation guide. Nothing else is required for transcript recovery: no hooks, no settings, no per-project setup.

## Use it after a failure

1. The session dies: a gateway error, a crash, a session too long or too old to resume.
2. Open a **new** session in the same project folder. Do not use `--resume` or `--continue`; a fresh session carries nothing the gateway can reject.
3. Type `/continue-work` in Claude Code, or `$continue-work` in Codex.

You do not paste a session id, a transcript or a summary. The agent reports what it recovered in a few lines and continues the work.

| You type | Result |
|---|---|
| `/continue-work` | Continue the most recent earlier session of this project |
| `/continue-work and skip the docs for now` | Same, with a new instruction that outranks the old ones |
| `/continue-work inspect` | Report what would be resumed. Nothing is changed |
| `/continue-work list` | List the sessions found for this project |
| `/continue-work 7e0016c5` | Continue that session (an id, an id prefix, or a transcript path) |
| `/continue-work handoff` | Save portable state before moving to another machine or tool |

Ask for `inspect` first whenever you want to check the recovery before any work happens.

## How the previous session is found

The reader looks for sessions that were started in the current project folder:

- Claude Code: `~/.claude/projects/<project>/<session-id>.jsonl` (`CLAUDE_CONFIG_DIR` is honoured).
- Codex: `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` (`CODEX_HOME` is honoured).

It takes the most recent session other than the live one. If that session did little, because it was itself a retry that died, the sessions before it are included until one with substantial work is reached, four at most. A project started in Codex can therefore be continued in Claude Code on the same machine, and the other way round.

Claude Code tells the reader which session is live through `CLAUDE_CODE_SESSION_ID`. Elsewhere the reader treats a session whose last prompt invoked `continue-work` as the live one and says so in the digest.

You can run the reader yourself:

```text
python3 <skill folder>/scripts/session_digest.py list
python3 <skill folder>/scripts/session_digest.py digest
python3 <skill folder>/scripts/session_digest.py digest --session <id> --budget 60000
python3 <skill folder>/scripts/session_digest.py show --session <id> --event 120-124
python3 <skill folder>/scripts/session_digest.py search --session <id> "migration"
```

`digest` prints every user prompt, how the session ended, the files and commands it touched, calls that must be verified before they are repeated, and the final stretch of activity. `--budget` sets the approximate total size in characters (default 66000). Agent tools cut long output short, so the digest prints in parts of at most 22000 characters: each part ends with the command for the next one, and `--part all` prints everything at once for saving to a file. `list --all` lists every project, which finds sessions of a folder that was later moved or renamed.

## Checkpoints: optional, and what makes a move possible

Transcripts stay on the machine that wrote them. A checkpoint is a small agent-maintained record inside the project that survives a move to another machine or tool and records intent that a transcript only implies: the exact next step, uncertain outcomes, what was deferred.

To enable it for a project, give a repository-connected agent this request. Replace `<SKILL_FOLDER>` with the installed folder.

```text
Set up continuation checkpoints for THIS project using the templates and snippets in <SKILL_FOLDER>.

Read existing project instructions first. Do not resume earlier work or change application code as part of setup.

- If this project already defines a continuation location or workflow, explain any conflict before adding another one.
- Merge the standing rules from snippets/AGENTS.md into instructions this host loads automatically. Preserve existing rules.
- Add the exclusions from snippets/gitignore.txt to .gitignore without removing other entries. If a state file is already tracked, report it.
- Only when missing, create .scratch/continuation.json and .scratch/continuation-handover.md from the templates.
- Set projectRoot to this project's actual absolute root and updatedAt to the actual current ISO timestamp. Leave task and nextUnit null and status idle until I provide the task.
- Ask before replacing an existing skill or checkpoint. Do not edit global configuration, hooks, permissions, models, or credentials. Do not commit or push.
- Validate the JSON and report the files created or changed and anything skipped.
```

Where the rules go: Codex and OpenCode read `AGENTS.md`. Claude Code 2.1.277 and later reads `AGENTS.md` when the project has no `CLAUDE.md`; when it has one, add a line `@AGENTS.md` to that `CLAUDE.md`. Gemini CLI reads `GEMINI.md`.

Checkpoint fields: `schemaVersion`, `projectRoot`, `updatedAt` (a real ISO timestamp), `status` (`idle`, `active`, `paused`, `blocked` or `completed`), `task`, `handover`, `authoritativePaths`, `outstandingRequests`, `completed`, `nextUnit`, `inFlight`, `pendingMutations`, `blockers`, `activeWorkers`, `restrictions`. Keep the JSON compact. Decisions, evidence pointers, test results and anything a person must do belong in the handover.

## Moving to another machine or tool

1. In the old place, run `/continue-work handoff`. It brings the checkpoint and handover up to date and saves a digest of the session under `.scratch/session-digests/`.
2. Carry the project across with `.scratch/` included. `.scratch/` is ignored by Git by default, so use a **private** repository with the folder added on purpose, or copy the folder directly. Never publish it.
3. In the new place, open the project and run `/continue-work`. No transcript exists there, so the agent works from the checkpoint, the saved digest and the files. If the project path changed, it resolves saved paths against the new root.

## Web chat

A web chat has no access to your disk. Upload the checkpoint, the handover, a saved digest and the relevant files, and ask for a snapshot-based review or next-step plan. Save anything it produces into the real project yourself. Never upload credentials.

## Limits and privacy

- A digest is a condensed record. The agent can read any event in full from the transcript, but only on the machine that still has it.
- Reasoning the old session never recorded, unsaved editor or browser state, and tool permissions are not recovered.
- Sends, pushes, deployments, migrations and payments with an uncertain outcome are verified, never repeated on a guess.
- Credentials are masked in digests on a best-effort basis. Treat a saved digest as private: it contains your prompts and tool output.
- The reader parses Claude Code and Codex transcripts. For other tools, recovery uses the checkpoint and the files, or a transcript you pass with `--file`.
- Recovery does not repair a gateway. It makes the failure cheap.
