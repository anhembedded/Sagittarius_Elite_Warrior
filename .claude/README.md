# `.claude/` — the manifest

Everything an AI session on this repository is given, and what loads it. This is the one tree for it: the rules, the map, the workflows, the subagents, the formats and the settings. `CLAUDE.md` at the repository root is the entry point Claude Code reads first; it imports the map and routes by task.

## Layout, and how Claude Code treats each part

| Path | What it is | Loaded by |
| :--- | :--- | :--- |
| `CLAUDE.md` (root) | entry point: routes by task, copies no rule | Claude Code, every session; imports `ONBOARDING.md` |
| `ONBOARDING.md` | the map: what loads when, lifecycles, authority, principles | the import above, every session |
| `rules/` | norms, one topic per file, every clause tagged with its enforcer; `rules/pitfalls/` holds the traps that produced broken code here | every session when the front matter has no `paths:`; on opening a matching file when it does (Claude Code discovers the directory recursively) |
| `skills/<name>/SKILL.md` | workflows: the review checklist, the two scheduled audits, the `EPIC-025` executor; a skill keeps its scripts and data beside it | the user with `/<name>`, or Claude from the `description` |
| `agents/<name>.md` | subagents that run in their own context, with their own tools and a preloaded skill | delegation, or `@<name> (agent)` |
| `templates/` | the formats: task, bug report, case study, epic, decision record | nothing loads them; a writer copies one and deletes its front matter |
| `settings.json` | project settings shared by every session: permission rules for the gate commands and the repository scripts (no hooks: the user removed the `SessionStart` one on 2026-09-17) | Claude Code |

Not here, on purpose: `Docs/CASE_STUDIES/` (knowledge for people and agents alike, indexed and guarded where the other design documents live; the one-line form of each study is a pitfall under `rules/pitfalls/`), and `.github/PULL_REQUEST_TEMPLATE.md` (GitHub fills it in). The engine repository keeps its own tree under `.agents/`; `ONBOARDING.md` §9 says which wins.

The platform's own description of these mechanisms: [memory and rules](https://code.claude.com/docs/en/memory), [skills](https://code.claude.com/docs/en/skills), [subagents](https://code.claude.com/docs/en/sub-agents), [settings](https://code.claude.com/docs/en/settings), [hooks](https://code.claude.com/docs/en/hooks-guide).

## Inventory

Derived from the tree: `python3 scripts/render_claude_manifest.py` prints it from each file's front matter, and `tests/unit/architecture/test_claude_tree_is_wired.py` fails when this table differs from that output. Never edit the rows by hand — change the file's front matter and re-render.

<!-- manifest:begin -->
| Path | Kind | Loads | What it is |
| :--- | :--- | :--- | :--- |
| `ONBOARDING.md` | map | imported by `CLAUDE.md`, every session | The process map for any AI agent on Sagittarius Elite Warrior — layout, lifecycles, the real verification commands, authority, principles, and where the traps live. Imported by CLAUDE.md, so it is in context every session. |
| `settings.json` | settings | Claude Code, every session | 8 permission rules |
| `rules/architecture-rule.md` | rule | `src/**/*.py` | Layers, ports and explicit contracts, CQRS, one abstraction per file, event placement, seams. Loads by path for every src/ file. |
| `rules/async-ui-action-rule.md` | rule | `src/**/*presenter*.py`, `src/**/*coordinator*.py` | Action identity, stale-callback fencing and cooperative cancellation for every background task started from the UI; the Coordinator pattern. |
| `rules/bug-fix-rule.md` | rule | every session | Root cause first, never a hotfix, log evidence, regression test before the fix at the right tier, kept forever, a report, and a case study when the gate was green. |
| `rules/ci-rule.md` | rule | every session | The one gate, its two-tier cadence, the diagnostic modes, the four test levels, failure handling, and the mandatory log scan. |
| `rules/code-quality-rule.md` | rule | `src/**/*.py`, `scripts/**/*.py` | Typing, readability, immutability, and the hard rules — no magic numbers, no nested loops, no God objects, no lazy imports, Single-Scope Cohesion. |
| `rules/commit-rule.md` | rule | every session | How a commit is made — Conventional Commits, atomic changes, the AI trailer, what never gets committed. Whether a commit, push or merge is allowed is ONBOARDING.md §7. |
| `rules/domain-truth-rule.md` | rule | `src/domain/**/*.py`, `src/modules/*/domain/**/*.py`, `src/modules/*/application/**/*.py` | The system never lies about what it did — real coverage, real exchange filters, immutable snapshots, distinct trading facts, a UI that promises only what the engine delivers. |
| `rules/install-rule.md` | rule | `requirements.txt`, `pyproject.toml`, `scripts/**`, `.github/workflows/**` | How the engine and dependencies are installed, the Python floor, and the rule that a missing tool is installed rather than reported. |
| `rules/logging-rule.md` | rule | `src/**/*.py`, `scripts/**/*.py` | Where a log line goes so one reproduce-and-send cycle locates a root cause; namespace, levels, tags, dev/debug modes. |
| `rules/report-rule.md` | rule | every session | Every report to the user — context, one diagram, the numbers with targets; Vietnamese in chat, English in the repository. |
| `rules/testing-rule.md` | rule | `tests/**/*.py` | How to write a test that can fail — what each level proves, no sleeps, invariants, boundary analysis with mutation checks, doubles from the interface, wiring asserted against the real graph. |
| `rules/ui-presentation-rule.md` | rule | `src/presentation/**/*.py`, `src/modules/*/ui/**/*.py`, `src/support/ui_kit/**/*.py`, `src/support/charting/**/*.py` | QtWidgets only, the OS theme, the seven desktop UX principles, MVP layout, preview.py, sizing, tables, icons, terminology. |
| `rules/pitfalls/source.md` | rule | `src/**/*.py` | Traps that produced broken source here — one line each, with the bug id. Loads with every src/ file. |
| `rules/pitfalls/tests.md` | rule | `tests/**/*.py` | Traps that produced broken tests here — one line each, with the bug or case-study id. Loads with every tests/ file. |
| `rules/pitfalls/ui.md` | rule | `src/presentation/**/*.py`, `src/modules/*/ui/**/*.py`, `src/support/ui_kit/**/*.py`, `src/support/charting/**/*.py` | Traps that produced broken UI code here — one line each, with the bug id. Loads with every presentation, module UI, ui_kit and charting file. |
| `skills/epic-025/SKILL.md` | skill | `/epic-025`, or Claude from its description | Execute one verified step of EPIC-025, the split of the application into bounded-context modules, when the user hands over the next step — reading order, the module-split invariants with their check commands, the per-step checklist, when and how to ask. On demand only. |
| `skills/pr-review/SKILL.md` | skill | `/pr-review`, or Claude from its description | Review a pull request, a branch, or an uncommitted diff in this repository against the repository's own rules — scope, architecture, code quality, tests, verification evidence, guards and baselines, bookkeeping. Use when asked to review a PR, to check a diff before merging, or to audit a branch somebody else wrote. |
| `skills/process-drift/SKILL.md` | skill | `/process-drift`, or Claude from its description | Audit whether the written process still matches what the repository does — rule contradictions, stale claims, quotations the cited file never contained, mechanisms the tree no longer has, board orphans, reference rot. Runs on a schedule (every 3 days) and leaves one dated file under Tasks/reports/process_drift/ whether or not it found anything. |
| `skills/test-health/SKILL.md` | skill | `/test-health`, or Claude from its description | Audit whether this repository's tests are still trustworthy — empty and vacuous tests, silent skips, tiers excluded from CI, allowlists with no completeness guard, duplicated fixtures, tests guarding deleted code, and rule clauses nobody enforces. Use on a schedule (every 3 days), before a release, after a large refactor, or whenever CI is green but bugs still reach users. |
| `agents/reviewer.md` | agent | delegation, or `@reviewer (agent)` | Independent, read-only review of a pull request, a branch or the uncommitted diff against this repository's own rules, using the pr-review skill in a context that did not write the change. Use before opening a pull request, when asked to review or audit a diff, or when a change touches a guard, a baseline or a rule. It reports findings; it never edits, commits or merges. |
| `templates/bug-report.md` | template | on demand, copied | The format of a bug report under Tasks/bug_report/incomplete/ (bug-fix-rule.md §7). Copy it, fill every brace, delete this front matter. |
| `templates/case-study.md` | template | on demand, copied | The format of a case study under Docs/CASE_STUDIES/ — why the gate was green while it was broken. Three required sections, 35 lines at most, the check ships in the same commit. Copy it, fill every brace, delete this front matter, add the index row. |
| `templates/decision.md` | template | on demand, copied | The format of a decision record (ADR, Nygard 2011) inside an epic — DECISION_{date}_{slug}.md. Copy it, fill every brace, delete this front matter. |
| `templates/epic.md` | template | on demand, copied | The format of an epic's README.md under Tasks/epics/EPIC-nnn_slug/ (Tasks/epics/README.md). Copy it, fill every brace, delete this front matter. |
| `templates/task.md` | template | on demand, copied | The format of a task file under Tasks/backlog/ (ONBOARDING §3). Copy it, fill every brace, delete this front matter. |
<!-- manifest:end -->

## Adding one

- **A rule**: a file under `rules/` with a `description:` and, when it belongs to a kind of file, a `paths:` list of globs that match tracked files; a row in `CLAUDE.md`'s table and in `ONBOARDING.md` §1; every clause tagged `[gate]`, `[guard: file]`, `[review: row]` or `[eye]`. A rule without `paths:` costs every session; the guard holds the total under its ceiling, which only falls.
- **A pitfall**: one line in the `rules/pitfalls/` file for its area, with the bug or case-study id.
- **A skill**: `skills/<name>/SKILL.md` whose `name` is the directory name; a scheduled one obeys `ONBOARDING.md` §13.
- **A subagent**: `agents/<name>.md` with `name`, `description`, `tools`, and the skill it runs.
- **A template**: a file under `templates/` with a `description:`; the rule that governs the document points at it.
- Then `python3 scripts/check_skill_prompt_references.py` (every cited path must exist) and the re-rendered inventory above.
