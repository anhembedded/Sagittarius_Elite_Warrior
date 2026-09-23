"""The two live-trading screens define less twice after every phase, never more
(HLD §3.3, `EPIC-025`'s "59 → 0" completion criterion for Phase 1).

**The number was always reproducible; what was missing is a guard.**
`tools/measure_duplicate_members.py` shipped in Phase 0 and still measures
exactly the **59** the epic claims — member names defined in
`screens/dashboard` and `screens/trading` and in no third UI package. What
nobody wrote is the ratchet, so between phases the number could grow without
anything noticing: a third screen reacting to the same order events, or a fix
applied to one Presenter and copied into the other, which is how `BUG-084` and
`BUG-086` each had to be fixed twice.

**Why the scan covers old and new trees together** is the tool's own answer to
the design review (`Tasks/reports/EPIC-025_design_review.md` §7.1): a script
scanning only `screens/` reports 0 the moment the two packages are renamed,
whether or not any duplication moved. Renaming a package moves its count; it
cannot hide it — and that is precisely what makes a ratchet over it meaningful.

**Why it has not fallen yet**, measured in PR 1.4b-2 and PR 1.4c-4: the
duplication goes when the two screens move into `modules/trading/ui/` with
their feeds, and today a legacy Presenter is the only consumer of seven
`ui/common` files while the screens themselves need 24 and 44 imports from
`presentation/ui/*` — which is what `support/ui_kit` and `support/charting`
answer in Phase 4. Until then this file's job is the other direction.

**PR 4.4e** (`EPIC-025E`, "settings becomes a surface") added two new
`market_data.ui`/`trading.ui` Presenter/View/ViewModel triads
(`modules/*/ui/settings/`) and measured `market_data.ui+trading.ui` rising
by 9 names — exactly the pattern this guard exists to catch, since it was
new duplication, not debt carried through a move. Fixed at the root per
this guard's own §"the one amendment": `set_status`/`_get_status_message`/
`_get_status_is_error` were byte-identical to what `TradingViewModel`
(`modules/trading/ui/trading/`) already defined, so all three now subclass
one new `support/ui_kit/status_view_model.py::StatusMessageViewModel` —
inherited names the tool's own documented exclusion rule does not count,
removing 3 of the 9. The remaining 6
(`_apply_status`/`_apply_venue`/`_load_from_config`/`_on_save`/
`load_fields`/`requestSave`) share a name and a role (View renders a
status/venue; Presenter loads from config and saves) but not a body —
trading's venue carries a live-session lock market_data's never had, and
each loads/saves entirely different config keys — so naming them alike
without sharing an implementation would be the disguised-not-removed
duplication this guard's own docstring rejects performing on `_role_data`.
**Correction (independent review, PR #234):** an earlier draft of this
docstring claimed the baseline had "already drifted stale" to a true
pre-PR value of 60. That was wrong, and the wrongness was caught by
re-measuring the actual merge-base commit rather than trusting the
claim — the recorded **64** matches the merge-base exactly; there was
no staleness. The "60" was this PR's own intermediate arithmetic: 64
minus the 4 names (`_apply_status`/`_get_status_is_error`/
`_get_status_message`/`set_status`) the now-deleted `settings` package
itself contributed to the `settings+trading.ui` pair — a step in *this
PR's* delta, not a fact about `master-warrior` before this PR touched
anything. The end-to-end arithmetic is: 64 (merge-base) − 4 (pair
removed by deleting `settings`) + 9 (raw new names in the two new
settings triads) − 3 (folded into `StatusMessageViewModel`) = **66**,
which is what both the merge-base and the head commit independently
measure. The corrected baseline value itself was always right; only
the story of *why* was wrong.

**`BOT-019`** (the Watchlist screen, `modules/market_data/ui/watchlist/`)
raised the total 66 → **67**: `WatchlistPresenter._handle_market_tick`
joins `dashboard_presenter`/`trading_presenter`'s own methods of the same
name, moving `_handle_market_tick` from a `trading.ui`-internal pair (not
counted — same package) into the `market_data.ui+trading.ui` pair this
guard does count. All three share a name and a role ("the slot
`MarketTickFeed.marketTick` connects to") but not a body — Dashboard/
Trading filter by `_active_interval` and forward to chart-update signals;
Watchlist computes a percent change and updates a table row. Renaming
Watchlist's method to dodge the counter would violate `code/naming.md`
§4's own "one word per concept" rule for the one name this codebase
already uses for exactly this slot; extracting a shared base would have
nothing real to share, since the three bodies do genuinely different
things — the same call this guard's own docstring already made for
`_apply_status`/`_load_from_config` above. Accepted as debt with no
extraction target, not something to disguise by renaming.
"""

from __future__ import annotations

import json
from pathlib import Path

from Sagittarius_Elite_Warrior.tools.measure_duplicate_members import (
    PHASE_1_PAIR,
    measure,
)

_BASELINE_FILE = Path(__file__).with_name("baseline_presenter_duplication.json")
_BASELINE: dict[str, int] = json.loads(_BASELINE_FILE.read_text(encoding="utf-8"))
_MEASURED = measure()

#: The pair Phase 1 must bring to zero, plus the total across every pair — a
#: fall in the first that only moved names into a *different* pair is not
#: progress, and the total is what says so.
_PHASE_1_KEY = "phase_1_count"
_TOTAL_KEY = "defined_in_more_than_one_package"


def test_the_baseline_names_the_pair_it_measures() -> None:
    """A baseline that stops matching the tool's own pair is a number about
    something else."""
    assert _MEASURED["phase_1_pair"] == "+".join(sorted(PHASE_1_PAIR))
    assert set(_BASELINE) == {_PHASE_1_KEY, _TOTAL_KEY}


def test_the_phase_1_duplication_does_not_grow() -> None:
    measured = int(_MEASURED[_PHASE_1_KEY])
    baseline = _BASELINE[_PHASE_1_KEY]
    assert measured <= baseline, (
        f"Dev Board + Trading duplicated members: {baseline} → {measured}.\n"
        "A behaviour both screens need belongs to the module they share — a\n"
        "port, a feed, a coordinator — not copied into the second Presenter.\n"
        "`python tools/measure_duplicate_members.py` lists the names."
    )


def test_the_duplication_across_every_pair_does_not_grow() -> None:
    measured = int(_MEASURED[_TOTAL_KEY])
    baseline = _BASELINE[_TOTAL_KEY]
    assert measured <= baseline, (
        f"member names defined in more than one UI package: {baseline} → "
        f"{measured}.\nThe Phase 1 pair can fall while this rises, which is "
        "duplication moved\nrather than removed — see the per-pair breakdown."
    )


def test_the_baseline_was_lowered_when_duplication_went() -> None:
    """A ratchet that is never tightened stops being one — the same rule
    `test_app_styling_only_shrinks.py` states for its own numbers."""
    for key in (_PHASE_1_KEY, _TOTAL_KEY):
        measured = int(_MEASURED[key])
        assert measured >= _BASELINE[key], (
            f"{key}: {_BASELINE[key]} → {measured}. Duplication was removed —\n"
            f"lower the number in {_BASELINE_FILE.name} in the same commit."
        )
