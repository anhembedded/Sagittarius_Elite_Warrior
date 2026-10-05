"""`MarketPresenter`'s Tools → Check connection (`EPIC-033H`, SPEC-003): the
answer as a word in the status bar, a failure where the user looks, and only
the newest check writes."""

from __future__ import annotations

import dataclasses

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
    CHECK_CONNECTION,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.ui.market.market_fixtures import (
    RaisingAccount,
)

_CONNECTED = ExchangeConnectionStatus(
    venue=TradingVenue.FUTURES_TESTNET,
    reachable=True,
    failure=None,
    server_time_skew_ms=12,
    usdt_balance=None,
    position_mode=None,
    margin_type=None,
    open_position_count=0,
)
_NO_KEY = dataclasses.replace(
    _CONNECTED, reachable=False, failure=ConnectionFailureKind.NOT_CONFIGURED
)


class _Binder(ICommandBinder):
    """Holds what the presenter binds, as the Engine's registry would."""

    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}
        self.enabled: dict[str, object] = {}

    def bind(
        self,
        action_id,
        handler,
        *,
        enabled=None,
        checked=None,
        initially_enabled=True,
    ) -> None:
        self.handlers[action_id] = handler
        self.enabled[action_id] = enabled


class _Seen(QObject):
    """Records a bool signal's values."""

    got = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.values: list[bool] = []


# -- Tools → Check connection (SPEC-003) ---------------------------------------


def test_check_connection_is_bound_and_off_while_it_runs(build, threads):
    presenter = build()
    binder = _Binder()
    presenter.bind_commands(binder)
    seen = _Seen()
    presenter.checkConnectionEnabled.connect(seen.values.append)

    binder.handlers[CHECK_CONNECTION](False)
    assert presenter.view.connection.text() == "Exchange: checking…"
    threads.run_all()

    assert binder.enabled[CHECK_CONNECTION] is presenter.checkConnectionEnabled
    assert seen.values == [False, True]


def test_a_connected_check_reads_connected_in_the_status_bar(build, threads):
    presenter = build()

    presenter.check_connection()
    threads.run_all()

    assert presenter.view.connection.text() == "Exchange: connected (FUTURES_TESTNET)"
    assert presenter.view.connection in presenter.view.status_widgets()


def test_a_failed_check_names_the_fix_where_the_user_looks(build, threads, monkeypatch):
    presenter = build(account=FakeAccountSnapshot(status=_NO_KEY))
    shown: list[str] = []
    monkeypatch.setattr(presenter.view, "show_connection_failure", shown.append)

    presenter.check_connection()
    threads.run_all()

    assert presenter.view.connection.text() == "Exchange: not connected"
    assert shown == [
        "FUTURES_TESTNET: no API key. Save one in Tools → Options → Trading."
    ]


def test_a_check_that_raises_is_reported_not_lost(build, threads, monkeypatch):
    presenter = build(account=RaisingAccount())
    shown: list[str] = []
    monkeypatch.setattr(presenter.view, "show_connection_failure", shown.append)

    presenter.check_connection()
    threads.run_all()

    assert presenter.view.connection.text() == "Exchange: not connected"
    assert shown == ["The connection check failed: proxy refused the tunnel"]


def test_a_superseded_checks_answer_is_ignored(build, threads, monkeypatch):
    """`async-ui-action-rule.md` §1: only the newest check may write."""
    account = FakeAccountSnapshot(status=_CONNECTED)
    presenter = build(account=account)
    shown: list[str] = []
    monkeypatch.setattr(presenter.view, "show_connection_failure", shown.append)
    presenter.check_connection()
    presenter.check_connection()

    threads.run_last()  # the second check answers: connected
    account.answer_with(_NO_KEY)
    threads.run_all()  # the first answers late: no key

    assert presenter.view.connection.text() == "Exchange: connected (FUTURES_TESTNET)"
    assert shown == []
