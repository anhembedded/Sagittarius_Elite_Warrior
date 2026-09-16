# Decision 2026-09-16 — the allowlist stays clean; "59 duplicated members → 0" waits for Phase 2 + Phase 4

**Decided by:** the user, in reply to a measurement offered with two options and no recommendation
dressed as a fact.
**Answer, verbatim:** *"để tiêu chí đó chờ Phase 2 + Phase 4"* — let that criterion wait for
Phase 2 and Phase 4.

## What was asked, and why it could not be measured

`EPIC-025`'s own table sets Phase 1's last exit criterion as **59 → 0**: the member names that
`screens/trading` and `screens/dashboard` each define separately
(`tools/measure_duplicate_members.py` counts them; `test_presenter_duplication_only_shrinks.py`
holds the number shrink-only). The two screens going to one owner —
`modules/trading/ui/` — is what drives it to zero, and that move was blocked on
`support/ui_kit` and `support/charting` existing. PRs 1.6a–1.6g built both.

Re-measured after 1.6g, the blockers are down from 66 imports to **42**:

| What the two screens still import from the legacy tree | Imports |
| :--- | ---: |
| `ui/common` (the seven trading feeds, and eight others) | 21 |
| `components/order_book` | 10 |
| `qml/{SymbolPicker,kit,interfaces,TimeRangePicker}` | 6 |
| `components/strategy_params` | 4 |
| `components/strategy_overlay` | 1 |

**31 of the 42 could have moved in one pull request** — both screens, `components/order_book` and
the seven trading feeds of `ui/common`, all into `modules/trading/ui/`. The remaining 11 could
not: they are QML packages that ADR D21 **deletes** in Phase 4 rather than moves, and
`components/strategy_params`, which needs `BaseStrategy` from Phase 2's `modules/strategy`. A
legacy screen may import a module only through its `contracts/`, so those 11 would have had to
become **new lines in `allowlist_module_boundaries.txt`** — a file whose whole discipline is that
it only ever shrinks (316 lines today, **23** live entries, down from 80 at PR 1.3a).

> **The count in that sentence was 36 when this file was written, and 36 was never right.**
> `grep -cvE '^\s*#|^\s*$' tests/unit/architecture/allowlist_module_boundaries.txt` answers
> **23**, and walking the file's history says it has answered 23 since PR 1.3c-5 — 80 after
> 1.3a, then 56, 46, 32, 29, 25, 23. The wrong number came from `Tasks/epics/README.md`'s
> Phase 1 row and was copied forward into six `TRACKING.md` rows and into this file, all on
> the same day, each time as "unchanged at 36" — which is the failure
> `.agents/Skills/README.md` §1 bans by name: a count written into a briefing as current
> state. It changes nothing about the decision below (the question was whether to *add* 11
> entries, and 11 added to 23 is as much a growth as 11 added to 36), which is why it is a
> note here rather than a re-decision. Corrected everywhere on 2026-09-16, and the command is
> written out so the next reader measures instead of copying.

So the question was not "which is cheaper". It was whether to spend the epic's one invariant —
*the allowlist never grows* — to reach a number four pull requests early. That trades a measured
thing for a judged one, which is why it was the user's to answer and not mine.

## What was decided

**Keep the ratchet clean.** No new allowlist entry is written to unblock the duplication
criterion. The criterion is carried forward on its existing shrink-only guard, and the two screens
move to `modules/trading/ui/` when the work they are actually waiting on lands:

- **Phase 2 (`modules/strategy`)** gives `components/strategy_params` a real home — and with
  `BaseStrategy` inside a module, a form rendering *a strategy's* parameters reads as
  `modules/strategy/ui`, not as a generic package.
- **Phase 4** deletes the six remaining QML imports rather than moving them (ADR D20–D21), so they
  never need an entry at all.

Nothing is deferred silently: the 59 stays visible in the epic's table with its guard, and this
file is the reason it is still 59.

## What this does not change

- **`support/ui_kit` extraction continues bottom-up now.** A leaf of `ui/common` or `components/`
  that can reach `support/` costs zero allowlist entries in either direction (a legacy file may
  import `support/**` whole), so that work is independent of this decision and is where the next
  pull requests go.
- **Phase 1 still closes** on everything else it promised; this criterion moves with the screens.
- The **two other open questions stand** — `sync_progress_{feed,report}` → `modules/market_data/ui/`
  (HLD §3.5 assigned them to `support/ui_kit`, which the rule table refuses), and
  `components/strategy_params` → `modules/strategy/ui`. Phase 2 is where the second one is
  naturally answered, which this decision makes the likely venue for both.
