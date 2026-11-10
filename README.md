# Skills

Two reusable agent skills: **find an existing foundation before building**, and **resume interrupted work without blindly repeating actions**.

| Skill | What it does | Use it when |
|---|---|---|
| [reuse-scout](skills/reuse-scout/SKILL.md) | Decomposes a project or blocker, searches repositories/packages/tooling, ranks existing foundations, and separates reusable parts from genuine gaps. | Before building a feature, choosing a library, forking a project, or investigating a problem others may have solved. |
| [continue-work](skills/continue-work/SKILL.md) | Reads a saved checkpoint and handover, reconciles them with available evidence, and continues only outstanding authorized work. | After a crash, a lost response, a fresh session, or a deliberate handoff between agents. |

Both are **instruction-based skills**, not applications or tool installers. Installation does not grant filesystem access, browsing, credentials, permission to send anything, or access to a private repository.

> **Compatibility is not one-size-fits-all.** CLI/IDE agents can usually discover a skill folder. Some web products have native skill or plugin installation; others can only use the instructions as an uploaded/pasted reference. The sections below distinguish those routes instead of promising a universal installer.

## Get the collection

```text
git clone https://github.com/MdRaf1/skills.git
```

For a private repository, use a GitHub account with access through your normal Git/GitHub authentication. A link pasted into an AI chat does not make private files readable. Never paste a token into a chat, checkpoint, or committed URL.

Cloning this catalog does **not** automatically install its skills into every project or AI tool.

## Downloads and package formats

| Skill/package | ZIP | `.skill` |
|---|---|---|
| Continue Work | [continue-work.zip](dist/continue-work.zip) | [continue-work.skill](dist/continue-work.skill) |
| Reuse Scout | [reuse-scout.zip](dist/reuse-scout.zip) | [reuse-scout.skill](dist/reuse-scout.skill) |
| Both skills as a portable plugin | [skills-plugin.zip](dist/skills-plugin.zip) | — |

On GitHub, open a package and use **Download raw file**. Choose the file type your host explicitly supports.

- **`SKILL.md`** is the instruction entry point. Its spelling and capitalization matter.
- **A skill folder** includes that entry point plus any templates, references, metadata, and notices. Copy the whole folder, not just the Markdown file, for native installation.
- **A `.zip` and its matching `.skill` file contain identical ZIP bytes.** The latter is a distribution filename, not a universal import API. Use `.zip` when an uploader asks for ZIP.
- **`plugin.json`** and `skills/` form an instruction-only portable plugin. The plugin ZIP contains that layout. It is prepared for compatible installers/distribution systems; this repository has not been published to a vendor plugin directory or installed into any account.

## Install in CLI and IDE agents

In the table, `<name>` is `continue-work` or `reuse-scout`. Copy `skills/<name>/` from this catalog into the indicated directory of the **project you want to work on**. For personal installation, copy into the user-level directory instead.

Inspect an existing destination before replacing it. Preserve project instructions, local changes, and checkpoints. Do not add nested duplicate folders such as `continue-work/continue-work/`.

| Tool | Project installation | Personal installation | How to use |
|---|---|---|---|
| **Claude Code** | `.claude/skills/<name>/SKILL.md` | `~/.claude/skills/<name>/SKILL.md` | `/continue-work` or `/reuse-scout` |
| **Codex CLI / IDE extension** | `.agents/skills/<name>/SKILL.md` | `~/.agents/skills/<name>/SKILL.md` | `$continue-work`, `$reuse-scout`, or select through `/skills` |
| **Cursor Agent** | `.cursor/skills/<name>/SKILL.md` or `.agents/skills/<name>/SKILL.md` | `~/.cursor/skills/<name>/SKILL.md` or `~/.agents/skills/<name>/SKILL.md` | Select `/continue-work` or `/reuse-scout` in Agent chat |
| **VS Code: GitHub Copilot local agent** | `.github/skills/<name>/SKILL.md` | `~/.copilot/skills/<name>/SKILL.md` | Select the skill from chat's `/` menu; `/skills` opens configuration in the local harness |
| **Gemini CLI** | `.gemini/skills/<name>/SKILL.md` or `.agents/skills/<name>/SKILL.md` | `~/.gemini/skills/<name>/SKILL.md` or `~/.agents/skills/<name>/SKILL.md` | Check `/skills list`; ask it to activate/use the named skill and review the activation consent |
| **OpenCode** | `.opencode/skills/<name>/SKILL.md` | `~/.config/opencode/skills/<name>/SKILL.md` | Ask it to load the named skill through its `skill` tool, then provide the task |

`~` means your home directory on the machine running the tool. On Windows, use the corresponding directory under your Windows user profile.

### Example installed layout: Codex

```text
your-project/
  .agents/
    skills/
      continue-work/
        SKILL.md
        agents/openai.yaml
        references/SETUP.md
        snippets/...
        templates/...
      reuse-scout/
        SKILL.md
        agents/openai.yaml
        THIRD_PARTY_NOTICES.md
        LICENSE.upstream.txt
```

### An installation request you can give a repository-connected agent

Replace `<CATALOG_ROOT>` and `<DESTINATION_SKILLS_DIRECTORY>` with real paths from the table. This installs skill instructions only; it does not authorize running either skill.

```text
Install continue-work and reuse-scout from <CATALOG_ROOT>/skills into
<DESTINATION_SKILLS_DIRECTORY> for this project.

Read the source files and existing project instructions first. Copy each whole
skill folder. Preserve its supporting files. If a destination already exists,
show the difference and ask before replacing it. Do not touch global settings,
credentials, permissions, unrelated files, or an existing checkpoint. Do not
run either skill, commit, or push. Report exactly what was installed and how
to select it in this host.
```

Restart the agent if discovery does not refresh. Gemini CLI also documents `/skills reload`. Do not assume `/skills` or `/name` has the same meaning in every product.

### Invocation and safety controls

- Codex's supplied `continue-work/agents/openai.yaml` sets `policy.allow_implicit_invocation: false`: recovery must be explicitly selected.
- `reuse-scout` is discoverable by its description; hosts that support implicit selection may suggest/load it before building. Its instructions stop at a report rather than implementing the chosen solution.
- Claude Code, Cursor, the VS Code local harness, and current OpenCode document `disable-model-invocation: true`. If you want an additional explicit-only guard for `continue-work` in one of those clients, add that field to the YAML frontmatter of the **installed copy**, retaining `name` and `description`. Keep the generic web-upload package unchanged for portability.
- Even if a host loads a skill automatically, `continue-work` requires an explicit resume/inspection request and current authorization. It must not resume an old task just because its instructions were loaded.
- Keep ordinary permission and consent prompts enabled. Do not use blanket approval or installation-consent bypass flags for these skills.

### Other CLI/IDE clients and remote agents

Pi, Antigravity, GitHub Copilot CLI, Cline, Windsurf, Aider, and other clients have their own versions and configuration surfaces. Do not treat the VS Code settings above as configuration for every independent client, or assume every client scans `.agents/skills`.

If the client documents native Agent Skills, use its documented folder and invocation mechanism. Otherwise, point it explicitly at the relevant `SKILL.md` and ask it to read and follow it for the task. This is **instruction-file use**, not a claim of native skill discovery.

Cloud/remote agents need the instructions installed or made available in their remote workspace. Local files are not automatically present there. Account access, skill sync, and repository access are separate features; consult the host's documentation.

## Install or use in web and desktop AI tools

### Claude.ai: native skill upload

1. Download one skill's **ZIP** from the table above. It contains a named folder with `SKILL.md` and its resources.
2. In Claude, open **Customize → Skills → + → Create skill → Upload a skill**.
3. Upload the ZIP, review it, and enable the skill.
4. Ask, for example, **“Use reuse-scout to evaluate existing foundations for this project…”** or **“Use continue-work to inspect the checkpoint and handover I attached…”**.

The official article requires the **Code execution and file creation / Create and edit files** capability; availability can depend on account and organization policies. If the upload controls are unavailable, use the reference fallback below instead of inventing a missing menu.

An ordinary chat attachment is not the same as installing an enabled skill. The CLI's `/name` command is not presented here as a universal Claude.ai shortcut. In Claude Desktop, distinguish account/chat skill features from the Code experience; the latter follows Claude Code's project/file workflow.

### ChatGPT web: native plugin route, or reference fallback

Current OpenAI documentation distinguishes these routes:

- **Standalone skills:** supported in the ChatGPT desktop app, Codex CLI, and IDE extension.
- **Plugin-bundled skills:** supported across ChatGPT web, desktop, and mobile. An instruction-only skill plugin does not inherently require an app or MCP server.

This catalog includes the portable root [`plugin.json`](plugin.json), automatic root `skills/` layout, and [`dist/skills-plugin.zip`](dist/skills-plugin.zip). Use them through a **supported plugin installation/distribution workflow available to your account or organization**. Once the plugin and its skills are available, type `@` to select a skill and give the task.

A generic “upload this standalone ZIP to ChatGPT web” installation route, or direct installation from this private GitHub URL, has **not** been established here. The prepared plugin package is not a claim that your account can import an arbitrary repository or ZIP. See the official [plugin packaging](https://developers.openai.com/plugins/build/plugins) and [skills](https://developers.openai.com/codex/skills/) documentation for your environment's supported distribution route.

For immediate use when native installation is unavailable, use the instruction-file fallback below. In a custom GPT or project, attaching a file as knowledge alone does not ensure it will be applied: explicitly request that the instructions be used.

### Gemini web/Gems, Copilot web, and other chat products

This catalog does not claim a native `SKILL.md` installer for every web product. If the product supports file attachments, reusable instructions, or project knowledge, use the skill as a reference and explicitly request its use. Otherwise paste the skill text into the conversation.

This also works as a fallback in ChatGPT or Claude when native skill installation is unavailable. It does **not** add browsing, tools, persistent storage, local execution, or repository permissions.

### Universal instruction-file fallback

Upload **`skills/<name>/SKILL.md` itself**, not an opaque ZIP that the host may not inspect, or paste its contents. Supply referenced resources separately when needed. Then say:

```text
Use the attached/pasted SKILL.md as guidance for this task: <your task>.

Adapt the steps to this chat's available capabilities. Ask for missing inputs.
Do not assume access to my private repository, local filesystem, browser,
credentials, or external tools. State what you could not verify. Ask before
external actions. Do not claim that a chat attachment was saved into my repo.
```

For `continue-work`, also supply the checkpoint, handover, and only the relevant redacted files or outputs. Expect a **snapshot-based review** unless the host truly has authorized access to the live project. Save any proposed updated checkpoint into the actual project yourself when the host cannot do so.

For `reuse-scout`, enable the host's available search/browsing tools or supply source material. If a channel is unavailable, the report should name that limitation—not fabricate current findings or pretend the search found no matches.

## Use Reuse Scout

### Before building

After loading/selecting the skill, ask:

```text
Use reuse-scout before I build a local-first notes application with sync.
Constraints: Windows and Linux, self-hostable, commercially usable license,
and a small maintenance burden. Rank the closest existing foundations,
identify what each covers and what is missing, and do not write code yet.
```

Expected output: a ranked recommendation, sources, coverage and gaps, health/freshness, access and data risks, cost, license, and adaptation effort. It recommends **Adopt, Extend, Compose, Reference, or Build only the remaining gap**, then asks you to choose a path.

### When blocked

```text
Use reuse-scout in blocker mode for this problem:
<exact error or observed behavior>
Library/platform and version: <actual version>
What I already tried: <verified attempts>
Find the best-supported fix or workaround, the relevant versions and evidence,
and how to verify it. Do not implement anything yet.
```

A quick scout targets roughly ten tool calls; a deeper scout has a larger bounded budget. Tool names and model-tier hints in the source are capability preferences, not guaranteed APIs in every host. Use the host's actual tools and permissions. The skill is research/reporting only: it does not authorize cloning and running arbitrary installers or building the chosen solution.

## Use Continue Work

### Initialize once per project

Read the bundled [setup and daily-use guide](skills/continue-work/references/SETUP.md). It includes a safe setup prompt, standing instructions, templates, privacy exclusions, and a fresh-session test.

The key steps are:

1. Install the skill in the host.
2. Add the checkpoint-maintenance rule to instructions the host actually loads for the project.
3. Initialize that project's `.scratch/continuation.json` and linked handover without overwriting existing state.
4. Work normally, saving verified state at meaningful boundaries.

The supplied checkpoint is intentionally idle and uninitialized. Installing a skill alone does not create a record of previous conversations.

### Save before stopping

```text
Checkpoint the current work and stop. Save all outstanding requests,
verified completed work, the exact next step, restrictions, in-flight
attempts, pending writes, blockers, worker state, and actual test results.
Do no further task work after saving.
```

### Resume in a fresh session

Explicitly select the skill using your host's mechanism. For example, use `$continue-work` in Codex or `/continue-work` in Claude Code. For a first check, request:

```text
Use continue-work to inspect the checkpoint and actual available evidence only.
Do not resume the task or change files. Report the task, outstanding requests,
next step, and any uncertainty or mismatch.
```

Once that matches the saved work, explicitly ask to continue within the existing scope and permissions.

**Limits:** this is checkpoint-based recovery, not native conversation resume, automatic receipt logging, a transaction system, or a gateway fix. It has no old-session-ID lookup. Missing evidence stays missing. A lost response is not proof that a send, deployment, push, migration, or submission failed. Do not run two agents against the same checkpoint simultaneously; this version has no concurrent-writer coordination.

## Repository layout

```text
plugin.json                         portable instruction-only plugin manifest
skills/
  continue-work/
    SKILL.md
    agents/openai.yaml
    references/SETUP.md
    snippets/...
    templates/...
  reuse-scout/
    SKILL.md
    agents/openai.yaml
    THIRD_PARTY_NOTICES.md
    LICENSE.upstream.txt
dist/
  continue-work.zip
  continue-work.skill
  reuse-scout.zip
  reuse-scout.skill
  skills-plugin.zip
scripts/
  package_skills.py
```

No live checkpoints, user conversations, application records, or credentials belong in this catalog.

## Build and verify packages

The skills themselves need no Python runtime. Maintainers use Python 3's standard library to rebuild distribution archives:

```text
python -I scripts/package_skills.py
python -I scripts/package_skills.py --check
```

Use `python3` instead of `python` if that is your platform's Python 3 command. The build command regenerates the named files under `dist/`; `--check` verifies existing packages without rewriting them.

The builder uses explicit resource allowlists, rejects symlinks/unexpected skill resources, checks basic entry-point metadata and the uninitialized checkpoint, fixes archive timestamps, verifies archived bytes against source, and checks ZIP/`.skill` parity. Add a deliberate allowlist entry when adding a new resource.

These checks are **package checks**, not proof that each vendor imported or executed the skills successfully. Run a harmless task or read-only recovery preview in the actual destination host after installation.

## Attribution and compatibility notes

- `reuse-scout/SKILL.md` preserves the supplied Reuse Scout instructions. The supplied standalone `.skill` package and folder were checked for matching instruction content before consolidation.
- Reuse Scout credits **ECC's MIT-licensed `search-first` skill**. The credit and [upstream license notice](skills/reuse-scout/LICENSE.upstream.txt) are retained in source and packages; see [third-party notices](skills/reuse-scout/THIRD_PARTY_NOTICES.md). No blanket license for every addition in this catalog is implied by that upstream notice.
- The supplied Reuse Scout folder originally had a Claude plugin wrapper. The reusable content is now exposed as standard skill folders plus a separate portable plugin manifest; product-specific wrappers are not universal AI configuration files.
- `continue-work` is the lightweight checkpoint variant, adapted to distinguish repository-connected execution from web-chat snapshot review. It does not include the original project's automatic logging hooks.
- Installation guidance was checked against official documentation on **2026-11-10**. Product versions, account eligibility, managed policies, and available tools can change. Gemini CLI's current documentation includes account/availability changes; check it for your setup rather than assuming every account can use the same client.

### Official documentation

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Using skills in Claude](https://support.claude.com/en/articles/12512180-using-skills-in-claude)
- [Codex and ChatGPT skills](https://developers.openai.com/codex/skills/)
- [Portable plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [Cursor skills](https://cursor.com/docs/context/skills)
- [VS Code agent skills](https://code.visualstudio.com/docs/agent-customization/agent-skills)
- [Gemini CLI skills](https://geminicli.com/docs/cli/skills/)
- [OpenCode skills](https://opencode.ai/docs/skills/)
