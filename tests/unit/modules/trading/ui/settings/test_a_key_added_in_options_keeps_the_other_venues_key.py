"""`BUG-176` — a key added in Tools → Options → Trading never overwrites the key of
a venue it is not for.

The owner pasted a mainnet key into the page's one field and it replaced the
working Futures Testnet key. The page now has one way in, Add key…, which finds the
environment the key belongs to and keeps it for that environment's venues only.

(Red on master `6aa3586` as `test_a_key_pasted_in_options_does_not_replace_the_futures_testnet_key`:
`presenter._settings_view_model.apiKey = <mainnet key>; presenter.apply()` left the
Futures Testnet provider resolving the mainnet key. This is the same journey on the
page that replaced it, with a stronger assertion: every venue's key is read back.)
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
    KeyEnvironment,
    KeyStanding,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.ui.settings.key_page_world import (
    KEY,
    OLD_TESTNET_KEY,
    SECRET,
    build_page,
    mainnet_accepts,
)

_FUTURES_TESTNET = TradingVenue.FUTURES_TESTNET
_SPOT_TESTNET = TradingVenue.SPOT_TESTNET
_FUTURES_MAINNET = TradingVenue.FUTURES_MAINNET
_SPOT_MAINNET = TradingVenue.SPOT_MAINNET


@pytest.fixture
def page(qapp, tmp_path, request):
    page = build_page(tmp_path, request)
    page.providers[_FUTURES_TESTNET].save_to_file(OLD_TESTNET_KEY, "testnet-secret")
    page.presenter.revert()
    return page


def test_a_mainnet_key_added_in_options_leaves_the_futures_testnet_key(page) -> None:
    page.probe.verdicts = mainnet_accepts(futures=True)
    page.type_in_dialog()

    page.click_add()

    assert page.key_of(_FUTURES_TESTNET) == OLD_TESTNET_KEY
    assert page.key_of(_SPOT_TESTNET) is None
    assert page.key_of(_FUTURES_MAINNET) == KEY
    assert page.key_of(_SPOT_MAINNET) is None
    assert page.notifier.failures == []


def test_a_mainnet_key_goes_to_the_keyring_and_never_to_the_secrets_file(page) -> None:
    page.probe.verdicts = mainnet_accepts(spot=True, futures=True)
    page.type_in_dialog()

    page.click_add()

    assert set(page.keyring.secrets) == {
        "spot_mainnet_api_key",
        "spot_mainnet_api_secret",
        "futures_mainnet_api_key",
        "futures_mainnet_api_secret",
    }
    assert KEY not in page.secrets_file.read_text()
    assert SECRET not in page.secrets_file.read_text()


def test_a_testnet_key_for_one_venue_is_kept_for_that_venue_alone(page) -> None:
    page.probe.verdicts[KeyEnvironment.SPOT_TESTNET] = EnvironmentVerdict(
        KeyEnvironment.SPOT_TESTNET, KeyStanding.ACCEPTED
    )
    page.type_in_dialog()

    page.click_add()

    assert page.key_of(_SPOT_TESTNET) == KEY
    assert page.key_of(_FUTURES_TESTNET) == OLD_TESTNET_KEY
    assert page.keyring.secrets == {}
