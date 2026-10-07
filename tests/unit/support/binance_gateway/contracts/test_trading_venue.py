import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_TESTNETS = (TradingVenue.FUTURES_TESTNET, TradingVenue.SPOT_TESTNET)
_MAINNETS = (TradingVenue.FUTURES_MAINNET, TradingVenue.SPOT_MAINNET)
_FUTURES = (TradingVenue.FUTURES_TESTNET, TradingVenue.FUTURES_MAINNET)
_SPOT = (TradingVenue.SPOT_TESTNET, TradingVenue.SPOT_MAINNET)
_ORDERABLE = (*_TESTNETS, *_MAINNETS)


def test_trading_venue_enum_values():
    assert TradingVenue.DISABLED == "disabled"
    assert TradingVenue.FUTURES_TESTNET == "futures_testnet"
    assert TradingVenue.SPOT_TESTNET == "spot_testnet"
    assert TradingVenue.FUTURES_MAINNET == "futures_mainnet"
    assert TradingVenue.SPOT_MAINNET == "spot_mainnet"


def test_the_testnets_come_before_the_mainnets_so_the_primary_is_never_real_money():
    """`EPIC-034` D11 — the first orderable venue is the primary one."""
    orderable = [v for v in TradingVenue if v.supports_order_submission]

    assert orderable == [*_TESTNETS, *_MAINNETS]
    assert orderable[0].is_testnet


@pytest.mark.parametrize("venue", _FUTURES)
def test_a_futures_venue_trades_usd_m_futures(venue: TradingVenue) -> None:
    assert venue.market_type is MarketType.FUTURES_USD_M


@pytest.mark.parametrize("venue", _SPOT)
def test_a_spot_venue_trades_spot(venue: TradingVenue) -> None:
    assert venue.market_type is MarketType.SPOT


def test_disabled_venue_has_no_market_type():
    """No trading means no market to compare a chart against — `None`,
    not a fabricated default (`code/errors.md` #6)."""
    assert TradingVenue.DISABLED.market_type is None


@pytest.mark.parametrize("venue", _ORDERABLE)
def test_every_venue_but_disabled_supports_order_submission(
    venue: TradingVenue,
) -> None:
    assert venue.supports_order_submission is True


def test_disabled_never_supports_order_submission() -> None:
    assert TradingVenue.DISABLED.supports_order_submission is False


@pytest.mark.parametrize("venue", _MAINNETS)
def test_a_mainnet_venue_moves_real_money_and_is_not_a_testnet(
    venue: TradingVenue,
) -> None:
    assert venue.is_mainnet is True
    assert venue.is_testnet is False


@pytest.mark.parametrize("venue", _TESTNETS)
def test_a_testnet_venue_is_the_python_binance_testnet_flag(
    venue: TradingVenue,
) -> None:
    assert venue.is_testnet is True
    assert venue.is_mainnet is False


def test_disabled_is_neither_a_testnet_nor_a_mainnet() -> None:
    assert (TradingVenue.DISABLED.is_testnet, TradingVenue.DISABLED.is_mainnet) == (
        False,
        False,
    )


def test_every_venue_is_named_for_the_person_by_its_market_and_its_exchange() -> None:
    assert {v: v.display_name for v in TradingVenue} == {
        TradingVenue.DISABLED: "Trading off",
        TradingVenue.FUTURES_TESTNET: "Futures Testnet",
        TradingVenue.SPOT_TESTNET: "Spot Testnet",
        TradingVenue.FUTURES_MAINNET: "Futures Mainnet",
        TradingVenue.SPOT_MAINNET: "Spot Mainnet",
    }


@pytest.mark.parametrize("venue", _FUTURES)
def test_only_a_futures_venue_has_positions(venue: TradingVenue) -> None:
    """`BUG-142` — Spot holds balances, not positions."""
    assert venue.has_positions is True


@pytest.mark.parametrize("venue", [*_SPOT, TradingVenue.DISABLED])
def test_spot_and_disabled_have_no_positions(venue: TradingVenue) -> None:
    assert venue.has_positions is False
