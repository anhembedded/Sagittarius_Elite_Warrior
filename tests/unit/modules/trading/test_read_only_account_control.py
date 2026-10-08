"""`EPIC-035H` review — a read-only copy changes no leverage and no margin mode.

Leverage and margin mode are account settings the first copy's ladder trades
under, and `FuturesAccountControl` talks to the exchange through the session
factory, not through a trading client, so the client-factory wrapper does not
reach it. The control has a wrapper of its own; reads pass.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.errors import ReadOnlyInstanceError
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.read_only_account_control import (
    ReadOnlyAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_assembly import (
    SharedVenueInputs,
    VenueAssembly,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_account_control import (
    IFuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore

_REASON = "Another copy is running; this one is read-only."


def _inner() -> Mock:
    return Mock(spec=IFuturesAccountControl)


def test_a_read_only_copy_changes_no_leverage() -> None:
    inner = _inner()

    with pytest.raises(ReadOnlyInstanceError, match="read-only"):
        ReadOnlyAccountControl(inner, _REASON).change_leverage("BTCUSDT", 5)

    inner.change_leverage.assert_not_called()


def test_a_read_only_copy_changes_no_margin_mode() -> None:
    inner = _inner()

    with pytest.raises(ReadOnlyInstanceError):
        ReadOnlyAccountControl(inner, _REASON).change_margin_type(
            "BTCUSDT", MarginType.ISOLATED
        )

    inner.change_margin_type.assert_not_called()


def test_the_reads_go_through() -> None:
    inner = _inner()
    inner.open_position.return_value = Decimal(2)
    control = ReadOnlyAccountControl(inner, _REASON)

    assert control.open_position("BTCUSDT") == Decimal(2)
    control.symbol_setting("BTCUSDT")
    control.leverage_brackets("BTCUSDT")
    inner.symbol_setting.assert_called_once_with("BTCUSDT")
    inner.leverage_brackets.assert_called_once_with("BTCUSDT")


def _assembly(instance: InstanceAccess, venue: TradingVenue) -> VenueAssembly:
    return VenueAssembly(
        venue,
        SharedVenueInputs(
            container=Mock(),
            secrets_file_path="unused",
            session_states=VenueSessionStates(),
            secret_store=InMemorySecretStore(),
            instance=instance,
        ),
    )


def test_a_second_copys_futures_venue_gets_the_read_only_control(
    tmp_path: Path,
) -> None:
    first = InstanceAccess.acquire(tmp_path / "instance.lock")
    second = InstanceAccess.acquire(tmp_path / "instance.lock")

    control = _assembly(second, TradingVenue.FUTURES_TESTNET).account_control
    writable = _assembly(
        InstanceAccess.unguarded(), TradingVenue.FUTURES_TESTNET
    ).account_control

    assert isinstance(control, ReadOnlyAccountControl)
    assert not isinstance(writable, ReadOnlyAccountControl)
    first.release()
