"""The intervals the Database screen can sync (`BOT-167`).

The screen's syncs fetch one market (`EPIC-027A`: Spot, until its own market
selector exists); the list it offers is that market's own, from the one rule
(`core/vo/market_timeframes.py`). Moving the screen to Futures is a change to
`SYNC_MARKET` here, and `1s` leaves the list with it, so no Futures 1-second
sync can be started.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_timeframes import timeframes_for
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType

SYNC_MARKET = MarketType.SPOT
SYNC_INTERVALS: list[str] = [tf.value for tf in timeframes_for(SYNC_MARKET)]
