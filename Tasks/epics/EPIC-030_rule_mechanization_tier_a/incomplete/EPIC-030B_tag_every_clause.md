# EPIC-030B — Every rule clause names what enforces it, honestly

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟢 — Documentation only; a wrong tag misleads a reviewer
**Complexity:** S — delivered in PR 1 (documentation-only)
**Epic:** [EPIC-030](../README.md)
**Depends on:** EPIC-030A

---

## 1. Context and problem
`.claude/README.md` says every clause carries an enforcement tag, yet `ci-rule.md`, `commit-rule.md` and `report-rule.md` had none and 24 other clauses were untagged. Three `[gate]` tags claimed machine enforcement that does not exist (`code/quality.md` §1 zero `Any`, §5 no bare `noqa`), and four guard tags were malformed or pointed at prose.

## 2. Acceptance criteria
- [ ] `EPIC-030C`'s clause check reports zero untagged clauses.
- [ ] No `[gate]` tag claims a check that `pyproject.toml` or `ci-local.ps1` does not run.
- [ ] Every `[guard: …]` names one tracked test file.

## 3. Design
The design is recorded in the epic README §1 and in this task's pull request; the guard, where there is one, carries probe tests that prove it can fail.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| Pending | Written when done. |

## 5. Testing
Not run. Each criterion maps to a unit test or guard under `tests/unit/`; documentation-only work names `python3 scripts/check_skill_prompt_references.py` and the document guards.

## Implementation notes (written when done)
Not yet established.

## Resume (optional; while unfinished)
PR #322 tagged `ci-rule.md`, `commit-rule.md` and `report-rule.md`. Still open, and blocked until `.claude/**` edits are allowed in the session:
- the 24 untagged clauses `EPIC-030C`'s checker lists (`architecture-rule.md` SOLID bullets, `install-rule.md`, `testing-rule.md` §1–§2, `logging-rule.md` 5 and 7, `ui-presentation-rule.md` §3–§4, `domain-truth-rule.md`, `async-ui-action-rule.md`);
- retagging to the guards PR #323 adds (review finding 2):
  - `architecture-rule.md` §3 Shared Kernel → `[guard: test_module_inside_imports_only_the_shared_kernel.py, tests/unit/support/indicators/test_indicator_script_conventions.py]`;
  - `architecture-rule.md` §3 layers point inward → add `test_module_layers_point_inward.py`;
  - `async-ui-action-rule.md` §2 coordinators and `domain-truth-rule.md` chart host → `[guard: test_presenter_owned_objects_are_never_registered.py; review: G4]`, replacing the unwired grep;
  - `ui-presentation-rule.md` §5 previews → `[guard: test_every_presenter_package_has_a_preview.py, tests/unit/presentation/ui/test_preview_fixtures_exist.py]`;
  - `ci-rule.md` §2 unit tier → `[guard: test_unit_tests_never_reach_the_network.py; review: E3]`;
  - `commit-rule.md` §3 forbidden content → `[guard: test_no_runtime_artifact_is_tracked.py; review: L4, L5]`;
- the legend placeholders in `ONBOARDING.md` and `.claude/README.md`, the `report-task-rule.md` description and the re-rendered manifest (in the session's stash), and the `gate` check name in `ONBOARDING.md` §7 (the real check is `ci-local.ps1 -Full`).
