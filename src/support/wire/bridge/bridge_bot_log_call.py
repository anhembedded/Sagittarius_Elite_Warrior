"""`EPIC-047F` — the bridge's `bot_log` call: one bot's own log lines after a cursor, read-only and bounded.

@details `{"type":"call","id":n,"method":"bot_log","params":{"bot_id":"<six characters>","since":<int, 0 = the newest>}}` is
answered by `{"lines":[{"seq","at","level","text"}…],"next":<cursor>}`. The host keeps only lines of `Bot <id>: …` at INFO or
above, so the filter by bot is made where the files are (a bot's file holds that bot's lines and no other), and the page is
bounded by the host's own limits (`IBridgeBotLog`). It holds no stream: the desktop asks again for the selected bot only. It is
a read of a local file, so it runs on the session's thread like `snapshot`; a build with no log port answers `no_bot_log`.
"""

from __future__ import annotations

import re

from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import CallError
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_bot_log import (
    IBridgeBotLog,
)

_BOT_ID = re.compile(r"[a-z0-9]{6}")


def serve_bot_log(
    log: IBridgeBotLog | None, params: dict[str, object]
) -> dict[str, object]:
    if log is None:
        raise CallError("no_bot_log", "this host serves no bot log")
    bot_id, since = params.get("bot_id"), params.get("since", 0)
    if type(bot_id) is not str or not _BOT_ID.fullmatch(bot_id):
        raise CallError("bad_bot_log", "bot_id is six characters of a-z and 0-9")
    if type(since) is not int or since < 0:
        raise CallError("bad_bot_log", "since is a whole number, zero or more")
    page = log.read(bot_id, since)
    return {
        "lines": [
            {"seq": line.seq, "at": line.at, "level": line.level, "text": line.text}
            for line in page.lines
        ],
        "next": page.next_since,
    }
