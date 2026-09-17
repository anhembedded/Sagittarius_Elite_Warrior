# BOT-135 — One tree for the AI process: `.agents/` folded into `.claude/`, wired to the platform

**Status:** ✅ Done 2026-09-17
**Source:** the user, 2026-09-17 — *"tui đánh giá cấu trúc thư mục của AI vẫn chưa tốt, cần có rule, format, skill v.v... 1 vấn đề khác là có 2 dir cho AI .agents và .claude hãy gôm lại, tối ưu cho nền tảng claude"* ("the AI directory structure is still not good; it needs rules, formats, skills and so on. Another problem: there are two AI directories, `.agents` and `.claude` — merge them, optimised for the Claude platform"), then: *"ý tưởng của tui là kiểu sẽ có các file như là manifest, skills/ rules/ pitfalls/ case_studies/ templates/ v.v... hãy cân nhắc các dự án lớn và best practice"* ("my idea is files like a manifest, skills/, rules/, pitfalls/, case_studies/, templates/ and so on — weigh it against large projects and best practice").
**Risk:** 🟢 — documents move and one guard is replaced by another; no application behaviour changes. The one runtime effect is what Claude Code now loads by itself.
**Complexity:** 🟡 `M` — eighty files touched (`git diff --stat -M HEAD~1..HEAD`), most of them one path each; the design is in §2.

---

## 1. Context and problem

Two directories served the same purpose. `.agents/` held the map, the twelve rules and the audit briefs under a convention (`trigger: always_on`, `patterns:`) that no tool executed — an agent had to remember to read them. `.claude/` held six *pointer* files, one per path-scoped rule, because Claude Code does load `.claude/rules/*.md` and honours a `paths:` list there; a guard (`test_claude_rule_pointers_match_agents_rules.py`) kept the two in step. So every path-scoped rule existed twice (once as text, once as a pointer), every always-on rule existed only as a reading instruction, and `AGENTS.md`, a filename Claude Code never reads, listed everything a third time. The strategic review (`BOT-134`, P1 *mechanism over memory*) had already named the gap: six of ten principles rested on the agent having read and remembered a rule.

## 2. Design

The user's idea, weighed against what the platform documents and what large repositories do:

| The idea | What was done | Why |
| :--- | :--- | :--- |
| a **manifest** | `.claude/README.md`, with an inventory table **derived** by `scripts/render_claude_manifest.py` from each file's front matter and held to the tree by a guard | A manifest written by hand is a copy, and copies drift (Hunt & Thomas 1999, DRY); a derived one cannot. The same shape as `render_task_counts.py` and the board guard (`BOT-134` S4). A README rather than a YAML file: GitHub renders it, a reader opens it first, and nothing would read a YAML manifest |
| **rules/** | `.claude/rules/*-rule.md`, the twelve rules themselves, with the platform's own front matter: `paths:` for a rule that loads on a kind of file, none for a rule that loads every session | This is the mechanism Claude Code documents (`code.claude.com/docs/en/memory`): the pointer indirection and its guard disappear; a rule loads itself. Filenames keep the `-rule` suffix so every `ci-rule.md §1`-style citation in the history still resolves |
| **pitfalls/** | `.claude/rules/pitfalls/{tests,ui,source}.md` — the fifteen traps of `ONBOARDING.md` §8 split by the files they concern, each file path-scoped | A trap is read when it matters, not remembered: the UI traps load with UI files, the test traps with tests. Progressive disclosure (Nielsen 2006). The one trap that belongs to no file stays in §8 |
| **case_studies/** | **left in `Docs/CASE_STUDIES/`**; the manifest and the bug-fix rule point there; the one-line form of each study is a pitfall | Case studies are explanation for people and agents alike (Diátaxis), already indexed and guarded where the other design documents live; nothing under `.claude/` would load them, so moving them buys no mechanism and costs every link |
| **templates/** | `.claude/templates/{task,bug-report,case-study,epic,decision}.md`, each with a `description:` and brace placeholders; the governing rule points at its template | The formats were implicit in five places (ONBOARDING §3, bug-fix-rule §7, the case-study README, the epics README, the ADR convention of `EPIC-016`); now each is one file. The pull-request body goes where the platform fills it in: `.github/PULL_REQUEST_TEMPLATE.md` |
| **skills/** | the two audit briefs and the `EPIC-025` executor become `.claude/skills/<name>/SKILL.md` beside `pr-review` and `test-health` | Skills are the platform's unit for a workflow: invocable as `/name`, discoverable from the description, with scripts and data beside them |
| — | `.claude/agents/reviewer.md`: a read-only subagent preloaded with `pr-review` | A second reader in a context that did not write the change — the author's own pre-check before the independent review `ONBOARDING.md` §7 requires (Fagan 1976) |
| — | `.claude/settings.json`: permission rules for the gate commands; a `SessionStart` hook printing `git status --short --branch` shipped with it and was removed the same day at the user's word (*"bỏ hook SessionStart đi, giữ permission"*) | The map is imported by `CLAUDE.md` (`@.claude/ONBOARDING.md`), so it is in context without being remembered; §12.1's three commands stay the agent's to run |
| — | `AGENTS.md` and `Skills/README.md` deleted; the shared unattended-run rules become `ONBOARDING.md` §13 | Claude Code reads `CLAUDE.md`, not `AGENTS.md` (documented); one map instead of three indexes |

**What now loads every session** (measured by `scripts/measure_process.py`, held under a ceiling that only falls by `test_claude_tree_is_wired.py`): `CLAUDE.md`, the map, and the four rules without a file scope (`ci`, `commit`, `bug-fix`, `report`) — 363 lines. `logging-rule.md` and `install-rule.md` are path-scoped now; the one behavioural sentence of the latter (a missing tool is installed, never reported) lives in the map, §5.

## 3. Changes, per file

| File | Change |
| :--- | :--- |
| `.claude/rules/*-rule.md` | moved from `.agents/rules/`; front matter is `description` plus `paths` (the six former pointer scopes, `src/application/**` dropped because it matches nothing since `EPIC-025` PR 3.1c) |
| `.claude/rules/pitfalls/` | new, three files |
| `.claude/ONBOARDING.md` | moved; §1 says what loads when, §3–§4 point at the templates, §7 names the pull-request template and `settings.json`, §8 points at the pitfalls, §9 is "two rule trees", §13 holds the unattended-run rules |
| `CLAUDE.md` | imports the map; rows for pitfalls, templates, the pull-request template, the reviewer, the audits, the manifest |
| `.claude/README.md`, `scripts/render_claude_manifest.py` | the manifest and its renderer |
| `.claude/skills/{process-drift,epic-025}/SKILL.md` | moved from `.agents/Skills/*.prompt.md`, given front matter, links re-based |
| `.claude/agents/reviewer.md`, `.claude/settings.json`, `.claude/templates/*.md`, `.github/PULL_REQUEST_TEMPLATE.md` | new |
| `tests/unit/architecture/test_claude_tree_is_wired.py` | replaces the pointer guard: description on every file, every `paths:` glob matches a tracked file (`git ls-files`, `CS-005`), skill `name` equals its directory, the always-loaded ceiling, the manifest equals the renderer |
| `tests/unit/test_rule_navigation_is_complete.py` | scans `.claude/rules/**`, checks `CLAUDE.md` and the map, looks a nested rule up by its path |
| `scripts/check_skill_prompt_references.py` | reads `CLAUDE.md` and every `.md` under `.claude/` (so the map and the rules are checked for the first time; four placeholder paths became `{nnn}` patterns) |
| `scripts/measure_process.py`, `scripts/ci-local.ps1`, `scanned_roots_registry.py`, `test_skill_prompt_references_ask_git.py`, `test_case_study_index_is_consistent.py` | retargeted |
| 40 documents and 5 source comments | `.agents/…` citations rewritten to `.claude/…`; history under `Tasks/*/completed/` and `Tasks/reports/` left as written (§10) |

## 4. Testing

The architecture tier plus the board and navigation guards (`python -m pytest tests/unit/architecture tests/unit/test_task_board_is_consistent.py tests/unit/test_rule_navigation_is_complete.py -q`): 405 passed before the full gate; then `scripts/ci-local.ps1 -Full` on the final tree, log path in the commit body.

## Implementation notes

- The reference checker, once pointed at the map and the rules, found what a reader would not: four placeholder paths written as literals (`BOT-XXX_slug.md`), two engine-repository paths cited as if local, and six links in the moved `EPIC-025` executor that still pointed one directory up. The checker read 11 documents before this change and reads 28 now.
- The board guard found one more: `ROADMAP.md` linked `../.agents/ONBOARDING.md` in a 2026-08 note.
- `.claude/settings.json` is tool configuration, which `ONBOARDING.md` §7 says to ask about: it is in the pull request for that reason, and the report to the user names it as the one decision in the diff.
- The `reviewer` subagent read the commit before the pull request was opened (its first run): one blocking finding — `measure_process.py` imported by package path and crashed when run bare, as every document says to run it — and five stale citations, all fixed in the follow-up commit.
- 2026-09-17, after the merge: the `SessionStart` hook is removed at the user's word; the eight permission rules stay. The manifest row re-rendered from the file.
- Not moved: the engine repository's own `.agents/` (a separate repository, `ONBOARDING.md` §9). The two Routines' prompts cite the new paths with the old ones as a fallback until this lands on `master-warrior`.
