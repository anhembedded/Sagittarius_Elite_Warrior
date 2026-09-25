from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.open_position import (
    OpenPosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)

if TYPE_CHECKING:
    # `FillPricing` imports `domain.policies.fee_calculator_policy`, which
    # runs this package's own `__init__.py` (which exports this class) —
    # a top-level import here would be circular. Type-only per
    # `code/quality.md` §2's one documented exception.
    from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.fill_pricing import (
        FillPricing,
    )

logger = logging.getLogger("App.PaperExchange")


class StopManagementPolicy:
    """
    @brief Domain policy for the per-bar position risk-state adjustments that
    run BEFORE order matching (`OrderMatchingPolicy`) checks a bar's
    high/low against `stop_loss_price`: MAE/MFE excursion tracking
    (`BOT-106B`), break-even stop arming (`BOT-105A`), and trailing stop
    ratcheting (`BOT-105A`).
    @details Split out of `paper_exchange.py` once trailing stop's arrival
    pushed that file past the 400-line ceiling (`architecture-rule.md`
    §5.4) — the same reason `open_position.py` itself was split out earlier
    (`EPIC-025D` §5.5). The three methods are one lifecycle, not three
    unrelated ones (the Single-Scope Cohesion counterweight,
    `code/quality.md` §3, applies): `PaperExchange.check_intrabar_stops()`
    calls all three in this exact order, every bar, on the same position
    list, and each reads what the previous one just wrote — excursion
    tracking's `mfe_percent` feeds both stop mechanisms' arm conditions.
    """

    def update_excursion_tracking(
        self,
        positions: Sequence[OpenPosition],
        pricing: FillPricing,
        high: float,
        low: float,
    ) -> None:
        """
        @brief BOT-106B — widens every open position's MAE/MFE from this
        bar's high/low, before any close this same bar removes it from
        the caller's position list — a position's final bar still counts.
        """
        for pos in positions:
            if pos.balance_before_entry <= 0:
                continue
            worst_price, best_price = (
                (low, high) if pos.side is PositionSide.LONG else (high, low)
            )
            worst_value = pricing.mark_to_market(
                pos.side,
                pos.leverage,
                pos.quantity,
                pos.entry_price,
                pos.balance_before_entry,
                worst_price,
            )
            best_value = pricing.mark_to_market(
                pos.side,
                pos.leverage,
                pos.quantity,
                pos.entry_price,
                pos.balance_before_entry,
                best_price,
            )
            worst_pnl_percent = (
                (worst_value - pos.balance_before_entry)
                / pos.balance_before_entry
                * 100
            )
            best_pnl_percent = (
                (best_value - pos.balance_before_entry) / pos.balance_before_entry * 100
            )
            pos.mae_percent = min(pos.mae_percent, worst_pnl_percent)
            pos.mfe_percent = max(pos.mfe_percent, best_pnl_percent)

    def apply_break_even_stops(
        self, positions: Sequence[OpenPosition], trigger_pct: float | None
    ) -> None:
        """
        @brief BOT-105A — once a position's best-seen unrealized profit
        (`pos.mfe_percent`, already widened for this bar by
        `update_excursion_tracking()`) reaches `trigger_pct`, moves
        `stop_loss_price` to `entry_price` exactly once.
        @details Ignores fees (moves to the raw `entry_price`, not
        `entry_price` adjusted for `entry_fee`) — the proposal names both
        as acceptable; the raw price is the simpler, unambiguous choice
        and is what "break-even" means without a fee-aware reading. Always
        a favorable move: a not-yet-triggered `stop_loss_price` sits on
        the losing side of `entry_price` by construction, or is `None`
        (no static stop configured for this run) — either way this only
        ever tightens protection, so it never needs to compare against
        the position's current stop the way a trailing stop would.
        """
        if trigger_pct is None:
            return
        for pos in positions:
            if pos.break_even_armed or pos.mfe_percent < trigger_pct:
                continue
            pos.stop_loss_price = pos.entry_price
            pos.break_even_armed = True
            logger.debug(
                f"[paper-exchange] Break-even armed | {pos.side.value} entry "
                f"{pos.entry_price:,.2f} | MFE {pos.mfe_percent:.2f}% >= "
                f"trigger {trigger_pct:.2f}% | stop moved to entry"
            )

    def apply_trailing_stops(
        self,
        positions: Sequence[OpenPosition],
        activation_pct: float | None,
        offset_pct: float | None,
        high: float,
        low: float,
    ) -> None:
        """
        @brief BOT-105A — once a position's best-seen unrealized profit
        (`pos.mfe_percent`) reaches `activation_pct`, arms its trailing
        stop and, every bar from then on, ratchets `stop_loss_price` to
        `offset_pct` behind the best price seen since arming
        (`pos.trailing_peak_price`).
        @details Unlike `apply_break_even_stops()`'s one-time move, this
        repeats every bar — the peak/trough only ever advances favorably
        (`max()` for LONG, `min()` for SHORT), and the resulting stop only
        ever replaces `stop_loss_price` with a strictly more protective
        value, so a stop already moved further (by break-even or a prior,
        tighter trailing update) is never loosened.
        """
        if activation_pct is None or offset_pct is None:
            return
        offset_fraction = offset_pct / 100.0
        for pos in positions:
            if pos.trailing_armed:
                # Narrowed to `float` here (never `None` once armed — the
                # arm branch below always sets it in the same call), so the
                # `max()`/`min()` below stay `float`-typed for mypy.
                existing_peak = pos.trailing_peak_price
                if existing_peak is None:
                    continue
                peak_price = (
                    max(existing_peak, high)
                    if pos.side is PositionSide.LONG
                    else min(existing_peak, low)
                )
            else:
                if pos.mfe_percent < activation_pct:
                    continue
                pos.trailing_armed = True
                peak_price = high if pos.side is PositionSide.LONG else low
            pos.trailing_peak_price = peak_price

            if pos.side is PositionSide.LONG:
                candidate_stop = peak_price * (1.0 - offset_fraction)
                if pos.stop_loss_price is None or candidate_stop > pos.stop_loss_price:
                    pos.stop_loss_price = candidate_stop
            else:
                candidate_stop = peak_price * (1.0 + offset_fraction)
                if pos.stop_loss_price is None or candidate_stop < pos.stop_loss_price:
                    pos.stop_loss_price = candidate_stop
            logger.debug(
                f"[paper-exchange] Trailing stop | {pos.side.value} peak "
                f"{peak_price:,.2f} | offset {offset_pct:.2f}% | "
                f"stop now {pos.stop_loss_price:,.2f}"
            )
