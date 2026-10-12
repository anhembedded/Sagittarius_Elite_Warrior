"""A venue world for the trading pre-flight checks, built from the ports (`testing-rule.md` §2).

The account reader and the credentials provider are the module's own verified
fakes; the key probe is a subclass of the real port that answers what the test
arranged for mainnet. Nothing here talks to a network.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_reads import (
    VenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_environment_probe import (
    IKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
    KeyEnvironment,
    KeyStanding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_permissions import (
    KeyPermissions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_credentials_provider import (
    FakeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: What the fake key looks like; a test greps a rendered report for both.
KEY = "fake-key"
SIGNING_PHRASE = "fake-secret"


def status(
    venue: TradingVenue,
    *,
    skew_ms: int | None = 0,
    failure: ConnectionFailureKind | None = None,
    can_trade: bool | None = True,
) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=venue,
        reachable=failure is None,
        failure=failure,
        server_time_skew_ms=skew_ms,
        usdt_balance=Decimal(100),
        position_mode=PositionMode.ONE_WAY,
        margin_type=None,
        open_position_count=0,
        can_trade=can_trade,
    )


class StoredKey(IExchangeCredentialsProvider):
    """A provider that resolves the fake key from a named source, or is refused."""

    def __init__(
        self, source: CredentialsSource, refusal: str = "", refusal_kind: str = ""
    ) -> None:
        self._source = source
        self._refusal = refusal
        self._kind = refusal_kind

    def resolve(self) -> ResolvedCredentials:
        if self._refusal:
            return ResolvedCredentials(
                None, CredentialsSource.NONE, self._refusal, self._kind
            )
        return ResolvedCredentials(
            ExchangeCredentials(KEY, SIGNING_PHRASE), self._source
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("a pre-flight check never writes a key")

    def remove_stored(self) -> None:
        raise AssertionError("a pre-flight check never removes a key")


class ArrangedProbe(IKeyEnvironmentProbe):
    def __init__(self, verdict: EnvironmentVerdict | None = None) -> None:
        self.verdict = verdict
        self.asked = 0

    def probe(
        self, environment: KeyEnvironment, credentials: ExchangeCredentials
    ) -> EnvironmentVerdict:
        self.asked += 1
        assert environment is KeyEnvironment.MAINNET, (
            "only mainnet has a permission list"
        )
        assert self.verdict is not None, "the test arranged no verdict"
        return self.verdict


def accepted(
    *,
    trade_spot: bool = True,
    trade_futures: bool = True,
    withdraw: bool = False,
    read: bool = True,
) -> EnvironmentVerdict:
    return EnvironmentVerdict(
        KeyEnvironment.MAINNET,
        KeyStanding.ACCEPTED,
        KeyPermissions(read, trade_spot, withdraw, trade_futures),
    )


def venue(
    which: TradingVenue,
    connection: ExchangeConnectionStatus | None = None,
    credentials: IExchangeCredentialsProvider | None = None,
) -> VenueContext:
    return fake_venue_context(
        which,
        account_reader=FakeTradingAccountReader(connection or status(which)),
        credentials_provider=credentials or FakeCredentialsProvider(),
    )


def reads_over(
    *contexts: VenueContext, probe: ArrangedProbe | None = None
) -> VenueReads:
    return VenueReads(FakeVenueContexts(*contexts), probe or ArrangedProbe())
