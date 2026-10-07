"""The retired `exchange.market_data_venue` setting, read for one purpose only.

@details The Data Source option was removed: a screen with no trading venue always
reads the public mainnet (`DEFAULT_MARKET_DATA_VENUE`), a venue screen its own
venue's market (`BUG-172`). A `user_config.json` written before that may still hold
the key, and `label_legacy_store` needs the value once: the candles stored before
`BUG-172` belong to the venue it named when they were synced, which is the only
evidence of where they came from. This is the one place that names the key; no
other file may (`test_a_venue_screen_charts_its_own_venues_market.py`).

Retire when: no install can still hold unlabelled legacy candles (the labelling is
done once per data directory, `legacy_store_label.MARKER`).
"""

from __future__ import annotations

import logging

from sagittarius_engine.interfaces.i_config import IConfig

logger = logging.getLogger("App.Database")

#: The retired key, as a configuration written by an earlier build spells it.
RETIRED_KEY = "exchange.market_data_venue"


def retired_data_source_setting(config: IConfig) -> object:
    """@brief What an earlier build's configuration says the Data Source was.

    @return The raw value, or `None` when the key is absent (the earlier build then
    read its default, the mainnet). When the key is present it is **ignored** for
    everything but the legacy-candle labelling, and that is logged once.
    """
    raw = config.get(RETIRED_KEY, None)
    if raw is not None:
        logger.info(
            "[retired-setting] %s=%r is ignored: screens with no trading venue "
            "always read the public mainnet, and every venue screen its own "
            "venue's market. It only labels candles stored by an earlier build.",
            RETIRED_KEY,
            raw,
        )
    return raw
