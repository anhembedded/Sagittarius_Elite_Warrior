"""`BUG-176` — the Options Trading page over the real use cases, with no exchange.

@details The page, `EnrolKeyCommandHandler`, `RemoveKeyCommandHandler` and
`ListVenueKeysQueryHandler` are the real ones; each venue's credentials provider is
the real one too (a temp `secrets.local.json` for the testnets, an in-memory store
standing in for the keyring for the mainnets). Only the exchange is scripted: a
`ScriptedKeyProbe` answers what each environment says of a key, and connection
checks answer what a test sets. The thread manager runs each task as it is submitted.
"""

from __future__ import annotations

import concurrent.futures
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from binance.exceptions import BinanceAPIException
from PySide6.QtWidgets import QLabel, QLineEdit
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    describe_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.credentials.enrol_key import (
    EnrolKeyCommand,
    EnrolKeyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.credentials.remove_key import (
    RemoveKeyCommand,
    RemoveKeyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_exchange_connection_status import (
    GetExchangeConnectionStatusQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.list_venue_keys import (
    ListVenueKeysQuery,
    ListVenueKeysQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_environment_probe import (
    IKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
    KeyEnvironment,
    KeyStanding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_permissions import (
    KeyPermissions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.trading_settings_presenter import (
    TradingSettingsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.trading_settings_view import (
    TradingSettingsView,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    EnvFirstCredentialsProvider,
    MainnetCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

KEY = "A1b2" + "x" * 56 + "Z9y8"
SECRET = "the-secret-that-must-never-be-shown"  # noqa: S105 - a test value
OLD_TESTNET_KEY = "T3st" + "n" * 56 + "K3y!"
VENUES = (
    TradingVenue.FUTURES_TESTNET,
    TradingVenue.SPOT_TESTNET,
    TradingVenue.FUTURES_MAINNET,
    TradingVenue.SPOT_MAINNET,
)


def reason_of(code: int, message: str) -> str:
    """The wording the probe gives an exchange's refusal: `describe_failure`'s."""
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code, exc.message, exc.status_code, exc.response, exc.request = (
        code,
        message,
        401,
        None,
        None,
    )
    return describe_failure(exc)


UNKNOWN_REASON = reason_of(-2008, "Invalid Api-Key ID.")
REFUSED_REASON = reason_of(-2015, "Invalid API-key, IP, or permissions for action.")


def unknown_everywhere() -> dict[KeyEnvironment, EnvironmentVerdict]:
    return {
        e: EnvironmentVerdict(e, KeyStanding.UNKNOWN, reason=UNKNOWN_REASON)
        for e in KeyEnvironment
    }


def mainnet_accepts(
    *, spot: bool = False, futures: bool = False, withdraw: bool = False
) -> dict[KeyEnvironment, EnvironmentVerdict]:
    verdicts = unknown_everywhere()
    verdicts[KeyEnvironment.MAINNET] = EnvironmentVerdict(
        KeyEnvironment.MAINNET,
        KeyStanding.ACCEPTED,
        permissions=KeyPermissions(
            can_read=True,
            can_trade_spot=spot,
            can_withdraw=withdraw,
            can_trade_futures=futures,
        ),
    )
    return verdicts


class ScriptedKeyProbe(IKeyEnvironmentProbe):
    """Answers what a test scripted for each environment, whatever the key."""

    def __init__(self) -> None:
        self.verdicts = unknown_everywhere()
        self.asked: list[KeyEnvironment] = []

    def probe(
        self, environment: KeyEnvironment, credentials: ExchangeCredentials
    ) -> EnvironmentVerdict:
        self.asked.append(environment)
        return self.verdicts[environment]


class InlineThreads(IThreadManager):
    """Runs each task as it is submitted, or holds it for the test to release."""

    def __init__(self) -> None:
        self.held: list[Callable[[], None]] | None = None

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        if self.held is not None:
            self.held.append(lambda: future.set_result(task(*args, **kwargs)))
        else:
            future.set_result(task(*args, **kwargs))
        return future

    def shutdown(self, wait: bool = True) -> None:
        return None


class _Dispatcher(ICommandDispatcher):
    def __init__(self, handlers: dict[type, Any]) -> None:
        self._handlers = handlers

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        return self._handlers[handler_class].execute(input_dto)


class _ConnectionStatuses:
    """`GetExchangeConnectionStatusQuery`'s answer per venue, as a test sets it."""

    def __init__(self) -> None:
        self.by_venue: dict[TradingVenue, ExchangeConnectionStatus] = {}
        self.asked: list[TradingVenue] = []

    def execute(
        self, query: GetExchangeConnectionStatusQuery
    ) -> ExchangeConnectionStatus:
        self.asked.append(query.venue)
        return self.by_venue.get(query.venue) or status_of(query.venue)


def status_of(
    venue: TradingVenue, failure: ConnectionFailureKind | None = None
) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=venue,
        reachable=failure is None,
        failure=failure,
        server_time_skew_ms=None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    )


@dataclass
class KeyPage:
    presenter: TradingSettingsPresenter
    view: TradingSettingsView
    probe: ScriptedKeyProbe
    notifier: RecordingNotifier
    threads: InlineThreads
    keyring: InMemorySecretStore
    secrets_file: Path
    providers: dict[TradingVenue, IExchangeCredentialsProvider]
    statuses: _ConnectionStatuses
    typed: list[tuple[str, str] | None] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)

    def type_in_dialog(self, key: str = KEY, secret: str = SECRET) -> None:
        """What the next dialog hands back; `None` is Cancel."""
        self.typed.append((key, secret))

    def cancel_dialog(self) -> None:
        self.typed.append(None)

    def key_of(self, venue: TradingVenue) -> str | None:
        credentials = self.providers[venue].resolve().credentials
        return credentials.api_key if credentials else None

    def row(self, venue: TradingVenue):
        return next(
            r for r in self.presenter._settings_view_model.rows if r.venue is venue
        )

    def click_add(self) -> None:
        self.presenter._settings_view_model.addKeyRequested.emit()

    def click_replace(self, venue: TradingVenue) -> None:
        self.presenter._settings_view_model.replaceKeyRequested.emit(venue)

    def click_remove(self, venue: TradingVenue) -> None:
        self.presenter._settings_view_model.removeKeyRequested.emit(venue)

    def click_check(self) -> None:
        self.presenter._settings_view_model.checkConnectionsRequested.emit()

    @property
    def status_text(self) -> str:
        return self.presenter._settings_view_model.statusMessage

    def everything_on_screen(self) -> str:
        """Every text the page shows or holds in an editable field."""
        texts = [label.text() for label in self.view.findChildren(QLabel)]
        texts += [field.text() for field in self.view.findChildren(QLineEdit)]
        return "\n".join(texts)


def build_page(tmp_path: Path, request: Any) -> KeyPage:
    for name in list(os.environ):
        if name.startswith("BINANCE_"):
            del os.environ[name]
    secrets_file = tmp_path / "secrets.local.json"
    file_source = SecretsFileSource(str(secrets_file))
    keyring = InMemorySecretStore()
    providers: dict[TradingVenue, IExchangeCredentialsProvider] = {
        TradingVenue.FUTURES_TESTNET: EnvFirstCredentialsProvider(
            file_source, TradingVenue.FUTURES_TESTNET
        ),
        TradingVenue.SPOT_TESTNET: EnvFirstCredentialsProvider(
            file_source, TradingVenue.SPOT_TESTNET
        ),
        TradingVenue.FUTURES_MAINNET: MainnetCredentialsProvider(
            keyring, TradingVenue.FUTURES_MAINNET
        ),
        TradingVenue.SPOT_MAINNET: MainnetCredentialsProvider(
            keyring, TradingVenue.SPOT_MAINNET
        ),
    }
    contexts = FakeVenueContexts(
        *(fake_venue_context(v, credentials_provider=providers[v]) for v in VENUES)
    )
    probe = ScriptedKeyProbe()
    statuses = _ConnectionStatuses()
    dispatcher = _Dispatcher(
        {
            EnrolKeyCommand: EnrolKeyCommandHandler(probe, contexts),
            RemoveKeyCommand: RemoveKeyCommandHandler(contexts),
            ListVenueKeysQuery: ListVenueKeysQueryHandler(contexts),
            GetExchangeConnectionStatusQuery: statuses,
        }
    )
    notifier = RecordingNotifier()
    threads = InlineThreads()
    services = {
        INotifier: notifier,
        ICommandDispatcher: dispatcher,
        IThreadManager: threads,
        IVenueContexts: contexts,
    }
    container = Mock()
    container.resolve.side_effect = lambda interface: services.get(interface, Mock())

    view = TradingSettingsView()
    request.addfinalizer(view.deleteLater)
    page = KeyPage(
        presenter=TradingSettingsPresenter(view, container),
        view=view,
        probe=probe,
        notifier=notifier,
        threads=threads,
        keyring=keyring,
        secrets_file=secrets_file,
        providers=providers,
        statuses=statuses,
    )

    def ask_for_key(hint: str) -> tuple[str, str] | None:
        page.hints.append(hint)
        return page.typed.pop(0)

    view.ask_for_key = ask_for_key  # type: ignore[method-assign]
    return page
