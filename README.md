# Skills

Two skills for AI coding assistants and chat tools.

| Skill | What it does |
|---|---|
| [**reuse-scout**](skills/reuse-scout/SKILL.md) | Finds existing projects, libraries, and tools before you build. Compares options and explains what still needs custom work. |
| [**continue-work**](skills/continue-work/SKILL.md) | Resumes interrupted work from a saved checkpoint, checking what actually happened before repeating anything. |

## Download

Get ready-to-upload packages from **[Releases](https://github.com/MdRaf1/skills/releases/latest)**:

| Skill | Downloads |
|---|---|
| Continue Work | [ZIP](https://github.com/MdRaf1/skills/releases/latest/download/continue-work.zip) · [.skill](https://github.com/MdRaf1/skills/releases/latest/download/continue-work.skill) |
| Reuse Scout | [ZIP](https://github.com/MdRaf1/skills/releases/latest/download/reuse-scout.zip) · [.skill](https://github.com/MdRaf1/skills/releases/latest/download/reuse-scout.skill) |

A [combined plugin ZIP](https://github.com/MdRaf1/skills/releases/latest/download/skills-plugin.zip) is also available for compatible plugin installers. Each `.skill` file contains the same ZIP bytes as its matching `.zip`.

## Install

### Claude web

1. Download the skill's **ZIP** above.
2. Open **Customize → Skills → + → Create skill → Upload a skill**.
3. Upload and enable it, then ask Claude to use the skill.

Skill uploads depend on your account's available features and file-creation capability.

### CLI and IDE tools

Clone the source:

```sh
git clone https://github.com/MdRaf1/skills.git
```

Copy the whole `skills/<name>/` folder into your working project's directory below. `<name>` is `reuse-scout` or `continue-work`. Check before replacing an existing copy.

| Tool | Destination | Use it |
|---|---|---|
| Claude Code | `.claude/skills/<name>/` | `/reuse-scout` or `/continue-work` |
| Codex | `.agents/skills/<name>/` | `$reuse-scout` or `$continue-work` |
| Cursor | `.cursor/skills/<name>/` | Select the skill from `/` |
| VS Code Copilot, local agent | `.github/skills/<name>/` | Select the skill from `/` |
| Gemini CLI | `.gemini/skills/<name>/` | Ask it to activate the named skill |
| OpenCode | `.opencode/skills/<name>/` | Ask it to load the named skill |

Restart the tool if the skill does not appear. For personal installs, other clients, and plugin setup, see the [full installation guide](docs/INSTALLATION.md).

### ChatGPT, Gemini, and other web chats

If native skill installation is unavailable, upload or paste the skill's **`SKILL.md`** and say:

> Use these instructions for this task: [describe your task]. Tell me what information or tools you are missing.

This is instruction-based use, not a native installation. It does not give the chat access to your computer or add tools. ChatGPT's native web route uses plugin-bundled skills; see the [guide](docs/INSTALLATION.md#web-and-desktop-tools) for the distinction.

## Use

**Reuse Scout:** after loading it, ask:

> Find the best existing foundations for a self-hosted notes app. Compare coverage, maintenance, license, and effort. Don't write code yet.

**Continue Work:** first follow its [one-time checkpoint setup](skills/continue-work/references/SETUP.md). Before ending a session, ask the agent to save the current task, completed work, and exact next step. In a fresh session, invoke the skill to check the saved state and continue.

Continue Work needs saved evidence—it cannot recover work that was never recorded. For web use, attach the checkpoint, handover, and relevant files. Keep credentials out of those files, and verify uncertain sends or deployments before retrying.

## More

- [Detailed installation, usage, and package-building guide](docs/INSTALLATION.md)
- [Reuse Scout attribution and upstream MIT notice](skills/reuse-scout/THIRD_PARTY_NOTICES.md)
