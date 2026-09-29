# EPIC-028M — The single Trading screen is gone, the Dev Board uses the shared order panel, and the docs describe two desks

**Status:** 🔵 Backlog
**Source:** the user, 2026-09-29 — *"cần có 2 cái chứ không phải 1, 1 cái là future, 1 cái là spot … cái nào chung được thì chung, riêng thì riêng"* ("two trading screens, one Futures and one Spot; share what can be shared"). See the [ADR](../DECISION_2026-09-29_two_trading_desks.md).
**Risk:** 🟢 — deletion plus docs; a saved layout pointing at the old route must still open
**Complexity:** M — delete two god files, rewire Dev Board F9, HLD/SPEC
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028K](EPIC-028K_futures_desk_screen.md), [EPIC-028L](EPIC-028L_spot_desk_screen.md), ADR O4

---

## 1. Context and problem
- `trading_view.py`, `trading_presenter.py` are on the god-file baseline; HLD 04 §4.5 and HLD 11 §11.3 say manual order is Dev Board only.

## 2. Acceptance criteria
- [ ] Route `trading` and its view/presenter/view model are deleted and removed from `baseline_god_files.json`; a saved layout naming it opens the Futures desk.
- [ ] The Dev Board's F9 dialog hosts the shared order-entry panel with the configured venue's profile.
- [ ] HLD 04 §4.5, HLD 11 §11.2–11.3, `SPEC-004` (still single-venue: its precondition names Futures Testnet and it has no per-venue toggles; the PR #295 review's question 4), `SPEC-005`, `SPEC-012` updated; a new SPEC "See my account on a desk" lists its proving tests.
- [ ] `test_spec_index_is_consistent.py`, reference checker and the full gate green.

## 3. Design
Delete, don't deprecate (no compatibility shims). The saved-layout fallback lives in the layout loader, keyed by route.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/trading/` | deleted |
| `src/modules/trading/ui/dashboard/…` | F9 dialog on the shared panel |
| `Docs/HLD/04_*.md`, `Docs/HLD/11_*.md`, `Docs/SPEC/*` | updated / new SPEC |

## 5. Testing
Sanity route scan; layout-fallback unit test; doc guards.
- Not run.

## Implementation notes (written when done)
Not started.
