"""`BUG-176` — the Trading page of Tools → Options: one row per venue, one way in.

@details What the user sees and is told, over the real use cases (`key_page_world`):
the rows, what a refused key says, what Replace and Remove touch, and that the full
key and the secret are on no widget after entry.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
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
    VENUES,
    KeyPage,
    build_page,
    mainnet_accepts,
    status_of,
    unknown_everywhere,
)

_FUTURES_TESTNET = TradingVenue.FUTURES_TESTNET
_SPOT_TESTNET = TradingVenue.SPOT_TESTNET
_FUTURES_MAINNET = TradingVenue.FUTURES_MAINNET
_SPOT_MAINNET = TradingVenue.SPOT_MAINNET


@pytest.fixture
def page(qapp, tmp_path, request) -> KeyPage:
    return build_page(tmp_path, request)


def test_the_page_lists_one_row_per_venue_with_no_key_yet(page) -> None:
    rows = page.presenter._settings_view_model.rows

    assert [r.venue for r in rows] == list(VENUES)
    assert [r.title for r in rows] == [v.display_name for v in VENUES]
    assert all(not r.has_key and r.key == "—" for r in rows)
    assert all("No key" in r.state for r in rows)


def test_a_row_shows_the_first_and_last_four_characters_of_its_key_and_where_it_lives(
    page,
) -> None:
    page.providers[_FUTURES_TESTNET].save_to_file(OLD_TESTNET_KEY, "s")
    page.presenter.revert()

    row = page.row(_FUTURES_TESTNET)

    assert row.key == "T3st…K3y! (secrets.local.json)"
    assert row.has_key
    assert page.row(_SPOT_TESTNET).has_key is False


def test_the_full_key_and_the_secret_are_on_no_widget_after_entry(page) -> None:
    page.probe.verdicts = mainnet_accepts(spot=True, futures=True)
    page.type_in_dialog()

    page.click_add()

    shown = page.everything_on_screen()
    assert KEY not in shown
    assert SECRET not in shown
    assert "A1b2…Z9y8" in shown


def test_adding_a_key_names_the_venues_it_was_kept_for_and_checks_them(page) -> None:
    page.probe.verdicts = mainnet_accepts(spot=True)
    page.type_in_dialog()

    page.click_add()

    assert page.status_text == "Key kept for Spot Mainnet. Connected."
    assert page.statuses.asked == [_SPOT_MAINNET]
    assert page.row(_SPOT_MAINNET).state == "Connected"
    assert page.row(_FUTURES_MAINNET).has_key is False
    assert page.notifier.failures == []


def test_a_key_that_works_nowhere_says_why_for_each_environment(page) -> None:
    page.type_in_dialog()

    page.click_add()

    notice = page.notifier.last
    assert notice.kind is FailureKind.COMMAND
    for environment in KeyEnvironment:
        assert environment.label in notice.headline
    assert "A testnet key does not work on mainnet" in notice.headline
    assert KEY not in notice.headline + notice.detail
    assert all(not r.has_key for r in page.presenter._settings_view_model.rows)


def test_a_refusal_by_a_known_key_points_at_the_ip_allowlist(page) -> None:
    page.probe.verdicts = unknown_everywhere()
    page.probe.verdicts[KeyEnvironment.MAINNET] = EnvironmentVerdict(
        KeyEnvironment.MAINNET, KeyStanding.REFUSED
    )
    page.type_in_dialog()

    page.click_add()

    headline = page.notifier.last.headline
    assert "knows this key but refused" in headline
    assert "public IP" in headline
    assert "192.168" in headline


def test_an_unreachable_environment_is_not_called_an_unknown_key(page) -> None:
    page.probe.verdicts[KeyEnvironment.MAINNET] = EnvironmentVerdict(
        KeyEnvironment.MAINNET,
        KeyStanding.UNREACHABLE,
        failure=ConnectionFailureKind.MAINTENANCE,
    )
    page.type_in_dialog()

    page.click_add()

    mainnet_line = next(
        line
        for line in page.notifier.last.headline.splitlines()
        if line.startswith("Binance mainnet")
    )
    assert "unavailable" in mainnet_line
    assert "does not know" not in mainnet_line


def test_a_key_that_can_withdraw_is_refused_with_a_sentence_saying_so(page) -> None:
    page.probe.verdicts = mainnet_accepts(spot=True, withdraw=True)
    page.type_in_dialog()

    page.click_add()

    assert "can withdraw funds" in page.notifier.last.headline
    assert page.keyring.secrets == {}


def test_cancelling_the_dialog_changes_nothing_and_asks_nobody(page) -> None:
    page.cancel_dialog()

    page.click_add()

    assert page.probe.asked == []
    assert page.notifier.failures == []
    assert page.status_text == ""


def test_replace_asks_for_that_venues_key_and_touches_no_other(page) -> None:
    page.providers[_FUTURES_MAINNET].save_to_file("f" * 20, "s")
    page.providers[_SPOT_MAINNET].save_to_file("s" * 20, "s")
    page.presenter.revert()
    page.probe.verdicts = mainnet_accepts(spot=True, futures=True)
    page.type_in_dialog()

    page.click_replace(_SPOT_MAINNET)

    assert "Spot Mainnet" in page.hints[-1]
    assert page.key_of(_SPOT_MAINNET) == KEY
    assert page.key_of(_FUTURES_MAINNET) == "f" * 20


def test_replace_with_a_key_of_another_venue_is_refused_and_names_both(page) -> None:
    page.probe.verdicts = mainnet_accepts(spot=True)
    page.type_in_dialog()

    page.click_replace(_FUTURES_TESTNET)

    headline = page.notifier.last.headline
    assert "belongs to Spot Mainnet" in headline
    assert "not Futures Testnet" in headline
    assert page.key_of(_FUTURES_TESTNET) is None


def test_remove_forgets_that_venues_key_only(page) -> None:
    page.providers[_FUTURES_TESTNET].save_to_file(OLD_TESTNET_KEY, "s")
    page.providers[_SPOT_TESTNET].save_to_file("p" * 20, "s")
    page.presenter.revert()

    page.click_remove(_FUTURES_TESTNET)

    assert page.key_of(_FUTURES_TESTNET) is None
    assert page.key_of(_SPOT_TESTNET) == "p" * 20
    assert page.row(_FUTURES_TESTNET).has_key is False
    assert page.status_text == "Key removed."


def test_a_key_from_an_environment_variable_cannot_be_replaced_or_removed_here(
    page, monkeypatch
) -> None:
    monkeypatch.setenv("BINANCE_FUTURES_TESTNET_API_KEY", "E" * 20)
    monkeypatch.setenv("BINANCE_FUTURES_TESTNET_API_SECRET", "s")
    page.presenter.revert()

    row = page.row(_FUTURES_TESTNET)
    assert row.has_key
    assert not row.editable
    assert "environment variable" in row.key
    page.click_remove(_FUTURES_TESTNET)
    assert "environment variable" in page.notifier.last.headline


def test_check_connections_words_each_venues_answer(page) -> None:
    page.providers[_FUTURES_TESTNET].save_to_file(OLD_TESTNET_KEY, "s")
    page.providers[_SPOT_TESTNET].save_to_file("p" * 20, "s")
    page.presenter.revert()
    page.statuses.by_venue[_SPOT_TESTNET] = status_of(
        _SPOT_TESTNET, ConnectionFailureKind.KEY_REJECTED
    )

    page.click_check()

    assert page.row(_FUTURES_TESTNET).state == "Connected"
    spot = page.row(_SPOT_TESTNET)
    assert spot.state_is_error
    assert "allowlist" in spot.state
    assert page.row(_SPOT_MAINNET).state.startswith("No key")
    assert "Spot Testnet could not be connected" in page.status_text


def test_the_buttons_are_off_while_an_action_runs_and_a_stale_answer_is_dropped(
    page,
) -> None:
    page.probe.verdicts = mainnet_accepts(spot=True)
    page.type_in_dialog()
    page.threads.held = []

    page.click_add()
    view_model = page.presenter._settings_view_model
    assert view_model.busy
    assert not page.view._add_key_button.isEnabled()
    page.click_add()  # ignored: the dialog is not even opened
    assert page.typed == []

    page.threads.held, release = None, page.threads.held
    for finish in release:
        finish()

    assert not view_model.busy
    assert page.view._add_key_button.isEnabled()


def test_the_page_is_never_dirty_and_apply_has_nothing_to_do(page) -> None:
    assert page.presenter.is_dirty() is False
    page.presenter.apply()
    assert page.presenter.is_dirty() is False
    assert page.presenter.validation_message() is None


def test_an_unexpected_failure_is_a_sentence_with_the_technical_text_behind_details(
    page,
) -> None:
    class _BoomError(RuntimeError):
        pass

    def explode(*_args, **_kwargs):
        raise _BoomError("socket exploded with SECRET-INSIDE")

    page.probe.probe = explode  # type: ignore[method-assign]
    page.type_in_dialog()

    page.click_add()

    notice = page.notifier.last
    assert notice.headline.startswith("Adding the key failed unexpectedly")
    assert "exploded" not in notice.headline
    assert "exploded" in notice.detail
    assert not page.presenter._settings_view_model.busy
