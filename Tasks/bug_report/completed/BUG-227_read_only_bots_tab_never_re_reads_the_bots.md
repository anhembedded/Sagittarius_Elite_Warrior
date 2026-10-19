# BUG-227 — A read-only copy of the Bots tab never shows the profit the running copy books after it opened

- **Reported:** 2026-10-19 (coordinator session, from the owner: "the UI and the VPS still do not show how much profit the bot has made")
- **Severity:** 🟡 P2. A second copy of the app beside the writing one shows the figures of the moment it opened, so the owner reads a stale (or zero, or blank) profit while the bot trades. No order, state or alert is affected.
- **Status:** ✅ Fixed (2026-10-19)
- **Board:** A read-only Bots tab never showed profit booked after it opened. Cause: it re-read the bots only on a `BotChangedEvent` the writing process never sends it. Fix: its 30 s clock re-reads the bots on a read-only copy.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (a second copy opens read-only) → `bots` → `ui/bots_screen/` (`BotsPresenter`, `presenter_pacing.py`)
- **Environment:** Linux, fake exchange and unit harness at `15379eb`. The owner's own setup (which machine runs the UI, whether it shares the VPS's data root) is Not yet established.

## Reproduction
1. Save a RUNNING grid bot whose runtime holds one booked cycle (profit 1.25) in the bots folder; open the Bots screen as a read-only copy (`InstanceAccess.declined`).
2. The writing copy books another cycle: its file now says 7.50 (saved from another store on the same folder, as another process does).
3. Let the screen's clock beat. Expected: the Total PnL cell reads 7.50. Actual: it keeps reading 1.25 for as long as the screen is open.

## Symptom
Table cell stays `1.25`: `AssertionError: assert '7.50' in '1.25'` (`test_a_read_only_copy_shows_a_cycle_the_writer_booked_after_it_opened`, red before the fix).

## Root cause
`BotsPresenter.__init__` reads the list once (`self._queries.bots()`) and afterwards only on `BotChangedEvent` (`_on_bot_changed`), which `NotifyingBotStore` publishes on the writing process's own bus. A read-only copy is another process: its bus never carries the writer's saves. The 30 s clock only recomputed the detail from the cached snapshot (`_refresh_detail`), so progress (grid profit, cycles, total PnL) never changed after the first read. Read at `15379eb`: `bots_presenter.py` (`_clock.timeout.connect(self._refresh_detail)`), `notifying_bot_store.py`.

## Fix
`BotsClock` (`presenter_pacing.py`) owns the clock: each beat refreshes the detail, and on a read-only copy (`IInstanceAccess.read_only`, passed through `BotsDependencies.instance`) also re-reads the bots through the screen's fenced list read. The writing copy is unchanged (it hears its own saves). One mechanism for every consumer of the clock, at the layer that owns the clock.

## Regression test
`tests/unit/modules/bots/ui/bots_screen/test_a_read_only_copy_follows_the_writers_files.py::test_a_read_only_copy_shows_a_cycle_the_writer_booked_after_it_opened` — failed before the fix for the reason above; passes after. The real presenter, store and queries are used; only the other process is a second `JsonBotStore` on the same folder. Its sibling locks that the writing copy does not re-read.

## Verification
`tests/unit/modules/bots/ui/bots_screen`: 445 passed; commit tier (`ci-local.ps1 -SkipTests`) PASS at the fix commit; the PR's `-Full` run is the full gate. Whether this is what the owner meets is Not yet established: it needs the owner's setup (screenshot of the Bots tab, `bot show <id>` output, and whether the UI shares the VPS's data root).
