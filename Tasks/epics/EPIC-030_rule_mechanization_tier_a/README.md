# EPIC-030 — The rulebook is enforced by mechanism, not by memory (Tier A)

- **Status:** 🟡 Phase 1 in progress
- **Repositories:** Elite
- **Origin:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per pull request, push this epic fast), after the audit "Sagittarius Rule Audit".
- **North star:** `.claude/CONSTITUTION.md` P1 (mechanism over memory) applied to the rulebook itself
- **Decisions:** [DECISION_2026-10-04_rule_provenance_ledger.md](DECISION_2026-10-04_rule_provenance_ledger.md)
- **Dependencies:** B1, the `master-warrior` ruleset (pull request required, `gate` check required), set by the user in GitHub

---

## 1. Decisions already made
1. Three pull requests: PR 1 documentation-only (A, B), PR 2 checker and architecture guards (C to G), PR 3 test isolation and audit alarm (H, I, L, M); one independent review per code pull request.
2. J (`Retire when:` baseline) and K (lower the always-loaded ceiling) are dropped as low strategic value.
3. A9 is a scheduled GitHub workflow that files an issue, never a clock-dependent test.
4. Contracts importing their own module's domain stays allowed (`src/modules/strategy/contracts/i_sizing_policy.py:131-134`).
5. Dates and pull request numbers leave rule text for the provenance ledger.

## 2. Goals — measurable
| Metric | Today (measured 2026-10-04) | When the epic is done |
| :--- | :-: | :-: |
| Rule clauses without an enforcement tag | 24 + 3 untagged rule files | 0, checked |
| `[gate]`/`[guard]` tags that check less than they claim | 7 | 0 |
| Dangling `§` citations in prompt trees | 12 | 0, checked |
| Engine imports outside the Shared Kernel in module cores | 1 | 0, guarded |
| Directories a full test run creates in the repository | `state/`, `database/` | none |
| Days a silent audit goes unnoticed | 27 | at most 7 |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-030A](incomplete/EPIC-030A_drift_fixes.md) | The rule tree states one policy once and cites only sections that exist | Elite | None | 🟢 | Planned |
| [EPIC-030B](incomplete/EPIC-030B_tag_every_clause.md) | Every rule clause names what enforces it, honestly | Elite | EPIC-030A | 🟢 | Planned |
| [EPIC-030C](incomplete/EPIC-030C_rule_integrity_checker.md) | The rule tree checks itself: tags, targets, sections, quotations, history | Elite | EPIC-030A, EPIC-030B merged | 🟡 | Planned |
| [EPIC-030D](incomplete/EPIC-030D_shared_kernel_guard.md) | Domain, application and contracts import from the engine only the Shared Kernel | Elite | EPIC-030C | 🟡 | Planned |
| [EPIC-030E](incomplete/EPIC-030E_module_layers_point_inward.md) | Inside one module, dependencies point inward | Elite | EPIC-030C | 🟢 | Planned |
| [EPIC-030F](incomplete/EPIC-030F_presenter_owned_never_registered.md) | Presenter-owned objects are never registered in the container | Elite | EPIC-030C | 🟢 | Planned |
| [EPIC-030G](incomplete/EPIC-030G_every_presenter_package_has_a_preview.md) | Every presenter package keeps a preview | Elite | None | 🟢 | Planned |
| [EPIC-030H](incomplete/EPIC-030H_unit_tests_never_reach_the_network.md) | Unit tests cannot reach the network | Elite | None | 🟡 | Planned |
| [EPIC-030I](incomplete/EPIC-030I_no_runtime_artifact_is_tracked.md) | No runtime artifact is tracked | Elite | None | 🟢 | Planned |
| [EPIC-030L](incomplete/EPIC-030L_audit_freshness_alarm.md) | A silent scheduled audit raises an alarm | Elite | None | 🟡 | Planned |
| [EPIC-030M](incomplete/EPIC-030M_data_root_seam.md) | Tests never write into the repository's state or database | Elite | None | 🔴 | Planned |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| PR 1 | The rule tree is consistent and fully tagged | `python3 scripts/check_skill_prompt_references.py` and the document guards; Not run |
| PR 2 | The checker and four architecture guards run in the commit tier | GitHub Actions `gate` run on the head sha, independent review; Not run |
| PR 3 | Tests are isolated from the repository and the network; the audit alarm fires | `gate` run, a test run leaving no `state/` or `database/`, a `workflow_dispatch` run filing one issue; Not run |

## 5. Out of scope
Tier B of the audit: enabling ruff or mypy rules in `pyproject.toml`, the review-disclosure check, Claude Code hooks, commit-message lint, pinning the engine. The 354 section citations inside `.py` and `.ps1` docstrings stay unchecked until a later task.

## Notes (newest first)
- **2026-10-04** — Epic scaffolded from the audit; J and K dropped by the user.
