"""`EPIC-027C` — the exchange's order rules for one symbol in one market, as a
backtest applies them. Its own file per `architecture-rule.md` §5, the same
reasoning `PartialTakeProfitLevel` applies."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExchangeFilters:
    """
    @brief The LOT_SIZE, minimum-notional and PRICE_FILTER values a simulated
    fill must obey (ADR `DECISION_2026-09-26_spot_market_axis.md` D5).
    @details Copied from the exchange's metadata for the backtest's own
    (market, symbol) before the run, so the run and its result carry the exact
    values it used — a later metadata refresh cannot change what a finished
    run claims. `BrokerSimulationConfig.exchange_filters is None` means no
    metadata was available and no filter was applied; the result says so
    rather than inventing a default rule.
    """

    #: LOT_SIZE `stepSize`: an entry quantity is floored to a multiple of it.
    step_size: float
    #: LOT_SIZE `minQty`: an entry below it is rejected.
    min_quantity: float
    #: NOTIONAL / MIN_NOTIONAL: an entry whose `quantity * price` is below it
    #: is rejected.
    min_notional: float
    #: PRICE_FILTER `tickSize`: one tick of slippage is this far.
    tick_size: float

    def __post_init__(self) -> None:
        if self.step_size <= 0:
            raise ValueError(f"step_size must be positive, got {self.step_size}")
        if self.tick_size <= 0:
            raise ValueError(f"tick_size must be positive, got {self.tick_size}")
        if self.min_quantity < 0:
            raise ValueError(
                f"min_quantity must be non-negative, got {self.min_quantity}"
            )
        if self.min_notional < 0:
            raise ValueError(
                f"min_notional must be non-negative, got {self.min_notional}"
            )
