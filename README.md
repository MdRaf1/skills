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

The [combined plugin ZIP](https://github.com/MdRaf1/skills/releases/latest/download/skills-plugin.zip) remains available as an optional download. Each `.skill` file contains the same ZIP bytes as its matching `.zip`.

## Install

**Let your AI handle the setup.** Open the project where you want the skill in Claude Code, Codex, Cursor, or another agent that can edit project files. Paste **one** of these prompts.

### Install Reuse Scout

```text
Install only reuse-scout from: https://github.com/MdRaf1/skills/tree/main/skills/reuse-scout

Read the repository's installation guide and the skill first. Copy the whole skill folder into this AI tool's project-level skills directory. Ask if the host or target project is unclear. Preserve supporting files and ask before replacing existing files. Do not install another skill, change global settings, or run reuse-scout. Stop after installation and tell me how to invoke it.
```

### Install Continue Work

```text
Install only continue-work from: https://github.com/MdRaf1/skills/tree/main/skills/continue-work

Read the repository's installation guide and the skill first. Copy the whole skill folder into this AI tool's project-level skills directory. Ask if the host or target project is unclear. If checkpointing is not configured, follow its references/SETUP.md for this project. Preserve existing rules and state; ask before replacing anything. Do not install another skill, change global settings, or resume any task. Verify the setup and tell me how to invoke it.
```

If the agent cannot fetch GitHub, give it the downloaded folder for the **chosen skill**. These prompts do not install anything into a web account or give a chat access to your computer.

### Web apps or manual installation

- **Claude web:** download the chosen skill's ZIP, then open **Customize → Skills → + → Create skill → Upload a skill**. Upload and enable it. Availability depends on your account and file-creation capability.
- **ChatGPT, Gemini, or other web chats:** if native installation is unavailable, upload or paste that skill's `SKILL.md` and ask the AI to use it for your task. This is instruction-based use, not a native installation.
- **Manual CLI/IDE setup:** copy just the chosen skill folder into your tool's skills directory. See the [installation paths and web compatibility guide](docs/INSTALLATION.md).

## Use

- **Claude Code:** `/reuse-scout` or `/continue-work`.
- **Codex:** `$reuse-scout` or `$continue-work`.
- **Other tools:** use the invocation instructions reported during setup or in the [guide](docs/INSTALLATION.md).

After loading **Reuse Scout**, ask:

> Find the best existing foundations for a self-hosted notes app. Compare coverage, maintenance, license, and effort. Don't write code yet.

For **Continue Work**, finish the [one-time checkpoint setup](skills/continue-work/references/SETUP.md) if it was not done during installation. Before ending a session, ask the agent to save the current task, completed work, and exact next step. In a fresh session, invoke the skill to check the saved state and continue.

Continue Work needs saved evidence—it cannot recover work that was never recorded. For web use, attach the checkpoint, handover, and relevant files. Keep credentials out of those files, and verify uncertain sends or deployments before retrying.

## More

- [Detailed installation, usage, and package-building guide](docs/INSTALLATION.md)
- [Reuse Scout attribution and upstream MIT notice](skills/reuse-scout/THIRD_PARTY_NOTICES.md)
