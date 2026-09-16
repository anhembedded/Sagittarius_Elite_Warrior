"""`EPIC-003E3` — everything the Backtest screen reads from `IConfig`,
read once, in one place.

@details These seven values were seven separate reads spread through a
272-line `__init__`, three of them with their own hand-rolled
parse-or-fall-back ladder. Two problems that caused:

1. **The fallbacks were invisible.** What a hand-edited `user_config.json`
   with `BACKTEST_LOG_MAX_ENTRIES: "many"` actually does was three lines of
   `try/except` buried between unrelated wiring. Here it is the module's
   subject, and it is tested directly.
2. **`bool` is an `int` in Python.** `int(True)` is `1`, so a config value
   of `true` for a count silently becomes a limit of one. The original
   guarded this for `BACKTEST_LOG_MAX_ENTRIES` and *not* for
   `BACKTEST_CHART_KLINES_FETCH_LIMIT` — one shared `_positive_int()` is
   how that stops being a per-field accident.

Reading is separated from applying: this returns a value object, and the
Presenter decides what to do with it. That is what makes "which config
does this screen depend on" answerable by reading one file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    default_symbol,
)
from sagittarius_engine.extensions.pyside_mvc.mvc.base_view import DEV_MODE_CONFIG_KEY

#: Default safety cap on chart candles.
#:
#: This used to be 5 000, which silently truncated the chart to the most
#: recent slice of a much longer run: a 52 000-candle backtest drew its 960
#: trade markers across the full range while only the last 5 000 candles
#: existed on the chart, so panning left ran out of candles and older
#: markers stood over empty space. Measured cost of lifting it: a 52 147-
#: candle load takes 179ms once (vs 63ms for 5 000) and pans at 18.2ms/
#: frame — identical to 5 000, because viewport windowing draws only the
#: visible ~200 bars. Range coverage itself is still checked by a compact
#: SQLite aggregate and is not inferred from this window.
DEFAULT_CHART_KLINES_FETCH_LIMIT = 200_000


@dataclass(frozen=True)
class BacktestScreenConfig:
    """@brief The Backtest screen's configured values, already validated."""

    symbol: str
    #: Empty, or a value the caller still has to check against the domain's
    #: timeframes — this object deliberately does NOT validate it, because
    #: an invalid interval must leave the ViewModel's own default in place
    #: rather than be replaced by a second opinion about what "default"
    #: means (`EPIC-014`).
    default_interval: str
    is_dev_mode: bool
    log_max_entries: int
    chart_klines_fetch_limit: int
    chart_opengl_enabled: bool
    chart_cached_interaction_enabled: bool

    @classmethod
    def read_from(
        cls,
        config: Any,
        *,
        fallback_symbol: str,
        default_log_max_entries: int,
    ) -> BacktestScreenConfig:
        """Read every key this screen depends on, applying each fallback.

        @param config The shared `IConfig` — the same one Settings edits.
        """
        config_values = config.get_all()
        return cls(
            symbol=default_symbol(config_values, fallback_symbol),
            default_interval=config_values.get("DEFAULT_INTERVAL") or "",
            is_dev_mode=bool(config.get(DEV_MODE_CONFIG_KEY, False)),
            log_max_entries=_positive_int(
                config.get(
                    ConfigKeys.BACKTEST_LOG_MAX_ENTRIES.value,
                    default_log_max_entries,
                ),
                default_log_max_entries,
            ),
            chart_klines_fetch_limit=_positive_int(
                config.get(
                    ConfigKeys.BACKTEST_CHART_KLINES_FETCH_LIMIT.value,
                    DEFAULT_CHART_KLINES_FETCH_LIMIT,
                ),
                DEFAULT_CHART_KLINES_FETCH_LIMIT,
            ),
            chart_opengl_enabled=bool(
                config.get(ConfigKeys.BACKTEST_CHART_OPENGL_ENABLED.value, False)
            ),
            #: `BUG-009`: defaults to OFF. The cached-frame preview replaces
            #: live rendering with a translated snapshot of the last frame,
            #: and every symptom the user reported follows from that one
            #: decision — the snapshot holds no pixels past its own edge
            #: (blank band), its Y axis cannot re-autoscale (vertical jump
            #: on release), and its indicator and volume windows are frozen
            #: at capture time. None of that is fixable while the frame is a
            #: snapshot. Its premise no longer holds either:
            #: `CHART_CARD_MAX_ZOOM_OUT_CANDLES` caps the plot at ~200
            #: visible candles, so a real pan re-render costs ~32ms
            #: regardless of how much history is loaded. Set this key to
            #: true to opt back in.
            chart_cached_interaction_enabled=bool(
                config.get(
                    ConfigKeys.BACKTEST_CHART_CACHED_INTERACTION_ENABLED.value,
                    False,
                )
            ),
        )


def _positive_int(raw: object, fallback: int) -> int:
    """`int(raw)` if that is a usable count, else `fallback`.

    `bool` is rejected before `int()` sees it: `int(True) == 1`, so a
    config value of `true` for a limit would silently mean "one entry" —
    a cap the user never asked for and cannot see.
    """
    if isinstance(raw, bool):
        return fallback
    try:
        value = int(raw)  # type: ignore[call-overload]
    except (ValueError, TypeError):
        return fallback
    return value if value > 0 else fallback
