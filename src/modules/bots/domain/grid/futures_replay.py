"""`EPIC-039K` — a Futures Grid's ladder replayed on candles: position, funding, liquidation.

@par A model, not a replay of the executor
**This is the position model (`grid_position_model.py`, `EPIC-039B`) walked over candles with
costs, funding and liquidation added. It is not a replay of a Futures executor**, because none
exists yet (`EPIC-039H`). The Spot replay runs the live executor's own reactions; this one
cannot, so it can drift from what a Futures bot would do. Once `039H` lands, this must either
replay that executor the way `grid_replay.py` does, or be tested against it on the same fills
(position, average entry and realised profit after each fill). Until then every Futures result
carries `futures` and the fill rule below, and nothing here is evidence about live behaviour.

@par How it walks
`simulate_grid` orders each candle's steps from the 1-second klines; this engine answers it
(`replay_engine.py`) under the Spot fill rule (no fill on touch, one fill per level per step, a
counter rests from the next step). A step is walked leg by leg and on each leg whatever the
price reaches first happens first (a level, the liquidation price, an exit), so a candle holding
a liquidating wick and the recovery liquidates. Fills book on `PositionBook` (shared with the
model); commissions are maker on ladder fills and taker on the opening trade and exits; funding
(`futures_funding.py`) comes out of the isolated margin; liquidation (`futures_liquidation.py`)
forfeits it and cancels the orders. An exit closes the position at market whatever its
direction: the parameters name range edges, not a side.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_benchmark import (
    HoldBenchmark,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_funding import (
    FundingSettlement,
    SettlementCursor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_ladder import Ladder
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_leg_events import (
    LegActions,
    LegEvent,
    LegSituation,
    leg_events,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_liquidation import (
    HeldPosition,
    Leveraged,
    distance_to_liquidation,
    is_liquidated_at,
    isolated_margin,
    liquidation_price,
    loss_of_liquidation,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_outcome import (
    FuturesOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_run_terms import (
    FuturesRunTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    BacktestFill,
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    Leg,
    PriceBar,
    PriceStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    crossed_exit_in_range,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    LevelSizing,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_position_model import (
    PositionBook,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.replay_engine import (
    ReplayEngine,
    ReplayOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

_ZERO = Decimal(0)


class FuturesReplay(ReplayEngine):
    """@brief A position grid's ladder, its books and its fills, advanced one step at a time."""

    def __init__(
        self,
        params: GridParams,
        terms: ExchangeTerms,
        run: FuturesRunTerms,
        first: PriceBar,
    ) -> None:
        self._params = params
        self._terms = terms
        self._run = run
        self._leveraged = Leveraged(params.leverage, run.brackets)
        self._plan = plan(params, terms, first.open, LevelSizing.EQUAL_QUANTITY)
        self._ladder = Ladder(self._plan, terms.tick_size)
        self._book = PositionBook(self._plan.opening_quantity, first.open)
        self._fills: list[BacktestFill] = []
        self._maker_fees = _ZERO
        self._taker_fees = _ZERO
        self._cycles = 0
        self._adjustment = _ZERO
        self._funding_paid = _ZERO
        self._funding_on_position = _ZERO
        self._charged = 0
        self._due = SettlementCursor(run.funding, after=first.time)
        self._hold = HoldBenchmark(self._plan.opening_quantity, first.open)
        self._stop: StopReason | None = None
        self._stop_detail = ""
        self._liquidation_price: Decimal | None = None
        self._margin_lost = _ZERO
        self._closest: Decimal | None = None
        self._ran_in_bar = False
        self._open(first)

    # -- what the simulator reads ---------------------------------------- #

    @property
    def plan(self) -> GridPlan:
        return self._plan

    @property
    def stopped(self) -> bool:
        return self._stop is not None

    def may_trade_in(self, low: Decimal, high: Decimal) -> bool:
        if self._ladder.reaches(low, high):
            return True
        stop, take = self._params.stop_loss_price, self._params.take_profit_price
        if crossed_exit_in_range(low, high, stop, take, self._params.direction):
            return True
        limit = self._liquidation_limit()
        if limit is None:
            return False
        held = self._held()
        return is_liquidated_at(low if held.quantity > 0 else high, held, limit)

    def value_at(self, price: Decimal) -> Decimal:
        return (
            self._params.capital_quote
            + self._book.realised
            + self._adjustment
            - self._maker_fees
            - self._taker_fees
            - self._funding_paid
            + self._unrealised(price)
        )

    def benchmark_at(self, price: Decimal) -> Decimal:
        return self._hold.value_at(self._params.capital_quote, price)

    def outcome(self, last_close: Decimal) -> ReplayOutcome:
        liquidated = self._stop is StopReason.LIQUIDATED
        return ReplayOutcome(
            fills=tuple(self._fills),
            grid_profit=self._book.realised
            + self._adjustment
            - self._maker_fees
            - self._taker_fees,
            unrealised=self._unrealised(last_close),
            completed_cycles=self._cycles,
            stop_reason=self._stop or StopReason.END_OF_DATA,
            maker_fees=self._maker_fees,
            taker_fees=self._taker_fees,
            final_states=self._ladder.drawn(),
            average_cost=None if self._book.position == 0 else self._book.entry,
            stop_detail=self._stop_detail,
            futures=FuturesOutcome(
                direction=self._params.direction,
                leverage=self._params.leverage,
                funding_included=self._run.funding.included,
                funding_note=self._run.funding.note,
                funding_paid=self._funding_paid,
                funding_settlements_charged=self._charged,
                final_position=self._book.position,
                liquidated=liquidated,
                liquidation_price=self._liquidation_price if liquidated else None,
                margin_lost=self._margin_lost,
                closest_to_liquidation=_ZERO if liquidated else self._closest,
            ),
        )

    # -- advancing --------------------------------------------------------- #

    def run_step(self, step: PriceStep) -> None:
        self._ran_in_bar = True
        self._settle(step.time, step.open)
        self._liquidate_if_opened_beyond_the_limit(step)
        self._ladder.start_step()
        for leg in step.legs:
            if self._stop is not None:
                return
            if leg is Leg.DOWN:
                self._walk(step, falling=True)
            else:
                self._walk(step, falling=False)

    def _liquidate_if_opened_beyond_the_limit(self, step: PriceStep) -> None:
        """A step that opens past the liquidation price (a gap, or the last step's move) ends
        the run where it opened, before any leg runs: the exchange could not have closed it at a
        price the market never traded, and a leg moving away must not fill into the position."""
        limit = self._liquidation_limit()
        if (
            self._stop is None
            and limit is not None
            and is_liquidated_at(step.open, self._held(), limit)
        ):
            self._liquidate(step.open, step.time)

    def close_bar(self, bar: PriceBar, end: datetime) -> None:
        if self._stop is not None:
            return
        self._settle(end, bar.close)
        if not self._ran_in_bar:
            self._note_distance(bar.low if self._book.position > 0 else bar.high)
        self._ran_in_bar = False

    # -- the opening ------------------------------------------------------- #

    def _open(self, first: PriceBar) -> None:
        quantity = self._plan.opening_quantity
        if quantity != 0:
            side = OrderSide.BUY if quantity > 0 else OrderSide.SELL
            self._hold.fee = abs(quantity) * first.open * self._run.taker_fee
            self._taker_fees += self._hold.fee
            self._record(
                first.time, side, first.open, abs(quantity), "Open", fee=self._hold.fee
            )

    # -- one leg ----------------------------------------------------------- #

    def _walk(self, step: PriceStep, *, falling: bool) -> None:
        while self._stop is None:
            events = self._events(step, falling)
            if not events:
                break
            # Whatever the price reaches first happens first. `events` lists a liquidation,
            # then an exit, then a fill, and `max`/`min` keep the first of equals: at one
            # price the exchange liquidates before a stop order could fill.
            chosen = (
                max(events, key=lambda e: e.trigger)
                if falling
                else min(events, key=lambda e: e.trigger)
            )
            chosen.run()
        if self._stop is None:
            self._note_distance(step.low if falling else step.high)

    def _events(self, step: PriceStep, falling: bool) -> list[LegEvent]:
        return leg_events(
            LegSituation(
                step=step,
                falling=falling,
                liquidation_limit=self._liquidation_limit(),
                position=self._book.position,
                stop_loss=self._params.stop_loss_price,
                take_profit=self._params.take_profit_price,
                tick=self._terms.tick_size,
                direction=self._params.direction,
            ),
            self._ladder,
            LegActions(self._liquidate, self._exit, self._fill),
        )

    # -- what happens ------------------------------------------------------ #

    def _fill(self, index: int, at: datetime) -> None:
        price = self._ladder.price_of(index)
        side, quantity = self._ladder.fill(index)
        before = self._book.position
        self._book.fill(side, quantity, price)
        if abs(self._book.position) < abs(before):
            self._cycles += 1
        if before * self._book.position <= 0:
            self._funding_on_position = _ZERO
        fee = quantity * price * self._run.maker_fee
        self._maker_fees += fee
        self._record(at, side, price, quantity, None, fee=fee, level_index=index)
        self._note_distance(price)

    def _exit(self, reason: StopReason, price: Decimal, at: datetime) -> None:
        position = self._book.position
        if position != 0:
            side = OrderSide.SELL if position > 0 else OrderSide.BUY
            fee = abs(position) * price * self._run.taker_fee
            self._book.fill(side, abs(position), price)
            self._taker_fees += fee
            self._record(at, side, price, abs(position), "Exit", fee=fee)
        self._funding_on_position = _ZERO
        self._ladder.cancel_all()
        self._stop = reason

    def _liquidate(self, price: Decimal, at: datetime) -> None:
        held = self._held()
        margin = isolated_margin(held, self._params.leverage)
        side = OrderSide.SELL if held.quantity > 0 else OrderSide.BUY
        realised_before = self._book.realised
        self._book.fill(side, abs(held.quantity), price)
        loss = loss_of_liquidation(margin, self._book.realised - realised_before)
        self._adjustment += loss.realised_adjustment
        self._margin_lost = loss.margin_lost
        self._liquidation_price = price
        self._funding_on_position = _ZERO
        self._record(at, side, price, abs(held.quantity), "Liquidation")
        self._ladder.cancel_all()
        self._stop = StopReason.LIQUIDATED
        self._stop_detail = (
            f"The position reached its liquidation price {price}; its margin "
            f"{margin:.4f} is forfeited and the orders are cancelled"
        )

    # -- funding ----------------------------------------------------------- #

    def _settle(self, until: datetime, price: Decimal) -> None:
        """Charge the settlements due by `until` on what is held, `price` standing in for a
        record without a mark price."""
        while self._stop is None:
            settlement = self._due.next_due(until)
            if settlement is None:
                return
            self._charge(settlement, settlement.mark_price or price)

    def _charge(self, settlement: FundingSettlement, mark: Decimal) -> None:
        charge = self._run.charge
        self._hold.funding += charge(self._hold.quantity, mark, settlement.rate)
        position = self._book.position
        if position == 0:
            return
        paid = charge(position, mark, settlement.rate)
        self._funding_paid += paid
        self._funding_on_position += paid
        self._charged += 1
        limit = self._liquidation_limit()
        held = self._held()
        if limit is not None and is_liquidated_at(mark, held, limit):
            self._liquidate(mark, settlement.time)
        else:
            self._note_distance(mark)

    # -- helpers ----------------------------------------------------------- #

    def _held(self) -> HeldPosition:
        return HeldPosition(
            self._book.position, self._book.entry, self._funding_on_position
        )

    def _liquidation_limit(self) -> Decimal | None:
        return liquidation_price(self._held(), self._leveraged)

    def _unrealised(self, price: Decimal) -> Decimal:
        return self._book.position * (price - self._book.entry)

    def _note_distance(self, price: Decimal) -> None:
        held = self._held()
        limit = self._liquidation_limit()
        if held.quantity == 0 or limit is None:
            return
        distance = distance_to_liquidation(price, held, limit)
        if self._closest is None or distance < self._closest:
            self._closest = distance

    def _record(
        self,
        at: datetime,
        side: OrderSide,
        price: Decimal,
        quantity: Decimal,
        tag: str | None,
        *,
        fee: Decimal = _ZERO,
        level_index: int | None = None,
    ) -> None:
        self._fills.append(
            BacktestFill(
                at,
                side,
                price,
                quantity,
                fee,
                level_index,
                maker=level_index is not None,
                tag=tag,
            )
        )
