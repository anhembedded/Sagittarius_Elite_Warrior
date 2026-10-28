"""`EPIC-047E` - the session's line before the tab is first shown, and with no profile chosen, says what is true."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.shell.vps_tab.vps_tab_session import (
    NO_PROFILE_WORDS,
    NOT_STARTED_WORDS,
    VpsTabSession,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.link_profiles import (
    LinkProfiles,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.transport_registry import (
    TransportRegistry,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.dispatcher_world import (
    _Local,
)


def _session() -> VpsTabSession:
    kinds = BotKindCatalog([GridKind(None, GridThresholds())])  # type: ignore[arg-type]
    return VpsTabSession(LinkProfiles(), TransportRegistry(), _Local(), kinds)


def test_before_the_first_show_the_line_does_not_claim_a_missing_profile() -> None:
    line = _session().host_line()

    assert line.text == NOT_STARTED_WORDS
    assert not line.ok


def test_with_no_profile_chosen_the_line_says_so_once_the_tab_is_shown() -> None:
    session = _session()

    session.opened()

    assert session.host_line().text == NO_PROFILE_WORDS
    session.stop()
