# Installation and usage guide

Start with the [README](../README.md) for the short version. This page covers personal installs, web/plugin differences, checkpoint setup, and maintaining release packages.

## Choose a format

Download packages from [GitHub Releases](https://github.com/MdRaf1/skills/releases/latest), or clone the source:

```text
git clone https://github.com/MdRaf1/skills.git
```

| Format | Use |
|---|---|
| `skills/<name>/` folder | Native installation in a CLI or IDE agent. Copy the whole folder, including supporting resources. |
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

Each prompt installs **only the selected skill**, preserves existing files, and stops before running a task. The Continue Work prompt also handles missing checkpoint setup. Neither prompt installs the other skill or changes global settings.

If the agent cannot fetch GitHub, provide the downloaded folder for that one skill. An agent without filesystem access cannot perform a project installation; use the web instructions below instead.

### Automatic versus explicit selection

- Codex's bundled `continue-work/agents/openai.yaml` disables implicit invocation. Explicitly select the recovery skill.
- `reuse-scout` can be discovered through its description in hosts that support automatic selection. It produces a report and stops before implementation.
- Claude Code, Cursor, the VS Code local harness, and current OpenCode document `disable-model-invocation: true`. Add that field to the YAML frontmatter of an **installed copy** if you want an additional manual-only guard. Preserve `name` and `description`; keep generic web-upload packages unchanged.
- Regardless of discovery behavior, Continue Work requires an explicit resume or inspection request. Loading a skill does not authorize external actions.
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

- **Continue Work:** attach the checkpoint, handover, and relevant redacted files or outputs. Without live project access, expect a snapshot-based review. Save proposed updated state into the real project yourself when the host cannot do that.
- **Reuse Scout:** enable available search/browsing or supply sources. Missing search access must be reported as a limitation, not fabricated current findings or a claim that nothing exists.

## Continue Work: setup and recovery

Follow the bundled [checkpoint setup guide](../skills/continue-work/references/SETUP.md). Install the skill in your agent, but create state in the **project whose work you want to continue**, not automatically in this catalog.

The setup guide includes templates and a standing instruction snippet. Put those rules somewhere the host actually loads; an unread sidecar does not maintain checkpoints.

Before ending a session, ask:

```text
Checkpoint the current work and stop. Save all outstanding requests, verified
completed work, the exact next step, restrictions, in-flight attempts, pending
writes, blockers, worker state, and actual test results. Do no further work.
```

In a fresh session, explicitly select Continue Work and ask for an inspection first:

```text
Inspect the checkpoint and relevant evidence only. Do not resume the task or
change files. Report the task, remaining requests, next step, and uncertainty.
```

If that matches where you stopped, explicitly ask it to continue.

This lightweight version has no automatic prompt/tool receipt logger, transcript importer, session-ID lookup, or concurrent-writer coordination. It does not fix a gateway or recover unsaved reasoning. Keep one active checkpoint writer at a time. Verify uncertain sends, pushes, deployments, migrations, and submissions before any repeat attempt.

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

The skills need no Python runtime. Maintainers use Python 3's standard library:

```text
python -I scripts/package_skills.py
python -I scripts/package_skills.py --check
```

Use `python3` if that is your platform's Python 3 command. The builder generates five archives in the **ignored local `dist/` directory**. `--check` verifies existing packages without rewriting them; on a fresh clone, build first.

Upload these generated files as GitHub Release assets:

- `continue-work.zip` and `continue-work.skill`
- `reuse-scout.zip` and `reuse-scout.skill`
- `skills-plugin.zip`

Keep the source folders in Git and archives in [Releases](https://github.com/MdRaf1/skills/releases). Do not commit newly generated archives. Earlier commits may still contain the original binaries; moving current downloads to Releases does not rewrite repository history.

The builder checks resource allowlists, rejects symlinks/unexpected resources, checks basic metadata and the uninitialized checkpoint, and verifies archive content against source. ZIP and `.skill` pairs must be identical. These are package checks, not tests of installation or execution in every destination product.

## Privacy and attribution

Do not add live checkpoints, conversations, credentials, or application records to this catalog. Git ignores are not encryption or access controls. A public skills repository does not make your private working project accessible to an AI tool.

Reuse Scout preserves the supplied instructions and their attribution to ECC's MIT-licensed `search-first` skill. See the [third-party notice](../skills/reuse-scout/THIRD_PARTY_NOTICES.md) and [upstream license](../skills/reuse-scout/LICENSE.upstream.txt). That upstream notice does not assign a blanket license to every addition in this collection.

Installation details were checked against official documentation on **2026-11-10**. Product versions, account eligibility, organizational policies, and available tools can change. Check Gemini CLI's current eligibility/availability notes for your account.

## Official documentation

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Using skills in Claude](https://support.claude.com/en/articles/12512180-using-skills-in-claude)
- [Codex and ChatGPT skills](https://developers.openai.com/codex/skills/)
- [Portable plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [Cursor skills](https://cursor.com/docs/context/skills)
- [VS Code agent skills](https://code.visualstudio.com/docs/agent-customization/agent-skills)
- [Gemini CLI skills](https://geminicli.com/docs/cli/skills/)
- [OpenCode skills](https://opencode.ai/docs/skills/)
