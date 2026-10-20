"""What the module says about itself (`test_module_declarations.py` checks the rest)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    HealthContributorDescriptor,
    HealthProbeDescriptor,
    IOperationsRegistry,
    PreflightCheckDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.options_page_contribution import (
    OptionsPageContribution,
)
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.module import AlertingModule
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history.alerts_view import (
    ALERTS_SURFACE,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id


class _Recorder(IOperationsRegistry):
    def __init__(self) -> None:
        self.health: list[HealthContributorDescriptor] = []

    def declare_preflight(self, descriptor: PreflightCheckDescriptor) -> None:
        raise AssertionError("alerting declares no pre-flight check")

    def declare_health(self, descriptor: HealthContributorDescriptor) -> None:
        self.health.append(descriptor)

    def declare_probe(self, descriptor: HealthProbeDescriptor) -> None:
        raise AssertionError("alerting declares no health probe")


def test_the_module_listens_to_the_bots_and_the_tradings_stream_health() -> None:
    """`EPIC-036G`: the bot source reads `bots/contracts`; `EPIC-036B1` adds `trading`'s stream health."""
    module = AlertingModule()

    assert module.module_id == "alerting"
    assert module.dependencies == ["bots", "trading"]


def test_it_declares_one_health_section_named_alerting() -> None:
    recorder = _Recorder()

    AlertingModule().declare_operations(recorder)

    assert [(d.name, d.contributor_id) for d in recorder.health] == [
        ("alerting", "alerting")
    ]


class _OptionsRecorder:
    """The two methods of `IContributionRegistry` the module uses; any other call fails."""

    def __init__(self) -> None:
        self.pages: list[OptionsPageContribution] = []
        self.screens: list[ScreenContribution] = []

    def contribute_screen(self, contribution: ScreenContribution) -> None:
        self.screens.append(contribution)

    def contribute_options_page(self, contribution: OptionsPageContribution) -> None:
        self.pages.append(contribution)

    def __getattr__(self, name: str) -> object:
        raise AssertionError(
            f"alerting contributes an options page and a screen, not {name}"
        )


def test_it_contributes_the_alerts_page_of_tools_options_after_trading_and_market_data() -> (
    None
):
    """`EPIC-036D1`: orders 10 (trading) and 20 (market data) come first."""
    registry = _OptionsRecorder()

    AlertingModule().contribute(registry)  # type: ignore[arg-type]

    [page] = registry.pages
    assert (page.contributor_id, page.order) == ("alerting", 30)


def test_it_contributes_the_alerts_screen_after_bots_and_before_developer() -> None:
    """`EPIC-036D2`: the mode bar lists Alerts at item 80; Developer is 90."""
    registry = _OptionsRecorder()

    AlertingModule().contribute(registry)  # type: ignore[arg-type]

    [screen] = registry.screens
    assert (screen.contributor_id, screen.route) == ("alerting", "alerts")
    assert screen.nav is not None
    assert (screen.nav.title, screen.nav.icon, screen.nav.item_sequence) == (
        "Alerts",
        "bell",
        80,
    )
    assert screen.gated_by is None


def test_the_alerts_view_renders_the_surface_the_shell_declares() -> None:
    """The view declares its `Surface` because a module may not import `shell/`; this is
    what keeps that one declaration, not two."""
    assert surfaces_by_id()["alerts"] == ALERTS_SURFACE
