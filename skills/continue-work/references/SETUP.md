# Continue Work: first-time setup and daily use

Install the whole `continue-work` skill folder using your host's documented skill location. This reference describes state setup **inside the project you want to resume**, not inside the separate skills catalog unless the catalog itself is your task.

## What is included

- `SKILL.md`: the recovery procedure.
- `templates/continuation.json`: an intentionally uninitialized checkpoint.
- `templates/continuation-handover.md`: the longer handover template.
- `snippets/AGENTS.md`: standing checkpoint-maintenance instructions.
- `snippets/gitignore.txt`: exclusions for private state.
- `agents/openai.yaml`: Codex presentation and explicit-only invocation policy.

This is the lightweight version: no automatic receipt logger, native transcript importer, session-ID lookup, or hook setup. It works from saved state and available evidence.

## 1. Initialize state in the actual project

After installing the skill, give a repository-connected agent this request. Replace `<INSTALLED_SKILL_FOLDER>` with its actual location.

```text
Set up lightweight continuation for THIS project using the templates and snippets in <INSTALLED_SKILL_FOLDER>.

Read existing project instructions first. Do not resume earlier work or change application code as part of setup.

- If this project already defines a continuation location or workflow, explain any conflict before adding another one.
- Merge the standing rules from snippets/AGENTS.md into instructions this host actually loads automatically. Preserve existing rules. Do not create an unread sidecar and assume it will be enforced.
- Add the private-state exclusions from snippets/gitignore.txt to .gitignore without removing other entries. If a state file is already tracked, report it rather than silently rewriting Git history or removing it from the index.
- Only when missing, create .scratch/continuation.json and .scratch/continuation-handover.md from the templates.
- Set projectRoot to this project's actual absolute root and updatedAt to the actual current ISO timestamp. Leave task and nextUnit null and status idle until I provide the task.
- Inspect existing files before changing them. Ask before replacing an existing skill or checkpoint. Do not edit global configuration, hooks, permissions, models, or credentials. Do not commit or push.
- Validate the JSON and report the actual created/changed files and anything skipped.
```

For Codex and OpenCode, `AGENTS.md` is a conventional project-instruction file. Claude Code uses `CLAUDE.md`; it can import an existing `AGENTS.md` with a standalone `@AGENTS.md` line when appropriate. Gemini CLI uses `GEMINI.md`. IDE agents have their own project-instruction mechanisms: check the host's configuration rather than assuming every file named `AGENTS.md` is loaded. Avoid circular imports and duplicate rules.

The raw checkpoint template has a null root and no task on purpose. It does not claim that a previous session was reviewed.

## 2. Start real work

Give the agent your actual task. The standing project rules request checkpoint updates at meaningful boundaries, even when the recovery skill is not loaded.

Before deliberately ending a session, say:

```text
Checkpoint the current work and stop. Save every outstanding request, verified completed work, exact next step, restrictions, in-flight attempts, pending writes, blockers, worker state, and actual test results. Do no further task work after saving.
```

The JSON is a compact index; the handover holds decisions, explanations, evidence pointers, uncertainties, and human handoff details. Both are notes, not proof that an external action succeeded.

## 3. Verify recovery in a fresh session

Open a fresh session in the same project. Explicitly select the installed skill, then request an inspection only:

```text
Use continue-work to inspect the saved checkpoint and relevant files only. Do not resume the task or change files. Report the verified task, outstanding requests, exact next unit, and any discrepancy or uncertainty.
```

In Codex, explicitly mention `$continue-work` or select it through `/skills`. In Claude Code, use `/continue-work`; your accompanying request should make clear when only an inspection is wanted. Other hosts use their documented selector or skill-loading mechanism. No universal slash-command syntax is assumed.

Expected: the same saved task and next step are recovered, actual evidence is checked where accessible, and no next-unit action is taken. If state is wrong or missing, correct it from evidence rather than inventing earlier progress.

Then explicitly ask the agent to continue the verified outstanding work within the existing scope and permissions.

## Everyday use

- **After a crash:** start a fresh session in the project and explicitly invoke `continue-work`.
- **Different checkpoint:** identify its path in the request. Relative paths are resolved within the current project; no session-ID lookup is included.
- **Pause:** ask for status `paused`, a saved next unit, and no further work until you explicitly resume.
- **New task:** state that it is new. Old deferred work must not be silently reopened.
- **Uncertain send/deploy/push/migration:** verify the external result before repeating it. A lost response is not proof of failure.
- **Switching CLIs:** stop the first writer after saving, then open the other CLI in the same project. This starter does not coordinate simultaneous checkpoint writers.

## Using it in web chat

A web chat does not automatically have your local repository or its real filesystem. Upload `SKILL.md`, the current checkpoint, the handover, and only the relevant redacted source/output files you want it to inspect. Supply referenced files separately when needed.

Ask for a **snapshot-based review** or next-step plan. Require it to state which claims could not be checked live. If it produces an updated checkpoint attachment, save that file into your actual project yourself; creating a chat attachment is not a repository write.

Never upload credentials or assume a private GitHub URL is readable merely because you pasted it. When adequate evidence is unavailable, the correct outcome is to identify the missing inputs, not reconstruct an imaginary session.

## Limits and privacy

- A crash between checkpoints may leave real files ahead of the notes. Inspect targets before retrying.
- Ignored state does not travel through Git. Reusing the skill in a different project needs fresh state. Continuing the same task on another machine requires a deliberate private transfer and root/path reconciliation.
- If `projectRoot` differs, stop and verify the move before following old paths.
- Keep state out of public Git and web-research services. Ignore rules are not encryption or filesystem permissions.
- Recovery does not carry previous approvals, change service limits, or fix a gateway.
- Automatic tool/prompt receipts would be a separate, host-specific extension. Do not copy another project's logger or hooks unchanged.
