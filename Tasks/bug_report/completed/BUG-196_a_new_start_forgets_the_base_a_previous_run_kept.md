# BUG-196 — A new Start forgets the base a previous run kept: it is never sold by the ladder and never shown to the owner

- **Reported:** 2026-10-09 (the owner, Spot Mainnet, bot `vce9z8`, ETHUSDT, via the coordinator session)
- **Severity:** 🟡 P2 — real money left idle and unaccounted (about 0.0166 ETH, about 41.9 USDT on the account after two halted starts); no order is wrongly placed
- **Status:** ✅ Fixed (2026-10-09)
- **Board:** A new Start counts only its own orders (ADR D6), so base a previous run kept was nobody's and unseen; fixed by reporting it: Start reads the earlier runs' leftover from the exchange's history (capped by the account's free base) and the bot's figures show it. Not carried, not a refusal.
- **Context:** SPEC-014 (run a grid bot) → `src/modules/bots/` (`domain/bot.py`, `application/services/grid_housekeeping.py`) and `src/modules/trading/` (`application/owner_inventory_deriver.py`)
- **Environment:** Linux, master-warrior at `37216c6` (BUG-194's fix); observed on Spot Mainnet 2026-10-09, reproduced on the fake exchange.

## Reproduction
Integration tier, the composed app over the fake Binance server: Start a Grid bot (RUNNING, opening buy filled), Stop it with `BaseHandling.KEEP`, Start it again. Observed on the fake exchange:

| After | Account BTC (seed 10) | Bot's owner book |
| :-- | :-- | :-- |
| first Start | 10.023976 | 0.023976 |
| Stop (keep) | 10.023976 | — |
| second Start | 10.047952 | 0.023976 |

The account holds 0.047952 BTC bought by the bot; the book of the second run holds 0.023976, the second opening only. The first run's 0.023976 is nobody's.

## Symptom
Two starts, each buying an opening inventory, each ended (BUG-194 halted both, then Stop): about 0.0166 ETH stays on the account. No ladder level sells it, no screen names it.

## Root cause
By design of ADR D6 (review round 2), and stated as such in `owner_inventory_deriver.py:11-12` ("base a previous run kept is not counted, since its orders predate `run_started_at`"):
1. `Bot._next_lifecycle` stamps a new `run_started_at` on `start` from DRAFT or STOPPED (`bot.py:164-166`); a resume from HALTED keeps it.
2. `GridHousekeeping.register` (`grid_housekeeping.py:65-76`) and `GridStartPreconditions.check` (`grid_start_preconditions.py:~100`) send that instant as the registration's `run_started_at`.
3. `OwnerInventoryDeriver.derive` reads order and trade history only from it (`owner_inventory_deriver.py:121-127`), so the previous run's tagged buys are outside the read.
Nothing compares the inventory the new run starts with against what the bot's earlier runs left, so the loss is silent.

Not the cause of BUG-195: a Resume from HALTED is the same run (`run_started_at` unchanged), and the 0.0083 ETH that resume derived was its own run's. BUG-195's `-2010` needs the account's free and locked base at the time (not in the log).

## Fix
Owner decision 2026-10-09 (option C): Start stays allowed; the leftover is reported, not carried. A hand-sale between runs would make a carried figure wrong, and D6's per-run rule stays.
- `trading`: `ITradingSession.earlier_runs_inventory(EarlierRunsRequest)` (dispatched as `ReadEarlierRunsCommand`) replays the owner's tagged orders and trades before the run's start (`earlier_runs_deriver.py`, the deriver's own fill rule), keeps no checkpoint and installs nothing, then caps the quantity at the account's free base (cost scaled). A venue that does not answer is `unavailable`, never an empty answer.
- `bots`: `GridEarlierRuns` (called first in `GridStartSequence.run`) records the answer on the run's runtime (`earlier_runs_base`, `earlier_runs_cost`, persisted, kept through a resume); an unknown answer is a WARNING and the start goes on. The bot's figures show "Left from earlier runs" (`bot_facts.py`, `FACT_SPECS`).
- "Adopt into this run" is the extension the record is the seam for; not built.

Deviation from the brief, reported to the owner: the Bots screen's pre-Start Run step is built from local state with no exchange round trip (`BotRunFactsReader`, `assess_readiness`), so a history read cannot sit in it. The figure therefore shows on the bot after Start (and stays on the stopped bot's record); a pre-Start item needs an asynchronous load on selection (`async-ui-action-rule.md`), a follow-up. **Delivered by `BOT-173`:** the exchange snapshot is loaded on selection and the warning "A previous run kept X ≈ Y USDT that this run will not trade" shows beside the Run step before Start.

## Regression test
- `tests/integration/modules/bots/test_a_new_start_reports_the_base_an_earlier_run_kept_on_the_fake_exchange.py` (Start, Stop keeping the base, Start): the second run records the first run's base and its cost, a first run records none, a hand-sold base is not claimed. Red without the fix (the runtime has no record of it), green after.
- `tests/unit/modules/trading/application/session/test_read_earlier_runs.py` (before/after the run start, another owner's orders, a sell between runs, the cap, the venue not answering), `tests/unit/modules/bots/application/services/test_grid_earlier_runs.py`, `tests/unit/modules/bots/ui/bots_screen/test_bot_facts.py`.

## Verification
Commit tier green (`ci-local.ps1 -SkipTests`: ruff, format, mypy, reference check); `tests/unit` and `tests/integration` green locally except `test_workbench_conformance[True-1024x700]`, which fails identically on the base. Positive proof the new mechanism ran, from the integration log: `[earlier-runs] <tag> on BTCUSDT: 0.02397600 BTC before <run start>` then `WARNING Bot <tag>: 0.02397600 BTC from earlier runs stays on the account and is not traded by this run [earlier-runs]`. The `-Full` run is GitHub Actions' on the PR head. Not run on a real exchange.
