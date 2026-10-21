"""Data only - where every hand-written set of bot lifecycle states stands, state by state.

Read by `test_every_state_set_classifies_every_state.py`. A row is `path::NAME` and two lists that
together name EVERY `BotLifecycleState`: the members the set holds and the states it deliberately
leaves out. A new state therefore fails the guard until each set has been read and the state put on
one side of it (`EPIC-044`, ADR 044 §2.4, round-1 review S7). `AWAITING_RANGE` is classified in each.
"""

from __future__ import annotations

_ALL = [
    "DRAFT",
    "STARTING",
    "RUNNING",
    "PAUSED",
    "RECOVERING",
    "HALTED",
    "AWAITING_RECOVERY",
    "AWAITING_RANGE",
    "STOPPING",
    "STOPPED",
    "ERROR",
]
ALL_STATES: frozenset[str] = frozenset(_ALL)


def _row(members: str, excluded: str) -> tuple[frozenset[str], frozenset[str]]:
    return frozenset(members.split()), frozenset(excluded.split())


_M = "src/modules/bots/"
#: path::NAME -> (members, states left out on purpose)
STATE_SETS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    # --- the lifecycle table's own sets ---
    _M + "domain/bot_lifecycle_fsm_matrix.py::PRICE_STREAM_STATES": _row(
        "STARTING RUNNING PAUSED RECOVERING HALTED AWAITING_RECOVERY AWAITING_RANGE STOPPING ERROR",
        "DRAFT STOPPED",
    ),
    _M + "domain/bot_lifecycle_fsm_matrix.py::PRICE_STALENESS_HALTS": _row(
        "STARTING RUNNING PAUSED RECOVERING",
        "DRAFT HALTED AWAITING_RECOVERY AWAITING_RANGE STOPPING STOPPED ERROR",
    ),
    _M + "domain/bot_lifecycle_fsm_matrix.py::RESUME_PROPOSES_STATES": _row(
        "HALTED AWAITING_RECOVERY",
        "DRAFT STARTING RUNNING PAUSED RECOVERING AWAITING_RANGE STOPPING STOPPED ERROR",
    ),
    _M + "domain/bot_lifecycle_fsm_matrix.py::RECOVERABLE_STATES": _row(
        "RUNNING PAUSED AWAITING_RANGE",
        "DRAFT STARTING RECOVERING HALTED AWAITING_RECOVERY STOPPING STOPPED ERROR",
    ),
    _M + "domain/bot_lifecycle_fsm_matrix.py::RUN_STARTING_STATES": _row(
        "DRAFT STOPPED",
        "STARTING RUNNING PAUSED RECOVERING HALTED AWAITING_RECOVERY AWAITING_RANGE STOPPING ERROR",
    ),
    # --- the watches that protect exposure (through `may_hold_exposure`) ---
    _M + "application/kinds/grid/watch/grid_price_reaction.py::_WATCHES_EXITS": _row(
        "STARTING RUNNING PAUSED RECOVERING HALTED AWAITING_RECOVERY ERROR",
        "DRAFT AWAITING_RANGE STOPPING STOPPED",
    ),
    _M
    + "application/kinds/grid/watch/grid_rate_limit_pause.py::_HALTED_BY_A_LIMIT": _row(
        "STARTING RUNNING PAUSED RECOVERING HALTED AWAITING_RECOVERY",
        "DRAFT AWAITING_RANGE STOPPING STOPPED ERROR",
    ),
    _M + "application/kinds/grid/protection/protection_futures.py::_SUPERVISED": _row(
        "RUNNING PAUSED RECOVERING",
        "DRAFT STARTING HALTED AWAITING_RECOVERY AWAITING_RANGE STOPPING STOPPED ERROR",
    ),
    # --- recovery, switch, stream, parking ---
    _M
    + "application/services/lifecycle/halt_recovery_director.py::TRANSIENT_FROM": _row(
        "STARTING RUNNING",
        "DRAFT PAUSED RECOVERING HALTED AWAITING_RECOVERY AWAITING_RANGE STOPPING STOPPED ERROR",
    ),
    _M + "application/kinds/grid/grid_facts.py::_SWITCHED_OFF_FROM": _row(
        "STARTING RUNNING PAUSED AWAITING_RECOVERY AWAITING_RANGE",
        "DRAFT RECOVERING HALTED STOPPING STOPPED ERROR",
    ),
    _M + "application/kinds/grid/watch/grid_stream_gap.py::_FED_BY_THE_STREAM": _row(
        "RUNNING PAUSED",
        "DRAFT STARTING RECOVERING HALTED AWAITING_RECOVERY AWAITING_RANGE STOPPING STOPPED ERROR",
    ),
    _M + "application/kinds/grid/grid_task_guard.py::_PARKED": _row(
        "HALTED AWAITING_RECOVERY ERROR",
        "DRAFT STARTING RUNNING PAUSED RECOVERING AWAITING_RANGE STOPPING STOPPED",
    ),
    _M
    + "application/services/lifecycle/bot_runner.py::_RESUMES_AFTER_A_CLOSED_SESSION": _row(
        "RECOVERING HALTED AWAITING_RECOVERY",
        "DRAFT STARTING RUNNING PAUSED AWAITING_RANGE STOPPING STOPPED ERROR",
    ),
    # --- at rest ---
    _M + "application/services/lifecycle/running_bots_objection.py::_AT_REST": _row(
        "DRAFT STOPPED",
        "STARTING RUNNING PAUSED RECOVERING HALTED AWAITING_RECOVERY AWAITING_RANGE STOPPING ERROR",
    ),
    _M + "contracts/bot_status_report.py::AT_REST_STATES": _row(
        "DRAFT STOPPED",
        "STARTING RUNNING PAUSED RECOVERING HALTED AWAITING_RECOVERY AWAITING_RANGE STOPPING ERROR",
    ),
    _M + "ui/bots_screen/bot_chart_host.py::_AT_REST": _row(
        "DRAFT STOPPED",
        "STARTING RUNNING PAUSED RECOVERING HALTED AWAITING_RECOVERY AWAITING_RANGE STOPPING ERROR",
    ),
    # --- display ---
    _M + "ui/bots_screen/bot_facts.py::_RUNNING_CLOCK": _row(
        "STARTING RUNNING PAUSED RECOVERING HALTED AWAITING_RECOVERY AWAITING_RANGE",
        "DRAFT STOPPING STOPPED ERROR",
    ),
    _M + "ui/bots_screen/bots_table_models.py::_ATTENTION_STATES": _row(
        "HALTED AWAITING_RECOVERY ERROR",
        "DRAFT STARTING RUNNING PAUSED RECOVERING AWAITING_RANGE STOPPING STOPPED",
    ),
    _M + "ui/bots_screen/plan_status.py::_NEEDS_THE_OWNER": _row(
        "HALTED AWAITING_RECOVERY RECOVERING ERROR",
        "DRAFT STARTING RUNNING PAUSED AWAITING_RANGE STOPPING STOPPED",
    ),
    # --- alerting (string sets) ---
    "src/modules/alerting/application/sources/bot_reason_routes.py::_HALT_OR_ERROR": _row(
        "HALTED ERROR",
        "DRAFT STARTING RUNNING PAUSED RECOVERING AWAITING_RECOVERY AWAITING_RANGE STOPPING STOPPED",
    ),
    "src/modules/alerting/application/sources/liquidation_alert_source.py::_JUDGED": _row(
        "STARTING RUNNING PAUSED RECOVERING",
        "DRAFT HALTED AWAITING_RECOVERY AWAITING_RANGE STOPPING STOPPED ERROR",
    ),
}
