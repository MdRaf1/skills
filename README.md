# Skills

Two skills for AI coding assistants and chat tools.

| Skill | What it does |
|---|---|
| [**reuse-scout**](skills/reuse-scout/SKILL.md) | Finds existing projects, libraries, and tools before you build. Compares options and explains what still needs custom work. |
| [**continue-work**](skills/continue-work/SKILL.md) | Continues a dead session in a fresh one. Reads the old session's transcript from disk, checks it against the files, and carries on without you restating anything. |

## Continue any session

For when a session dies on a gateway or API error, grows too long, or can no longer be resumed.

1. Open a **new** session in the same project folder. Do not use `--resume` or `--continue`.
2. Type `/continue-work` (Claude Code) or `$continue-work` (Codex).

That is all. You do not paste a session id, a transcript, or a summary. The agent finds the previous session on disk, tells you in a few lines what it recovered, and continues the work.

| You type | Result |
|---|---|
| `/continue-work` | Continue the most recent earlier session of this project |
| `/continue-work and skip the docs for now` | Same, plus a new instruction that outranks the old ones |
| `/continue-work inspect` | Show what would be resumed. Nothing is changed |
| `/continue-work list` | List the sessions found for this project |
| `/continue-work 7e0016c5` | Continue a specific session (an id, an id prefix, or a transcript path) |
| `/continue-work handoff` | Save portable state before moving to another machine or tool |

How it works: Claude Code and Codex already write every session to disk (`~/.claude/projects/`, `~/.codex/sessions/`). The bundled reader, `scripts/session_digest.py`, turns the previous session into a bounded digest, printed in parts small enough for an agent to read in full: every prompt you wrote, how the session ended, which files and commands it touched, which calls must be verified before they are repeated, and the final stretch of activity. If the latest session was only a short retry that also died, the sessions before it are included too. The agent then checks the digest against the real files and any saved checkpoint before it continues.

What to expect:

- It needs Python 3 for the reader. Without Python, recovery falls back to the checkpoint and the files.
- It works across tools on one machine: start in Codex, continue in Claude Code, or the reverse.
- Transcripts do not move between machines. Before switching machine, run `/continue-work handoff` and carry `.scratch/` across privately. See [setup and daily use](skills/continue-work/references/SETUP.md#moving-to-another-machine-or-tool).
- It gets close to the old conversation, not identical. Reasoning the old session never recorded cannot be recovered, and uncertain pushes, deployments, or payments are verified rather than repeated.

## Download

Get ready-to-upload packages from **[Releases](https://github.com/MdRaf1/skills/releases/latest)**:

| Skill | Downloads |
|---|---|
| Continue Work | [ZIP](https://github.com/MdRaf1/skills/releases/latest/download/continue-work.zip) · [.skill](https://github.com/MdRaf1/skills/releases/latest/download/continue-work.skill) |
| Reuse Scout | [ZIP](https://github.com/MdRaf1/skills/releases/latest/download/reuse-scout.zip) · [.skill](https://github.com/MdRaf1/skills/releases/latest/download/reuse-scout.skill) |

The [combined plugin ZIP](https://github.com/MdRaf1/skills/releases/latest/download/skills-plugin.zip) remains available as an optional download. Each `.skill` file contains the same ZIP bytes as its matching `.zip`.

## Install

### Claude Code plugin marketplace

This repository is a Claude Code plugin marketplace. Each skill is its own plugin, so you install only what you want. Inside Claude Code:

```text
/plugin marketplace add MdRaf1/skills
/plugin install continue-work@mdraf1-skills
/plugin install reuse-scout@mdraf1-skills
```

On Claude Code 2.1.275 or later, one line adds the marketplace and installs a plugin:

```text
/plugin install continue-work --marketplace MdRaf1/skills
/plugin install reuse-scout --marketplace MdRaf1/skills
```

Skills installed as plugins are namespaced by plugin name: type `/continue-work:continue-work` or `/reuse-scout:reuse-scout`. Arguments work the same way, for example `/continue-work:continue-work list`. Run `/plugin marketplace update mdraf1-skills` to pick up new releases.

### Continue Work for every project (Claude Code, manual copy)

```text
git clone https://github.com/MdRaf1/skills.git
mkdir -p ~/.claude/skills
cp -r skills/skills/continue-work ~/.claude/skills/
```

Start a new Claude Code session and type `/continue-work list` to confirm it loads. For Codex, copy the same folder to `~/.agents/skills/`. To update later, pull the repository and copy the folder again.

### Let your AI handle the setup

Open the project where you want the skill in Claude Code, Codex, Cursor, or another agent that can edit project files. Paste **one** of these prompts.

#### Install Reuse Scout

```text
Install only reuse-scout from: https://github.com/MdRaf1/skills/tree/main/skills/reuse-scout

Read the repository's installation guide and the skill first. Copy the whole skill folder into this AI tool's project-level skills directory. Ask if the host or target project is unclear. Preserve supporting files and ask before replacing existing files. Do not install another skill, change global settings, or run reuse-scout. Stop after installation and tell me how to invoke it.
```

#### Install Continue Work

```text
Install only continue-work from: https://github.com/MdRaf1/skills/tree/main/skills/continue-work

Read the repository's installation guide and the skill first. Copy the whole skill folder, including scripts/, into this AI tool's project-level skills directory. Ask if the host or target project is unclear. Preserve existing rules and state; ask before replacing anything. Do not install another skill, change global settings, or resume any task. Verify that `python3 <skill folder>/scripts/session_digest.py list` runs, and tell me how to invoke the skill.
```

If the agent cannot fetch GitHub, give it the downloaded folder for the **chosen skill**. These prompts do not install anything into a web account or give a chat access to your computer.

### Web apps or manual installation

- **Claude web:** download the chosen skill's ZIP, then open **Customize → Skills → + → Create skill → Upload a skill**. Upload and enable it. Availability depends on your account and file-creation capability.
- **ChatGPT, Gemini, or other web chats:** if native installation is unavailable, upload or paste that skill's `SKILL.md` and ask the AI to use it for your task. This is instruction-based use, not a native installation.
- **Manual CLI/IDE setup:** copy just the chosen skill folder into your tool's skills directory. See the [installation paths and web compatibility guide](docs/INSTALLATION.md).

A web chat cannot read session transcripts on your computer. There, Continue Work reviews the checkpoint, handover, or saved digest you upload.

## Use

- **Claude Code:** `/reuse-scout` or `/continue-work` for a copied skill folder; `/reuse-scout:reuse-scout` or `/continue-work:continue-work` for a marketplace plugin install.
- **Codex:** `$reuse-scout` or `$continue-work`.
- **Other tools:** use the invocation instructions reported during setup or in the [guide](docs/INSTALLATION.md).

After loading **Reuse Scout**, ask:

> Find the best existing foundations for a self-hosted notes app. Compare coverage, maintenance, license, and effort. Don't write code yet.

For **Continue Work**, see [Continue any session](#continue-any-session) above. Checkpoints are optional on one machine and needed for a move to another one; the [setup guide](skills/continue-work/references/SETUP.md) covers both.

## More

- [Detailed installation, usage, and package-building guide](docs/INSTALLATION.md)
- [Continue Work setup and daily use](skills/continue-work/references/SETUP.md)
- [Reuse Scout attribution and upstream MIT notice](skills/reuse-scout/THIRD_PARTY_NOTICES.md)
