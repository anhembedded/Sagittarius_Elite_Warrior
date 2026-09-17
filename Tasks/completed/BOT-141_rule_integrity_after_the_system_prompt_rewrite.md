# BOT-141 — The rule set says what it means again after the system-prompt rewrite

**Status:** ✅ Done (2026-09-17)
**Source:** User, 2026-09-17: *"Xét bộ rule AI mới của toi trong tối nay thế nào, có phải hoàn thiện hơn không?"* — review tonight's new rule set and say whether it is more complete; then *"Ok, nhớ là viết kiểu system promt, ko lê thê"* — proceed, keeping the system-prompt register.
**Risk:** 🟡 — a rule an agent reads every session; a wrong restoration misleads every later run.
**Complexity:** M — five rule/skill documents, two scripts, nineteen citations.
**Depends on:** None.

---

## 1. Context and problem
The 2026-09-17 rewrite (`80a64a1`, `a327be4`, `e02382d`, `a0a3aa7`) turned every rule into a system prompt. Measured on the tree: only four files changed materially — `ci-rule.md` −68 % (1161 → 360 words), `report-rule.md` −56 %, `commit-rule.md` −35 %, `CONSTITUTION.md` −17 %; the rest gained a heading. The compression took decisions that exist in no other file, renumbered sections that nineteen live documents cite, dropped `[gate]` from 6 occurrences to 0 while `.claude/README.md` and `ONBOARDING.md` still define the four-tag contract, and left "documentation-only" — the one class §7 lets an agent merge to `master-warrior` alone — undefined. `scripts/validate_skill.py` shipped in the same night reachable only from prose, and failing the repository's own Ruff gate.

## 2. Acceptance criteria
- [x] Every decision the compression dropped is readable again in the rule that owns it, in the current register.
- [x] `ONBOARDING.md` §7 defines documentation-only by path set and names its guards.
- [x] No document under `.claude/`, and no living board, index, HLD or active epic file, cites a section that does not exist.
- [x] A renumbering that breaks a citation fails a check rather than a reader.
- [x] `scripts/validate_skill.py` runs inside the gate and passes lint there.

## 3. Design
Restoration over rewrite: the compressed structure stays and the lost clauses return as directives inside it, because the register was the point of the rewrite. The new check extends `check_skill_prompt_references.py` rather than adding a second scanner (`CONSTITUTION.md` P5) — same trees, same exit contract. Two precision rules keep it from crying wolf: an anchor binds only to a document named within 30 characters before it, and a rule numbered as one top-level ordered list (`logging-rule.md`) resolves its items as sections.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `.claude/rules/ci-rule.md` | Restored testnet opt-in, `-AllowLogWarnings`, retired `-IncludeFlakyUi`, `BOT-038` flake re-verification, `BUG-119` stall split, component probe, evidence-binds-to-final-tree, move-PR import check, read-only gate, guard-versus-newer-decision; `[gate]`/`[review]`/`[eye]` tags back. |
| `.claude/rules/commit-rule.md` | Restored the trailer discipline, the pull-request body, and merging a branch an unattended agent opened (§4, §5). |
| `.claude/ONBOARDING.md` | §7 defines documentation-only and names the five document guards. |
| `.claude/rules/fix-bug-rule.md`, `.claude/skills/fix-bug/SKILL.md`, `.claude/rules/report-task-rule.md`, `.claude/rules/testing-rule.md`, `.claude/templates/task.md`, `.claude/skills/test-health/contract.json` | Section citations repointed to sections that exist. |
| `scripts/check_skill_prompt_references.py` | Verifies `§N` citations; proximity binding; list-shaped rules. |
| `scripts/validate_skill.py` | Named thresholds, git resolved through `shutil.which`, narrowed `except` — passes Ruff. |
| `scripts/ci-local.ps1` | New static step "Skill Definition Validation". |
| `Tasks/ROADMAP.md`, `Tasks/bug_report/README.md`, `Docs/HLD/01`, `Docs/HLD/08`, `Tasks/proposal/PRO-004.md`, `EPIC-012`/`EPIC-015` READMEs, `EPIC-025C/D/E` | Nineteen citations repointed. |

## 5. Testing
Documentation guards and the reference checker cover the rule edits; the two scripts are covered by the machine gate (`ci-rule.md` §1). Mutation evidence is required for both new checks, since a checker that passes on everything is the failure mode being fixed.

## Implementation notes (written when done)
Mutation-proved, not assumed: reintroducing the four repointed citations turns `check_skill_prompt_references.py` red on exactly those four and green on restore; truncating a `SKILL.md` turns `validate_skill.py` red and green on restore.

The first `pwsh -NoProfile -File scripts/ci-local.ps1 -SkipTests` on this tree failed on `scripts/validate_skill.py` (three `PLR2004`, `S603`/`S607`, `BLE001`) — the file had been committed without that run, and wiring it into the gate turned its own lint failure into a gate failure. Fixed at the mechanism, not with suppressions.

`test_task_board_is_consistent` then caught the board: `scripts/render_task_counts.py` prints its table for pasting rather than writing it, so recording this task left ROADMAP claiming 195 tasks against 196 directories.

Full gate green on the final tree: `logs/ci-local-20260917-182545.log` — Ruff, Ruff Format, Mypy, Repository Reference Check, Skill Definition Validation, 4995 passed / 4 skipped, Sanity, coverage 95.67 % ≥ 80 %, run-log scan clean, `RESULT: PASS`.

Deliberately not touched: dated records (`completed/`, `cancelled/`, `Tasks/reports/`, `Docs/CASE_STUDIES/`, `EPIC-025/TRACKING.md`) keep the section numbers they were written against — they record what a past reader was told, and the anchor check does not scan them. Open for the user: the Mermaid **Gantt** mandate of `a0a3aa7` has no date source in an epic child, so a timeline can only be invented.
