# EPIC-037C — "Only one" guards: a second copy of a canonical mechanism turns CI red

**Status:** 🔵 Planned — not started
**Source:** the owner's systems-thinking review, 2026-10-09 (see the epic README for the quote)
**Risk:** 🟡 — AST detectors can misfire and block honest work
**Complexity:** M — a registry, five detectors, a shrink-only baseline
**Epic:** [EPIC-037](../README.md)
**Depends on:** EPIC-037A (the catalog names the canonical mechanisms)

---

## 1. Context and problem
59 architecture guards exist, none of which notices a rebuilt mechanism (leverage point 8). Evidence for the first five entries: BUG-155 (symbol picking), BUG-165 (empty states), BUG-197 (global log level left changed by a test), the fenced background reads of `async-ui-action-rule.md`, and BUG-194 (inventory derived from the exchange's history on only some paths).

## 2. Acceptance criteria
- [ ] `tests/unit/architecture/canonical_mechanisms.py` holds a registry: name, canonical module, AST detector, shrink-only baseline file.
- [ ] Five entries: symbol picking outside `support/ui_kit/symbol_picker`; hand-built empty-state labels outside `EmptyStateStack`; a test changing a global logger level without the shared restore fixture; a presenter starting a background read outside the fenced read path; owner inventory derived outside `OwnerInventoryDeriver`.
- [ ] Each detector has probe tests (a planted violation is reported, the canonical use is not) and is shown red by re-introducing the original bug's shape.
- [ ] An exemption needs a one-line reason in the baseline; the baseline may only shrink.

## 3. Design
A balancing loop at commit time, independent of memory. Mirror the existing shrink-only baselines and the AST helpers in `tests/unit/architecture/boundaries/`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/unit/architecture/canonical_mechanisms.py` | new registry |
| `tests/unit/architecture/test_canonical_mechanisms_are_not_rebuilt.py` | new guard |
| `tests/unit/architecture/baseline_canonical_mechanisms.txt` | shrink-only baseline |
| `.claude/rules/capabilities.md` | link each guarded row to its guard |

## 5. Testing
Architecture tier. For each detector: probe red and green, plus the red run with the old bug re-introduced, recorded in Implementation notes.

## Implementation notes (written when done)
Not started.
