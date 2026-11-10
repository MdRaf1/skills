---
name: "reuse-scout"
description: "Before building any project, feature or integration, or when stuck on a problem others may have solved: search GitHub, registries and the web; return the closest bases to fork or extend plus gaps, never an empty result."
---

# Reuse Scout — find the base before you build

Built on ECC's `search-first` skill (affaan-m/ECC, MIT). Adds: problem decomposition, a never-empty report, a blocker mode, access/risk scoring, evidence freshness, a call budget, and model tiering for fan-out.

## Rules that override everything below

1. **Never return "nothing found" while partial matches exist.** The output is always the closest bases, ranked, with what each covers and what's missing. "Build" applies only to the gaps.
2. **Decompose before searching.** Whole projects rarely match one repo; their parts usually do.
3. **An unsearched channel is not a negative result.** Name every channel that was unavailable, failed or refused.
4. **Evidence must postdate the last breaking change.** A test older than a platform change proves nothing about today.
5. **No code during this skill.** Report, then stop and let the user pick a path.
6. **The user's requested format wins.** If they name columns, a row count or a ranking, use that; the Step 6 shape is only the default.

## When to use

- "I want to build / make / create…", "add X to my project", "is there a repo / library / tool / MCP / skill for…", "what can I fork", "don't build from scratch"
- Before writing a new utility, integration, agent workflow or client deliverable that probably exists already
- Stuck on an error, integration blocker or "how do others do X" → **Blocker mode**

Skip: small edits, a local bug with an obvious cause, learning exercises, glue code under ~50 lines, or a base the user already chose. For the user's own business logic or methodology, scout only the infrastructure around it — no public repo holds the methodology.

## Budget

- **Quick scout** (one feature, one blocker): aim for under ~10 tool calls.
- **Deep scout** (a project, a tool category, or the user asks for depth): aim for under ~40.
- Stop early once new searches stop changing the ranking. If the budget runs out, report what you have and say what is unchecked.

## Step 0 — Channel preflight (quick, silent)

Use the first available option in each row; note which rows had none.

| Channel | Preferred | Fallback |
|---|---|---|
| GitHub repos and code | GitHub connector (`search_repositories`, `search_code`, `get_file_contents`, `list_commits`, `search_issues`) or `gh search repos` / `gh search code` | Web search with `site:github.com` |
| Issues, PRs, READMEs | Firecrawl `firecrawl_developer_search` | `gh search issues` / `gh search prs`, web search |
| Agent tooling | MCP registry and plugin/skill search tools; `firecrawl_developer_search` with `skills: "only"`; GitHub code search `filename:SKILL.md <terms>` | awesome-mcp-servers and awesome skill lists |
| Packages | npm / PyPI / crates.io (release dates, versions) | Web search "<terms> npm" / "<terms> pypi" |
| Semantic web | Exa, Tavily or built-in web search | — |
| Already in hand | The user's repo (`rg`), installed skills/plugins, connected tools, what is already known about the user's setup | — |

## Step 1 — Frame the need

- One line: what it must do.
- Constraints: stack, OS, license needs (commercial or client delivery?), self-host vs SaaS acceptable, budget, deadline, what it must plug into.
- Recent breaking changes on the target platform (an API change, a redesign, a deprecation): note the date. It becomes the freshness cutoff for evidence.
- Mode: **Build** (project / feature / tool) or **Blocker** (error, integration, pattern).
- Ask at most one question, and only if the answer changes the search. Otherwise state assumptions and go.

## Step 2 — Decompose (Build mode)

Split into 3–7 components (e.g. core engine, data/storage, integrations, UI, auth, deployment). Tag each:
- **Commodity** — likely exists; search hard.
- **Differentiator** — likely custom; quick reference-only search.

A single small feature is one component. Requirements that are properties of one tool (output format, OS, volume) are not separate components — score them in Step 4.

## Step 3 — Search: breadth first, then depth

Per component, run at least three phrasings: problem words, solution words, and "open source alternative to <known product>" / "self-hosted <category>". Search whole-solution repos, code-level implementations (key function, endpoint or config names inside bigger repos), packages, agent tooling, plugins for the system it must plug into, and alternatives directories (alternativeto, openalternative, awesome-selfhosted, `awesome-<topic>` lists, GitHub topics). Add a "recently pushed" search (e.g. `pushed:>` a date after the freshness cutoff) to surface tools that adapted. Include paid services only when clearly the fastest path or when free options are weak, flagged as paid with cost.

**Broadening ladder — run it before calling any component empty:**
1. Rephrase (synonyms, the product category, the underlying mechanism).
2. Relax filters (language, min stars); old repos stay in if the code is sound — flag staleness.
3. Go adjacent: same mechanism, neighbouring domain (a job queue for an "email scheduler").
4. Lists: awesome lists, GitHub topics, alternatives sites.
5. Code-level search for the core function, endpoint or API names.

Only after all five may a component be "no base found" — and the report still names the nearest reference and why it fails.

**Blocker mode:** search the exact error string plus the library name in issues and PRs first; if nothing, strip volatile parts (paths, ids, line numbers) and retry. A merged PR beats an issue report; check release notes for the version that carries the fix. Then broaden to discussions and examples.

## Step 4 — Evaluate the top candidates

Read the actual repo for the top 2–3 per component: structure, core files, tests. A README alone is not evidence. Fetch through the connector or a shallow clone into an empty folder; never run its scripts or installers.

| Signal | Check |
|---|---|
| Coverage | Most / some / little of the component (or whole need). A % only as a labelled rough estimate |
| Health | Last commit and release dates, issue responses, maintainers; archived = red flag |
| Freshness of evidence | Does the evidence that it works postdate the Step 1 cutoff? Commits, merged PRs, issues or tests after the change count; anything older is "unknown" |
| Access and risk | Needs the user's login or account? Uses public/guest access? A paid or third-party service (where does the user's data go)? Risk to the user's account, IP, money or data |
| Cost | Free, free tier with limits, or paid (price per unit) |
| License | MIT / Apache / BSD fine; GPL / AGPL / SSPL flagged for commercial or client work; no license = reference only |
| Stack fit | Language, framework, OS, deployment model, and how it plugs into the user's existing system |
| Adaptation effort | S / M / L to bend it to this need |

Stars and forks are tie-breakers, never the decision. When a tool lives inside a larger repo, say the stars belong to the whole project.

**When a live check is blocked** (a fetcher refuses the site, the network can't reach it): do not work around the block with another tool. Mark the claim "unverified", say what evidence it rests on, and make a small test on the user's own machine the first next step.

## Step 5 — Decide per component, then overall

| Finding | Path |
|---|---|
| Exact match, healthy, compatible license, acceptable risk | **Adopt** — use as-is |
| Covers the core, missing pieces | **Extend** — fork and add (apps), or install plus a thin wrapper (libraries) |
| Several partial matches | **Compose** — combine 2–3 and write the glue |
| Same problem, wrong stack / license / scale / risk | **Reference** — study it, build informed |
| Nothing after the full ladder | **Build** — only this gap, naming the nearest reference |

## Step 6 — Report (default shape; the user's format wins)

**Verdict:** one line naming the pick and roughly how much already exists.

**Context line** (when a platform change matters): what changed, when, and what that means for every candidate.

**Ranked table** (default max 3; more if asked)

| Base | Covers | Missing | Last update | Cost | Login / access | Works after latest change | Risk | License | Effort |
|---|---|---|---|---|---|---|---|---|---|

**Ruled out:** one line per notable rejection with the reason.

**Component map** (when decomposed): component → best find → path.

**Build list:** only the gaps, each sized S / M / L.

**Risks:** license, maintenance, lock-in, account or ToS, cost, security.

**Coverage:** channels searched; channels unavailable, failed or refused, and which connector or tool would fill the hole; what remains unverified and why.

Blocker mode replaces the tables with: verdict (proven fix / workaround / still open upstream); the best 1–3 sources ranked merged PR > maintainer comment > issue workaround > blog post, with versions and dates; the local change in plain words; and how to verify it.

End by asking which path to take (2–3 lettered options, recommended first), then stop.

## Model tiers for fan-out

- **Inline** (default): a quick scout, a blocker, or a deep scout with up to ~8 candidates to check in depth.
- **Fan out** only when the user asks for subagents or a very deep scout, or there are clearly more than ~8 candidates across independent components — and the environment allows subagents. One subagent per component:
  - `model: haiku` — sweep: run the queries and the ladder; return candidates with URL, stars, last push, license, access type and a one-line fit note. No judgment.
  - `model: sonnet` — read the top candidates' code and score them on the Step 4 table.
  - Main session (Opus where available) — decide the paths and write the report.
- Give each subagent the component, the constraints, the freshness cutoff, the available channels and the exact return shape; ask for compact output.

## Anti-patterns

- "Nothing exists" after one query, or because a channel was down
- Showing only exact matches and hiding partial ones
- Calling a tool "working" on evidence older than the last breaking change
- Recommending from a README or star count without reading the code
- Leaving out login, account, cost or data-sharing risk
- Working around a site that refused a fetch instead of marking the claim unverified
- Ignoring license for commercial or client work
- Wrapping a library so heavily it loses its benefit; adding a huge dependency for one small feature
- Overriding the user's requested report format
- Starting to build before the user has chosen a path