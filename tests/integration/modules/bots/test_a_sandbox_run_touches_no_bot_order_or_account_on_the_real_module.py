"""`EPIC-040C` — a sandbox copied, edited, judged, run and reset on the real module's graph sends no
command, opens no order session, reads no account and writes no bot.

@details The kind catalog is the one `BotsModule.register` builds, so the backtester is the real
`GridKindBacktester` over the real query handler; the market data is the module's own fake. The
command dispatcher, the account reads, the venue's trading ports and the bot store are the
registered singletons, each watched for any call. The proof that the *guard* holds by construction is
`test_sandbox_sends_no_command.py`; this proves it on the path that runs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    KindBacktestRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.sandbox_plan import (
    SandboxPlan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest.sandbox_judge import (
    judge_sandbox,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_accounts import (
    IVenueAccounts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.backtest.sandbox_fixtures import (
    SAVED,
    bot,
    market,
)

from .bots_module_world import registered

_VENUE = TradingVenue.SPOT_TESTNET
_T0 = datetime(2026, 9, 1, tzinfo=UTC)
_CANDLES = 24


def _candles() -> list[MarketData]:
    out = []
    for n in range(_CANDLES):
        at = _T0 + timedelta(minutes=15 * n)
        close = 65000.0 + (300 if n % 2 else -300)
        out.append(
            MarketData(
                symbol="BTCUSDT",
                interval=TimeFrame.FIFTEEN_MINUTES.value,
                open_time=at,
                open_price=65000.0,
                high_price=max(65000.0, close) + 5,
                low_price=min(65000.0, close) - 5,
                close_price=close,
                volume=1.0,
                close_time=at + timedelta(minutes=15),
                quote_asset_volume=1.0,
                number_of_trades=1,
                taker_buy_base_asset_volume=0.5,
                taker_buy_quote_asset_volume=0.5,
            )
        )
    return out


def _watch(monkeypatch: pytest.MonkeyPatch, target: object, *names: str) -> list[str]:
    """Replaces `names` on `target` with a recorder that raises: any call fails the test."""
    calls: list[str] = []

    def recorder(name: str) -> Any:
        def call(*_args: object, **_kwargs: object) -> None:
            calls.append(name)
            raise AssertionError(f"the sandbox called {type(target).__name__}.{name}")

        return call

    for name in names:
        monkeypatch.setattr(target, name, recorder(name))
    return calls


def test_a_sandbox_run_touches_no_bot_order_or_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _module, context = registered(tmp_path / "bots")
    container = context.container
    sources = container.resolve(IMarketDataSources)
    ports = sources.ports_for(_VENUE.market_data_venue)
    ports.history.seed(_candles(), MarketType.SPOT)
    ports.repository.save_klines(MarketType.SPOT, _candles())
    store = container.resolve(IBotStore)
    stored_before = store.load_all()
    calls = {
        "dispatcher": _watch(
            monkeypatch, container.resolve(ICommandDispatcher), "dispatch"
        ),
        "accounts": _watch(
            monkeypatch, container.resolve(IVenueAccounts), "reader", "sources"
        ),
        "trading ports": _watch(
            monkeypatch,
            container.resolve(IVenueTradingPorts),
            "get",
            "primary",
            "enabled",
        ),
        "store": _watch(monkeypatch, store, "save", "delete"),
    }
    kind = container.resolve(IBotKindCatalog).kind(GRID_KIND_ID)
    backtester = kind.backtester()
    assert backtester is not None

    plan = SandboxPlan.from_bot(bot())
    plan = plan.with_config({**SAVED, "upper": "66000"})
    judged = judge_sandbox(kind, plan, market())
    answer = backtester.run(
        KindBacktestRequest(
            plan.symbol,
            plan.config,
            market().terms,  # type: ignore[arg-type]
            TimeFrame.FIFTEEN_MINUTES,
            _T0,
            _T0 + timedelta(minutes=15 * _CANDLES),
            plan.venue,
        )
    )
    plan = plan.reset()

    assert judged.verdicts
    assert isinstance(answer, BacktestOutcome) and len(answer.bars) == _CANDLES
    assert not plan.edited
    assert calls == {"dispatcher": [], "accounts": [], "trading ports": [], "store": []}
    assert store.load_all() == stored_before


def test_each_watch_catches_a_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A watch that cannot fire would let the test above pass for the wrong reason."""
    _module, context = registered(tmp_path / "bots")
    container = context.container
    watched = {
        "dispatch": (container.resolve(ICommandDispatcher), (object,)),
        "reader": (container.resolve(IVenueAccounts), (object(),)),
        "get": (container.resolve(IVenueTradingPorts), (_VENUE,)),
        "save": (container.resolve(IBotStore), (object(),)),
    }

    for name, (target, args) in watched.items():
        calls = _watch(monkeypatch, target, name)

        with pytest.raises(AssertionError, match="the sandbox called"):
            getattr(target, name)(*args)

        assert calls == [name]
