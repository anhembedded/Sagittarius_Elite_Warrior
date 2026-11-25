"""`EPIC-047F` — a bot's own log lines, from the host over the bridge's `bot_log` call.

@details One read-only call per ask, bounded by the host (`MAX_LINES_PER_READ`), no stream held: the tab asks again for the
selected bot only. The call blocks until the host answers, so the caller runs it off the UI thread (`RemoteBotLogFeed`). A link
that is down, a host that does not answer in time or one that serves no log is a `BotLogUnavailableError` with a sentence;
nothing is read from anywhere else (decision record 2026-10-27, D5).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_log_chunk import (
    BotLogChunk,
    BotLogLineOfTheHost,
    BotLogUnavailableError,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.link_host_world import LinkHostWorld
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    CallFailedError,
    CallTimedOutError,
    LinkLostError,
)

NOT_CONNECTED = (
    "Not connected to the host: the log keeps the lines it has until the link is back."
)


class HostBotLog:
    def __init__(self, world: LinkHostWorld) -> None:
        self._world = world

    def read(self, bot_id: str, since: int) -> BotLogChunk:
        link = self._world.live_link()
        if link is None:
            raise BotLogUnavailableError(NOT_CONNECTED)
        try:
            data = link.call("bot_log", {"bot_id": bot_id, "since": since})
        except LinkLostError:
            raise BotLogUnavailableError(NOT_CONNECTED) from None
        except CallTimedOutError:
            raise BotLogUnavailableError(
                "The host did not answer for the log in time."
            ) from None
        except CallFailedError as refused:
            raise BotLogUnavailableError(
                f"The host cannot serve this log: {refused}"
            ) from None
        return _chunk_of(data, since)


def _chunk_of(data: dict[str, object], since: int) -> BotLogChunk:
    raw_lines, cursor = data.get("lines"), data.get("next")
    if not isinstance(raw_lines, list) or type(cursor) is not int:
        raise BotLogUnavailableError("The host's log could not be read by this build.")
    lines: list[BotLogLineOfTheHost] = []
    for raw in raw_lines:
        if not isinstance(raw, dict):
            raise BotLogUnavailableError(
                "The host's log could not be read by this build."
            )
        seq, at, level, text = (raw.get(k) for k in ("seq", "at", "level", "text"))
        if type(seq) is not int or not all(
            isinstance(v, str) for v in (at, level, text)
        ):
            raise BotLogUnavailableError(
                "The host's log could not be read by this build."
            )
        lines.append(BotLogLineOfTheHost(seq, str(at), str(level), str(text)))
    return BotLogChunk(tuple(lines), max(cursor, since))
