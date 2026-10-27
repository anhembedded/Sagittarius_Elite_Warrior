"""`EPIC-047H` — the host's answer to `bot refresh-facts`: what it did, in the operator's words.

@details The verb reads and nothing else: it asks the refresher's queue (`IFactsRefreshRequests`) and returns
at once, so the control poller, which also carries a `stop`, never waits on the exchange. Asked inside the
30 seconds after a bot's last read the host does not read again and says when that was.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    HostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_facts_refresh_requests import (
    ON_DEMAND_MIN_INTERVAL_S,
    IFactsRefreshRequests,
    RefreshRequestVerdict,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_command_executor import (
    ExecutionOutcome,
)


def refresh_outcome(
    command: HostCommand, refresh: IFactsRefreshRequests | None
) -> ExecutionOutcome:
    if refresh is None:
        return ExecutionOutcome(False, "this host has no refresh to ask")
    answer = refresh.request(command.bot_id)
    match answer.verdict:
        case RefreshRequestVerdict.QUEUED:
            return ExecutionOutcome(
                True,
                "the host will read the bot's facts, planner inputs and fills again; each carries the time it was read",
            )
        case RefreshRequestVerdict.ALREADY_FRESH:
            return ExecutionOutcome(
                True,
                f"already fresh (read within {ON_DEMAND_MIN_INTERVAL_S} s), read at {answer.read_at}",
            )
        case RefreshRequestVerdict.OFF:
            return ExecutionOutcome(
                False,
                "the host's refresh is off (operations.vps_facts_refresh_interval_s is 0)",
            )
        case RefreshRequestVerdict.UNKNOWN_BOT:
            return ExecutionOutcome(
                False, "no bot has that id on an enabled venue (see `bot list`)"
            )
