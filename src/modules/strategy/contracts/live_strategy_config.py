"""`EPIC-022A` — what the user chose to run live, as plain data.

@details Deliberately holds **no live objects** (no `StrategyEngine`, no
`LiveTradingCoordinator`): this is the value that gets compared, logged,
persisted to `IConfig` and restored next session, and a value object that
also carried a running engine could not do any of those things. Building
the engine pair from one of these is `LiveStrategyFactory`'s job, and
holding the built pair is `LiveStrategySession`'s.

`strategy_params` is stored as an immutable `MappingProxyType` snapshot
rather than the caller's dict — the UI keeps editing its own dict while
the user types, and an armed config that silently changed underneath the
running engine would make "what is actually running" unanswerable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

#: `EPIC-021G`'s own defaults, repeated here as the value object's own
#: floor so a config missing these keys still produces a usable arming
#: rather than a `TypeError` at construction.
DEFAULT_SIZING_PERCENT = 20.0
DEFAULT_LEVERAGE = 1.0

#: Bounds this value object enforces on itself.
#:
#: They live in the domain, not on the Qt spin boxes that happen to be one
#: way of entering them (`BOT-125` review): a spin box only constrains
#: *typing*, and these values also arrive from `app_config.json` at boot
#: and from a restored session, neither of which passes through a widget.
#: Before this, a hand-edited `"trading.live_leverage": 0` armed happily
#: and reached position sizing.
#:
#: `MAX_LEVERAGE` is the exchange-wide ceiling, NOT a per-symbol limit —
#: Binance sets the real cap per symbol and it is lower for most of them.
#: `domain-truth-rule.md` forbids hard-coding a universal exchange filter
#: as if it were the truth, so this is deliberately only a sanity bound
#: ("no one can ask for 500x"); the binding per-symbol limit comes from
#: `SymbolMarketMetadata` on the order path, which is where a real filter
#: belongs.
MIN_SIZING_PERCENT = 0.1
MAX_SIZING_PERCENT = 100.0
MIN_LEVERAGE = 1.0
MAX_LEVERAGE = 125.0

#: The intervals a live strategy may be armed on, as `TimeFrame` members
#: rather than typed-out strings (`BOT-125` review): a mistyped `"1hr"`
#: here would be a constant nothing ever matches, discovered only by a bot
#: that silently never trades. Referencing the enum makes it an import
#: error instead.
#:
#: A curated subset of the domain's sixteen codes, and the exclusions are
#: the point. `1s` is a real Binance interval but a different risk class
#: entirely — every indicator's warm-up, every limit in
#: `TradingLimitPolicy`, and the once-per-minute assumption behind
#: `StrategyOverlayCoordinator`'s redraw are all sized for minutes and
#: above. `1w`/`1M` are the opposite problem: a strategy on monthly bars
#: emits a signal a few times a decade, so arming one reads as a working
#: bot that is in fact doing nothing. Both would arm happily and then
#: behave in a way the screen could not explain.
SUPPORTED_LIVE_INTERVALS: tuple[str, ...] = (
    TimeFrame.ONE_MINUTE.value,
    TimeFrame.THREE_MINUTES.value,
    TimeFrame.FIVE_MINUTES.value,
    TimeFrame.FIFTEEN_MINUTES.value,
    TimeFrame.THIRTY_MINUTES.value,
    TimeFrame.ONE_HOUR.value,
    TimeFrame.FOUR_HOURS.value,
    TimeFrame.ONE_DAY.value,
)


def _require_in_range(
    value: float, minimum: float, maximum: float, field_name: str
) -> None:
    """@raises ValueError Naming the field and the bound it broke.

    @details A `ValueError` rather than a clamp: silently correcting an
    out-of-range value would arm a bot the user did not ask for, and every
    caller already has somewhere to put the message —
    `ArmStrategyCommandHandler` turns it into `INVALID_PARAMS` with this
    text attached, and `boot()`'s `_arm_from_config` logs it and starts
    disarmed.
    """
    if not minimum <= value <= maximum:
        raise ValueError(
            f"{field_name} must be in the range [{minimum:g}, {maximum:g}]; "
            f"got {value:g}."
        )


@dataclass(frozen=True)
class LiveStrategyConfig:
    """@brief One complete answer to "what should the bot run right now".

    @details Every field a user picks on the Trading screen's strategy
    card, plus nothing else. `symbol`/`interval` are part of the config,
    not separate state, because `MarketTickEventHandler`'s single-symbol/
    single-interval rule (`BUG-085`) makes them inseparable from the
    engine: changing either one requires the same rebuild that changing
    the strategy does.
    """

    strategy_key: str
    symbol: str
    interval: str
    strategy_params: Mapping[str, Any] = field(default_factory=dict)
    sizing_percent: float = DEFAULT_SIZING_PERCENT
    leverage: float = DEFAULT_LEVERAGE

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "strategy_params", MappingProxyType(dict(self.strategy_params))
        )
        _require_in_range(
            self.sizing_percent,
            MIN_SIZING_PERCENT,
            MAX_SIZING_PERCENT,
            "sizing_percent",
        )
        _require_in_range(self.leverage, MIN_LEVERAGE, MAX_LEVERAGE, "leverage")
        # An empty interval is "nothing configured yet" and is reported by
        # `is_complete`; only a NON-empty unsupported one is an error here,
        # so a half-filled card still constructs while a `1M` armed from a
        # hand-edited config does not.
        if self.interval and self.interval not in SUPPORTED_LIVE_INTERVALS:
            raise ValueError(
                f"Timeframe {self.interval!r} cannot be used for live trading. "
                f"Choose one of: {', '.join(SUPPORTED_LIVE_INTERVALS)}."
            )

    @property
    def is_complete(self) -> bool:
        """@brief Whether this names a runnable target at all.

        @details `boot()` historically gated on
        `if live_symbol and live_strategy_key and live_interval` — the same
        three-way check, now asked of the value itself instead of being
        re-typed at each call site.
        """
        return bool(self.strategy_key and self.symbol and self.interval)
