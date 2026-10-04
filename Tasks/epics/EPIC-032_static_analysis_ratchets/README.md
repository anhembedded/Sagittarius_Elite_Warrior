# EPIC-032 — Static analysis only tightens (Tier B, rest)

- **Status:** ✅ Done (2026-10-04)
- **Repositories:** Elite
- **Origin:** the user, 2026-10-04 — "làm tiếp phần còn lại của Tier B đi" (do the rest of Tier B).
- **North star:** `.claude/CONSTITUTION.md` P1 and P8: a limit that only moves one way
- **Dependencies:** EPIC-031

---

## 1. Decisions already made
1. The user approved the `pyproject.toml` edits by choosing these audit items.
2. A rule with zero hits is enabled; a rule with hits is ratcheted per file, never enabled with mass suppressions.
3. Ratchet scope follows the rule a code serves: `quality.md` trees for `ANN401`, `PLC0415`, `C901`, `PLR0904`; every tree for `T20`.
4. `PLR0904` is a ruff preview rule, so it is ratcheted with `--preview` rather than selected (PR #330 review).

## 2. Goals — measurable
| Metric | Before (measured 2026-10-04) | When the epic is done |
| :--- | :-: | :-: |
| Strict mypy overrides that match a module | 1 of 3 strict sections | 3 of 3 |
| mypy `exclude` patterns | 69, unguarded, 3 dead | 66, shrink-only |
| Ruff rules enforced | 6 prefixes | 6 prefixes + 4 codes |
| Ruff debt with a ceiling | 0 of 5 rules | 5 of 5, per file |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-032A](completed/EPIC-032A_mypy_scope.md) | Mypy checks what the config says it checks | Elite | EPIC-031 | 🟢 | Done |
| [EPIC-032B](completed/EPIC-032B_zero_hit_ruff_rules.md) | Five ruff rules the tree already meets refuse the first breach | Elite | EPIC-031 | 🟢 | Done |
| [EPIC-032C](completed/EPIC-032C_ruff_debt_ratchet.md) | Four ruff rules the tree cannot meet yet only lose violations | Elite | EPIC-031 | 🟢 | Done |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| One pull request | mypy and ruff green under the new settings; both ratchets fail on a planted breach | Unit tests; the pull request's gate run and independent review |

## 5. Out of scope
Fixing the ratcheted debt itself; enabling a ratcheted rule once its baseline empties is the follow-up each guard's `Retire when:` names.

## Notes (newest first)
- **2026-10-04** — Epic delivered in one pull request.
