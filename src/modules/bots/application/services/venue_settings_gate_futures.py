"""`EPIC-039E` — the Futures venue's settings gate: ensure, read back, compare (decision D3, O5).

@details `ensure` runs **before any order** and does, in this order:
  1. the account's position mode must be One-way: Hedge is refused, and the gate has no way to
     change the mode (account-wide; Binance refuses it with open orders `-4067` or a position
     `-4068`, and another bot or the owner's desk may be using it);
  2. the symbol's margin type and leverage are read (`symbolConfig`; `positionRisk` v3 carries
     neither, `BUG-114`);
  3. only if one differs from the request: the symbol must be flat. The error-code page lists
     `-4047` (margin type with open orders), `-4048` (with a position) and `-4161` (an isolated
     leverage reduction with a position); the gate says so in words instead of passing a raw
     `-4xxx`. The REST pages for Change Initial Leverage and Change Margin Type could not be
     rendered (a script-built page), so whether leverage may change with orders open is **not**
     established and the gate assumes it may not;
  4. margin type is set, then leverage, each only if it differs. A change is signed account
     activity, gated like a cancel, so it needs the venue's order session open (Start opens it
     first); a closed one answers `CHANGE_NOT_PERMITTED`;
  5. both are **read back** and compared: a difference the exchange did not confirm is a
     `SETTINGS_MISMATCH` naming both values, never a start.

A setting that already matches is not written, so a Resume of a bot whose orders rest passes
untouched. `verify` is steps 1, 2 and the comparison.

@par Extension cases
  · Cross margin - one more `_MARGIN_TYPES` row is already there; the profile allows it;
  · Multi-Assets mode - another read in step 1 beside the position mode.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_settings_gate import (
    IVenueSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.margin_mode import MarginMode
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_settings_gate_result import (
    ENSURED,
    GateOutcome,
    GateRequest,
    GateResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_rejected_error import (
    AccountControlRejectedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_unavailable_error import (
    AccountControlUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)

logger = logging.getLogger("App.Bots.FuturesGate")

_MARGIN_TYPES: dict[MarginMode, MarginType] = {
    MarginMode.ISOLATED: MarginType.ISOLATED,
    MarginMode.CROSS: MarginType.CROSSED,
}

HEDGE_WORDS = (
    "The account is in Hedge Mode; this app trades One-way only, and it never changes "
    "the account's position mode"
)


class FuturesSettingsGate(IVenueSettingsGate):
    def __init__(self, ports: IVenueTradingPorts) -> None:
        self._ports = ports

    def ensure(self, request: GateRequest) -> GateResult:
        bound = self._bound(request)
        if isinstance(bound, GateResult):
            return bound
        before = self._read(bound, request)
        if isinstance(before, GateResult):
            return before
        if not _differences(before, request):
            return ENSURED
        busy = _busy_symbol(bound, request)
        if busy is not None:
            return busy
        refused = self._write(bound, request, before)
        if refused is not None:
            return refused
        return self.verify(request)

    def verify(self, request: GateRequest) -> GateResult:
        bound = self._bound(request)
        if isinstance(bound, GateResult):
            return bound
        now = self._read(bound, request)
        if isinstance(now, GateResult):
            return now
        differences = _differences(now, request)
        if not differences:
            return ENSURED
        return GateResult(
            GateOutcome.SETTINGS_MISMATCH,
            f"{request.symbol}: " + "; ".join(differences),
        )

    def _bound(self, request: GateRequest) -> VenueTradingPorts | GateResult:
        """The venue's ports, once its connection is up and its account is One-way."""
        try:
            ports = self._ports.get(request.venue)
        except VenueNotEnabledError:
            return _unreadable(f"{request.venue.display_name} is not enabled")
        status = ports.account_snapshot.check_connection()
        if (
            status.failure is ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED
            or status.position_mode is PositionMode.HEDGE
        ):
            return GateResult(GateOutcome.HEDGE_MODE_UNSUPPORTED, HEDGE_WORDS)
        if status.failure is not None or not status.reachable:
            return _unreadable("the connection check did not succeed")
        if status.position_mode is None:
            return _unreadable("the account's position mode was not read")
        return ports

    def _read(
        self, ports: VenueTradingPorts, request: GateRequest
    ) -> FuturesSymbolSetting | GateResult:
        try:
            setting = ports.order_entry_terms.futures_setting_for(request.symbol)
        except (AccountControlRejectedError, AccountControlUnavailableError) as error:
            return _unreadable(f"{request.symbol}'s settings were not read ({error})")
        if isinstance(setting, NotApplicable):
            return _unreadable(f"{request.venue.display_name} has no leverage to read")
        return setting

    def _write(
        self,
        ports: VenueTradingPorts,
        request: GateRequest,
        before: FuturesSymbolSetting,
    ) -> GateResult | None:
        """Margin type, then leverage, each only if it differs. A refusal after the margin
        type changed says so: the exchange then holds a setting the user did not see."""
        wanted = _MARGIN_TYPES[request.margin_mode]
        control = ports.futures_settings
        margin_changed = False
        try:
            if before.margin_type is not wanted:
                changed = control.change_margin_type(
                    request.symbol, wanted, owner_id=request.owner_id
                )
                refusal = _refusal(changed.blocked_by, changed.detail, "margin type")
                if refusal is not None:
                    return refusal
                margin_changed = True
                _log_change(
                    request, "margin type", before.margin_type.value, wanted.value
                )
            if before.leverage != request.leverage:
                leveraged = control.change_leverage(
                    request.symbol, request.leverage, owner_id=request.owner_id
                )
                refusal = _refusal(leveraged.blocked_by, leveraged.detail, "leverage")
                if refusal is not None:
                    return _after_margin_change(
                        refusal, margin_changed, before, request
                    )
                _log_change(
                    request, "leverage", str(before.leverage), str(request.leverage)
                )
        except (AccountControlRejectedError, AccountControlUnavailableError) as error:
            refused = GateResult(GateOutcome.EXCHANGE_REFUSED, f"the exchange: {error}")
            return _after_margin_change(refused, margin_changed, before, request)
        return None


def _after_margin_change(
    refusal: GateResult,
    margin_changed: bool,
    before: FuturesSymbolSetting,
    request: GateRequest,
) -> GateResult:
    """`refusal`, with what the exchange already holds when the margin type was changed first."""
    if not margin_changed:
        return refusal
    wanted = _MARGIN_TYPES[request.margin_mode]
    now = "; ".join(_differences(replace(before, margin_type=wanted), request))
    return GateResult(
        refusal.outcome,
        f"{refusal.detail}; the margin type was already changed to {wanted.value} "
        f"and stays so ({now})",
    )


def _differences(setting: FuturesSymbolSetting, request: GateRequest) -> list[str]:
    found: list[str] = []
    wanted = _MARGIN_TYPES[request.margin_mode]
    if setting.margin_type is not wanted:
        found.append(
            f"margin type {wanted.value} asked, exchange says {setting.margin_type.value}"
        )
    if setting.leverage != request.leverage:
        found.append(
            f"leverage {request.leverage} asked, exchange says {setting.leverage}"
        )
    return found


def _busy_symbol(ports: VenueTradingPorts, request: GateRequest) -> GateResult | None:
    """Why a change cannot be asked yet, or `None` when the symbol is known to be flat."""
    symbol = request.symbol
    try:
        orders = [o for o in ports.account_activity.open_orders() if o.symbol == symbol]
        held = [
            p for p in ports.account_snapshot.open_positions() if p.symbol == symbol
        ]
    except Exception as exc:  # noqa: BLE001 - converted at the seam: a symbol whose orders or position could not be read is not known to be flat, so the answer is a named refusal, never a raise and never "flat"
        return _unreadable(f"{symbol}'s open orders and position were not read ({exc})")
    if not orders and not held:
        return None
    what = []
    if orders:
        what.append(f"{len(orders)} open order(s)")
    if held:
        what.append(f"a position of {held[0].position_amt}")
    return GateResult(
        GateOutcome.SYMBOL_NOT_FLAT,
        f"{symbol} has {' and '.join(what)}, and Binance refuses a margin type or leverage "
        "change then; cancel the orders and close the position, or set the leverage and "
        "margin type in the exchange yourself. Nothing was changed",
    )


def _refusal(
    blocked: ExecuteOrderSafetyGate | AccountControlRefusal | None,
    detail: str | None,
    what: str,
) -> GateResult | None:
    if blocked is None:
        return None
    if isinstance(blocked, ExecuteOrderSafetyGate):
        return GateResult(
            GateOutcome.CHANGE_NOT_PERMITTED,
            f"the {what} change was not sent: {blocked.value}; "
            "open the venue's order session first",
        )
    if blocked is AccountControlRefusal.POSITION_OPEN:
        return GateResult(
            GateOutcome.SYMBOL_NOT_FLAT,
            f"the {what} change was not made: {detail or 'the symbol has a position'}",
        )
    return GateResult(
        GateOutcome.EXCHANGE_REFUSED,
        f"the {what} change was refused: {detail or blocked.value}",
    )


def _unreadable(why: str) -> GateResult:
    return GateResult(GateOutcome.SETTINGS_UNREADABLE, why)


def _log_change(request: GateRequest, what: str, old: str, new: str) -> None:
    logger.info(
        "%s %s: %s changed from %s to %s [futures-gate]",
        request.venue.display_name,
        request.symbol,
        what,
        old,
        new,
    )
