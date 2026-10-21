"""`EPIC-036D3` — the status-bar indicator: whether alerts are getting through, in every mode.

The view offers the widget (`IStatusSource`); the window places it once. It says it in words,
and a failing channel also gets an icon, so colour never carries it alone. It is read in the
background even while the Alerts mode is hidden, with a smaller window of alerts, and clicking it
shows the Alerts mode.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QToolButton
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_history import (
    IAlertHistory,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history import history_words
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import INavigationService
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_source import IStatusSource
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.ui.history.alerts_world import (
    AlertsScreen,
    build_screen,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import an_alert


@pytest.fixture
def screen(qapp, request, tmp_path: Path) -> AlertsScreen:
    return build_screen(request, tmp_path)


def _indicator(screen: AlertsScreen) -> QToolButton:
    (button,) = screen.view.status_widgets()
    assert isinstance(button, QToolButton)
    assert button.objectName() == "btnAlertsIndicator"
    return button


def test_the_view_offers_its_indicator_to_the_window(screen: AlertsScreen) -> None:
    assert isinstance(screen.view, IStatusSource)
    assert list(screen.view.status_widgets()) == [_indicator(screen)]


def test_the_indicator_is_not_shown_until_something_has_been_read(
    screen: AlertsScreen,
) -> None:
    assert _indicator(screen).isHidden()


def test_it_says_ok_when_every_channel_gets_its_alerts(screen: AlertsScreen) -> None:
    screen.refresh()

    button = _indicator(screen)
    assert not button.isHidden()
    assert button.text() == history_words.INDICATOR_OK
    assert button.icon().isNull()


def test_it_says_off_when_no_channel_is_configured(
    qapp, request, tmp_path: Path
) -> None:
    screen = build_screen(request, tmp_path, channel_ids=())

    screen.refresh()

    assert _indicator(screen).text() == history_words.INDICATOR_OFF


def test_it_names_a_failing_channel_in_words_and_with_an_icon(
    screen: AlertsScreen,
) -> None:
    screen.rig.channels["discord"].script.append(DeliveryResult.refused("refused"))
    screen.rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    screen.rig.deliver_all()

    screen.refresh()

    button = _indicator(screen)
    assert button.text() == "Alerts: Discord failing"
    assert not button.icon().isNull()
    assert "Alerts mode" in button.toolTip()


class _Counting(IAlertHistory):
    def __init__(self) -> None:
        self.limits: list[int] = []

    def read(self, limit: int):  # type: ignore[no-untyped-def]
        from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.alert_history_report import (
            AlertHistoryReport,
        )

        self.limits.append(limit)
        return AlertHistoryReport((), ())


def test_a_hidden_mode_is_still_read_for_the_indicator_but_with_a_small_window(
    qapp, request, tmp_path: Path
) -> None:
    from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history.alerts_presenter import (
        HEALTH_LIMIT,
        HISTORY_LIMIT,
    )

    history = _Counting()
    screen = build_screen(request, tmp_path, history=history)

    screen.presenter._poll()
    screen.view.show()
    screen.presenter._poll()

    assert history.limits == [HEALTH_LIMIT, HISTORY_LIMIT]
    assert HEALTH_LIMIT < HISTORY_LIMIT


def test_clicking_the_indicator_shows_the_alerts_mode(
    qapp, request, tmp_path: Path
) -> None:
    asked: list[tuple[str, NavigationSource]] = []

    class _Nav(INavigationService):
        def navigate(self, route: str, *, source: NavigationSource) -> bool:
            asked.append((route, source))
            return True

        @property
        def current_source(self) -> NavigationSource | None:
            return None

    screen = build_screen(request, tmp_path, services={INavigationService: _Nav()})
    screen.refresh()

    _indicator(screen).click()

    assert asked == [("alerts", NavigationSource.USER_INTENT)]
