"""`IMarketStream`, implemented over the commands the handlers already run.

**Why it dispatches instead of holding `ILiveStreamService`.** The service is
right there, and calling it directly would be one hop shorter — and would
bypass `StartLiveStreamCommandHandler`, which is where the module logs what
was subscribed and turns a bare `bool` into a message a screen can show.
Worse, it would leave two paths to the same websocket: the module's own CLI
(`stream_cmd.py`, `stream_cli_handler.py`) dispatches these commands, so a
port that skipped them would mean the CLI and the screens could diverge the
day either handler grows a rule. Dispatching keeps one path, which is the
same reasoning `MarketDataSyncService` next door records.

**What it adds.** Exactly the translation: the published `owner_id` becomes
the command's `owner`, and the command's response becomes `StreamOutcome`.
It decides nothing — a dispatch that answers nothing at all is reported as a
failure rather than defaulted to success, because that was the one real
defect in the `getattr(response, "success", True)` this port replaces.
"""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream.command import (
    StartLiveStreamCommand,
    StartLiveStreamResponse,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream.command import (
    StopLiveStreamCommand,
    StopLiveStreamResponse,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
    StreamOutcome,
)

#: What a caller is told when the dispatcher answered nothing — no handler
#: bound, or a test double that returns `None`. Named because it is the one
#: message this class writes itself.
_NO_ANSWER = "the live stream command was not answered"


class MarketStreamService(IMarketStream):
    """The module's answer to "stream these symbols for me"."""

    def __init__(self, dispatcher: ICommandDispatcher) -> None:
        self._dispatcher = dispatcher

    def start(
        self, owner_id: str, symbols: Sequence[str], interval: TimeFrame
    ) -> StreamOutcome:
        # `StartLiveStreamCommand`'s own validators refuse an empty owner and
        # an empty symbol list, and upper-case the symbols — so the port's
        # promises are enforced by the command rather than re-implemented
        # here, where the two copies could drift.
        command = StartLiveStreamCommand(
            owner=owner_id, symbols=list(symbols), interval=interval
        )
        return self._outcome(self._dispatcher.dispatch(StartLiveStreamCommand, command))

    def stop(self, owner_id: str) -> StreamOutcome:
        command = StopLiveStreamCommand(owner=owner_id)
        return self._outcome(self._dispatcher.dispatch(StopLiveStreamCommand, command))

    @staticmethod
    def _outcome(response: object) -> StreamOutcome:
        """Translate the module's own response into the published one.

        Matched by **type**, not by probing for a `success` attribute: these
        two classes are this module's, so it knows them by name, and the
        `getattr` probing this port exists to delete has no business
        reappearing in the port's own implementation
        (`architecture-rule.md` §2.1). Anything else means the dispatch was
        not answered — a `None`, or a test double that returns one — and the
        honest report for that is a failure with a message, never the old
        `getattr(response, "success", True)` reading it as success.
        """
        if isinstance(response, StartLiveStreamResponse | StopLiveStreamResponse):
            return StreamOutcome(success=response.success, message=response.message)
        return StreamOutcome(success=False, message=_NO_ANSWER)
