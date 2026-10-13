"""`EPIC-039E` - the Futures settings gate over the composed app and the fake Futures exchange.

@details Nothing is a hand-written port: `create_app()` builds the gate (`IVenueSettingsGate`,
chosen by the venue's profile) and the facts reader (`IVenueFacts`), the HTTP goes to the fake
server, and the fake refuses what Binance's error-code page says it refuses (`-4047`,
`-4048`). The promises: a first order goes out only on a symbol whose margin type and
leverage are the bot's; the gate says why, in words, when the symbol is busy; and it never
sends a position-mode change. Hedge Mode is switched on by the test through the fake's own
setting, the way the owner would in the Binance app.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_facts import (
    IVenueFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_settings_gate import (
    IVenueSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.margin_mode import MarginMode
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_settings_gate_result import (
    GateOutcome,
    GateRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot, BotDefinition
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)

from .futures_fake_exchange import FUTURES, SYMBOL, BootedFutures, booted_futures
from .grid_fake_exchange import FakeExchange


def _gate(app: BootedFutures) -> IVenueSettingsGate:
    return app.engine.context.container.resolve(IVenueSettingsGate)


def _open_the_order_session(app: BootedFutures) -> None:
    """What Start does first, and a margin or leverage change needs (signed activity)."""
    ports = app.engine.context.container.resolve(IVenueTradingPorts).get(FUTURES)
    assert ports.trading_session.ensure_ready().ready


def _ask(app: BootedFutures, leverage: int) -> GateOutcome:
    request = GateRequest(FUTURES, SYMBOL, leverage, MarginMode.ISOLATED)
    return _gate(app).ensure(request).outcome


def _setting(app: BootedFutures) -> tuple[int, MarginType]:
    """What the exchange says the symbol holds, read the way the app reads it."""
    ports = app.engine.context.container.resolve(IVenueTradingPorts).get(FUTURES)
    setting = ports.order_entry_terms.futures_setting_for(SYMBOL)
    assert isinstance(setting, FuturesSymbolSetting)
    return setting.leverage, setting.margin_type


def test_the_gate_makes_a_flat_symbol_match_and_never_changes_the_position_mode(
    futures: FakeExchange,
) -> None:
    with booted_futures(futures) as app:
        _open_the_order_session(app)
        assert _ask(app, 7) is GateOutcome.ENSURED

        assert _setting(app) == (7, MarginType.ISOLATED)
        posted = [path for method, path in app.urls.requests if method == "POST"]
        assert "/fapi/v1/marginType" in posted or "/fapi/v1/leverage" in posted
        assert "/fapi/v1/positionSide/dual" not in posted


def test_a_resting_order_stops_the_change_in_words_and_changes_nothing(
    futures: FakeExchange,
) -> None:
    with booted_futures(futures) as app:
        _open_the_order_session(app)
        before = _setting(app)
        app.client().place_order(
            Order(
                client_order_id=ClientOrderId("SEW-gate-aaaaaaaaaa"),
                symbol=SYMBOL,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("0.010"),
                price=Decimal("50000.0"),
                time_in_force=TimeInForce.GTC,
            )
        )

        assert _ask(app, before[0] + 1) is GateOutcome.SYMBOL_NOT_FLAT
        assert _setting(app) == before
        assert not [p for m, p in app.urls.requests if m == "POST" and "leverage" in p]


def test_hedge_mode_on_the_account_blocks_the_gate(futures: FakeExchange) -> None:
    with booted_futures(futures) as app:
        app.urls.futures_book.set_position_mode({"dualSidePosition": "true"})

        assert _ask(app, 3) is GateOutcome.HEDGE_MODE_UNSUPPORTED


def test_a_closed_order_session_is_a_named_refusal_not_a_change(
    futures: FakeExchange,
) -> None:
    with booted_futures(futures) as app:
        gate = app.engine.context.container.resolve(IVenueSettingsGate)
        before = _setting(app)

        result = gate.ensure(
            GateRequest(FUTURES, SYMBOL, before[0] + 1, MarginMode.ISOLATED)
        )

        assert result.outcome is GateOutcome.CHANGE_NOT_PERMITTED
        assert _setting(app) == before


def test_the_composed_app_reads_a_futures_bots_facts_by_its_profile(
    futures: FakeExchange,
) -> None:
    with booted_futures(futures) as app:
        facts = app.engine.context.container.resolve(IVenueFacts)
        bot = Bot.draft(
            BotId("a3f9c1"),
            BotDefinition("grid one", "grid", FUTURES, SYMBOL, {}),
            datetime(2026, 10, 13, tzinfo=UTC),
        )

        snapshot = facts.read(bot)

        assert isinstance(snapshot, FuturesLoaded), snapshot
        assert snapshot.facts.position == 0
        assert snapshot.facts.position_mode is PositionMode.ONE_WAY
        assert snapshot.facts.available_margin > 0
        assert snapshot.facts.brackets.symbol == SYMBOL
