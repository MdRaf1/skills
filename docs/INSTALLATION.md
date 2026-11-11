# Installation and usage guide

Start with the [README](../README.md) for the short version. This page covers personal installs, web/plugin differences, session recovery, and maintaining release packages.

## Choose a format

Download packages from [GitHub Releases](https://github.com/MdRaf1/skills/releases/latest), or clone the source:

```text
git clone https://github.com/MdRaf1/skills.git
```

| Format | Use |
|---|---|
| `skills/<name>/` folder | Native installation in a CLI or IDE agent. Copy the whole folder, including supporting resources such as `scripts/`. |
| `<name>.zip` | Upload to a host that accepts a skill ZIP, such as Claude.ai. |
| `<name>.skill` | The same ZIP bytes with a different extension. Use it only when your host accepts that filename type. |
| `skills-plugin.zip` | Both skills packaged with a portable root `plugin.json`, for compatible plugin installation/distribution workflows. |
| `SKILL.md` text | Upload/paste as instructions when native skill installation is unavailable. Supply referenced files separately when needed. |

Cloning a catalog does not register its skills with every AI tool. Installing instructions does not install browsing tools, grant repository access, or carry permissions between sessions.

## CLI and IDE installation

`<name>` means `continue-work` or `reuse-scout`. Copy the matching folder from this catalog into the desired project or personal location. Preserve any existing local modifications; do not overwrite an installed skill or checkpoint without reviewing it.

| Host | Project location | Personal location | Explicit use |
|---|---|---|---|
| Claude Code | `.claude/skills/<name>/` | `~/.claude/skills/<name>/` | `/continue-work` or `/reuse-scout` |
| Codex CLI / IDE extension | `.agents/skills/<name>/` | `~/.agents/skills/<name>/` | `$continue-work`, `$reuse-scout`, or `/skills` selection |
| Cursor Agent | `.cursor/skills/<name>/` or `.agents/skills/<name>/` | `~/.cursor/skills/<name>/` or `~/.agents/skills/<name>/` | Select the skill through Agent chat's `/` menu |
| VS Code Copilot local agent | `.github/skills/<name>/` | `~/.copilot/skills/<name>/` | Select through `/`; the local harness also has `/skills` configuration |
| Gemini CLI | `.gemini/skills/<name>/` or `.agents/skills/<name>/` | `~/.gemini/skills/<name>/` or `~/.agents/skills/<name>/` | Check `/skills list`, then ask it to activate the skill and review consent |
| OpenCode | `.opencode/skills/<name>/` | `~/.config/opencode/skills/<name>/` | Ask it to load the named skill through its `skill` tool |

`~` is the home directory on the machine running the agent. On Windows, use the corresponding Windows user-profile directory. The entry point must be named **`SKILL.md`**, with that capitalization.

Restart the agent if discovery has not refreshed. Gemini CLI also documents `/skills reload`. Do not assume `/skills` and `/name` have the same meaning in every client.

### Let an agent install one skill

Open the project where you want the skill and paste its individual setup prompt from the README:

- [Install Reuse Scout with AI](../README.md#install-reuse-scout)
- [Install Continue Work with AI](../README.md#install-continue-work)

Each prompt installs **only the selected skill**, preserves existing files, and stops before running a task. The Continue Work prompt also checks that the bundled transcript reader runs. Neither prompt installs the other skill or changes global settings.

If the agent cannot fetch GitHub, provide the downloaded folder for that one skill. An agent without filesystem access cannot perform a project installation; use the web instructions below instead.

### Automatic versus explicit selection

- Codex's bundled `continue-work/agents/openai.yaml` disables implicit invocation. Explicitly select the recovery skill with `$continue-work`.
- In Claude Code, Continue Work can also be selected from its description when you ask to continue or resume earlier work. Its frontmatter pre-approves one command, the bundled read-only transcript reader, through `allowed-tools`; every other action still goes through your normal permission prompts.
- `reuse-scout` can be discovered through its description in hosts that support automatic selection. It produces a report and stops before implementation.
- Claude Code, Cursor, the VS Code local harness, and current OpenCode document `disable-model-invocation: true`. Add that field to the YAML frontmatter of an **installed copy** if you want an additional manual-only guard. Preserve `name` and `description`; keep generic web-upload packages unchanged.
- Regardless of discovery behavior, Continue Work acts only on a request to continue, resume, inspect, or hand off earlier work. Loading a skill does not authorize external actions.
- Keep normal permission and consent prompts enabled. These skills do not require blanket approval flags.

### Other clients and remote workspaces

Pi, Antigravity, GitHub Copilot CLI, Cline, Windsurf, Aider, and other clients have their own versions and configuration surfaces. Check their native skill documentation; do not assume VS Code settings configure an independent CLI or every client reads `.agents/skills`.

Without native support, ask the agent to read the relevant `SKILL.md` as instructions for the task. That is instruction-file use, not native discovery.

Cloud agents need the files in their remote workspace or through a supported sync feature. A local install does not automatically make a skill available remotely.

## Web and desktop tools

### Claude.ai

1. Download the desired skill ZIP from [Releases](https://github.com/MdRaf1/skills/releases/latest).
2. Open **Customize → Skills → + → Create skill → Upload a skill**.
3. Upload, review, and enable the skill.
4. Explicitly ask Claude to use it for your task.

The official article requires **Code execution and file creation / Create and edit files**. Account and organization policies can affect availability. If the upload controls are missing, use the text fallback below.

Attaching a ZIP to an ordinary conversation is not the same as installing an enabled skill. The CLI's `/name` syntax is not a universal Claude.ai shortcut. In Claude Desktop, distinguish account/chat skill features from the Code experience; Code uses the repository workflow.

### ChatGPT web and desktop

OpenAI's documentation distinguishes:

- **Standalone skills:** available in the ChatGPT desktop app, Codex CLI, and IDE extension.
- **Plugin-bundled skills:** available across ChatGPT web, desktop, and mobile.

This catalog supplies [`plugin.json`](../plugin.json), root `skills/`, and a [combined plugin ZIP](https://github.com/MdRaf1/skills/releases/latest/download/skills-plugin.zip). The portable format discovers skills from the root `skills/` directory; this instruction-only plugin does not need an app or MCP server.

The combined archive is an optional download, not part of the individual-skill setup in this guide. This repository has not been published to a vendor plugin directory. If a skill is already available in your ChatGPT account, type `@` to select it.

A universal standalone-ZIP upload button in ChatGPT web, or automatic installation from a GitHub link, is not established here. A prepared package is not proof that an account can import it directly. See the official [plugin packaging](https://developers.openai.com/plugins/build/plugins) and [skills](https://developers.openai.com/codex/skills/) documentation for your environment.

If native installation is unavailable, use the text fallback. Attaching a file to a custom GPT or project as knowledge alone does not ensure it will be applied; explicitly request its use.

### Gemini web/Gems, Copilot web, and other chats

No universal `SKILL.md` installer is assumed. Use file attachments, reusable instructions, or project knowledge where available, and explicitly ask the model to follow the skill for the task. Otherwise paste its contents.

### Text fallback

Upload `SKILL.md` itself or paste its text, then ask:

```text
Use the attached instructions for this task: <your task>.
Adapt the steps to your available capabilities. Ask for missing inputs.
Do not assume access to my local files, private repositories, credentials,
or external tools. State what you cannot verify, and ask before external
changes. Do not claim that a chat attachment was saved into my repository.
```

Supply referenced files separately when needed. An AI being able to read instructions does not give it tools or persistent project storage.

- **Continue Work:** a web chat cannot read session transcripts on your computer. Attach the checkpoint, handover, a saved digest, and relevant redacted files or outputs. Expect a snapshot-based review. Save proposed updated state into the real project yourself when the host cannot do that.
- **Reuse Scout:** enable available search/browsing or supply sources. Missing search access must be reported as a limitation, not fabricated current findings or a claim that nothing exists.

## Continue Work: recovery, checkpoints, and moving

Full details are in the bundled [setup and daily-use guide](../skills/continue-work/references/SETUP.md).

**After a failure.** Open a new session in the same project folder, without `--resume` or `--continue`, and invoke the skill: `/continue-work` in Claude Code, `$continue-work` in Codex. Nothing else is supplied. Add `inspect` to see what would be resumed before any work happens, `list` to see the sessions found, or a session id to choose one.

**What it reads.** The bundled `scripts/session_digest.py` reads the transcripts Claude Code and Codex already keep (`~/.claude/projects/`, `~/.codex/sessions/`; `CLAUDE_CONFIG_DIR` and `CODEX_HOME` are honoured) and prints a bounded digest of the previous session, or of several consecutive sessions when the latest one was only a short retry. The digest is printed in parts, because agent tools cut long output short. It needs Python 3 and the standard library. It reads and prints; it has no option that writes, deletes, or sends anything. The agent then compares the digest with the working tree and any checkpoint before continuing.

**Checkpoints.** A checkpoint is an optional, agent-maintained record in the project (`.scratch/continuation.json` plus a handover). On one machine the transcript is enough. A checkpoint adds what a transcript only implies, such as the exact next step and uncertain outcomes, and it is what survives a move. The setup guide has the one-time request that enables it and the standing instruction snippet. Put those rules somewhere the host loads: Codex and OpenCode read `AGENTS.md`; Claude Code 2.1.277 and later reads `AGENTS.md` when the project has no `CLAUDE.md`, and otherwise needs an `@AGENTS.md` line in `CLAUDE.md`.

**Moving to another machine or tool.** Transcripts stay where they were written. Run `/continue-work handoff` first: it updates the checkpoint and handover and saves a digest under `.scratch/session-digests/`. Carry the project across with `.scratch/` included, privately, then run `/continue-work` there.

**Limits.** Recovery gets close to the old conversation, not identical. Reasoning the old session never recorded, unsaved editor or browser state, and tool permissions are not recovered. Uncertain sends, pushes, deployments, migrations, and submissions are verified before any repeat attempt. The reader parses Claude Code and Codex transcripts; other tools fall back to the checkpoint and files, or to a transcript passed with `--file`. Credentials in digests are masked on a best-effort basis only. Nothing here repairs a gateway.

## Reuse Scout: example tasks

**Before building:**

```text
Find existing foundations for a self-hosted notes app on Windows and Linux.
Compare coverage, maintenance, license, access risks, cost, and adaptation
work. Rank the closest matches and their gaps. Do not write code yet.
```

**When blocked:**

```text
Use blocker mode for <exact error or observed behavior> in <library/version>.
I already tried <verified attempts>. Find the best-supported fix or workaround,
its relevant versions and evidence, and how to verify it. Do not implement it.
```

The skill recommends Adopt, Extend, Compose, Reference, or Build only the remaining gap, then asks you to choose a path. A quick scout targets roughly ten tool calls; deeper work has a larger bounded budget. Tool names and model-tier hints are preferences, not guaranteed APIs in every host.

## Build and publish packages

Reuse Scout needs no runtime. Continue Work's transcript reader needs Python 3 on the machine where the agent runs. Maintainers use Python 3's standard library:

```text
python -m unittest discover -s tests
python -I scripts/package_skills.py
python -I scripts/package_skills.py --check
```

Use `python3` if that is your platform's Python 3 command. The first line runs the transcript reader's tests, which use synthetic transcripts only. The builder generates five archives in the **ignored local `dist/` directory**. `--check` verifies existing packages without rewriting them; on a fresh clone, build first.

Upload these generated files as GitHub Release assets:

- `continue-work.zip` and `continue-work.skill`
- `reuse-scout.zip` and `reuse-scout.skill`
- `skills-plugin.zip`

Keep the source folders in Git and archives in [Releases](https://github.com/MdRaf1/skills/releases). Do not commit newly generated archives. Earlier commits may still contain the original binaries; moving current downloads to Releases does not rewrite repository history.

The builder checks resource allowlists, rejects symlinks/unexpected resources, checks basic metadata and the uninitialized checkpoint, and verifies archive content against source. ZIP and `.skill` pairs must be identical. Archive entries are stored without the executable bit, so the reader is always run through the interpreter (`python3 .../session_digest.py`). These are package checks, not tests of installation or execution in every destination product.

## Privacy and attribution

Do not add live checkpoints, session digests, conversations, credentials, or application records to this catalog. Git ignores are not encryption or access controls. A public skills repository does not make your private working project accessible to an AI tool.

Reuse Scout preserves the supplied instructions and their attribution to ECC's MIT-licensed `search-first` skill. See the [third-party notice](../skills/reuse-scout/THIRD_PARTY_NOTICES.md) and [upstream license](../skills/reuse-scout/LICENSE.upstream.txt). That upstream notice does not assign a blanket license to every addition in this collection.

Installation details were checked against official documentation on **2026-11-10**; Claude Code skill frontmatter, placeholders, and `AGENTS.md` loading were rechecked on **2026-11-11**. The transcript reader was checked against transcripts written by Claude Code 2.1.322 and Codex CLI 0.167; both formats are undocumented and can change. Product versions, account eligibility, organizational policies, and available tools can change. Check Gemini CLI's current eligibility/availability notes for your account.

## Official documentation

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Claude Code project instructions and `AGENTS.md`](https://code.claude.com/docs/en/memory)
- [Using skills in Claude](https://support.claude.com/en/articles/12512180-using-skills-in-claude)
- [Codex and ChatGPT skills](https://developers.openai.com/codex/skills/)
- [Portable plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [Cursor skills](https://cursor.com/docs/context/skills)
- [VS Code agent skills](https://code.visualstudio.com/docs/agent-customization/agent-skills)
- [Gemini CLI skills](https://geminicli.com/docs/cli/skills/)
- [OpenCode skills](https://opencode.ai/docs/skills/)
