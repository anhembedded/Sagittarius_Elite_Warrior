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
from Sagittarius_Elite_Warrior.src.modules.alerting.module import AlertingModule


class _Recorder(IOperationsRegistry):
    def __init__(self) -> None:
        self.health: list[HealthContributorDescriptor] = []

    def declare_preflight(self, descriptor: PreflightCheckDescriptor) -> None:
        raise AssertionError("alerting declares no pre-flight check")

    def declare_health(self, descriptor: HealthContributorDescriptor) -> None:
        self.health.append(descriptor)

    def declare_probe(self, descriptor: HealthProbeDescriptor) -> None:
        raise AssertionError("alerting declares no health probe")


def test_the_module_listens_to_the_bots_only() -> None:
    """`EPIC-036G`: the bot source reads `bots/contracts`; `EPIC-036B` adds `trading`."""
    module = AlertingModule()

    assert module.module_id == "alerting"
    assert module.dependencies == ["bots"]


def test_it_declares_one_health_section_named_alerting() -> None:
    recorder = _Recorder()

    AlertingModule().declare_operations(recorder)

    assert [(d.name, d.contributor_id) for d in recorder.health] == [
        ("alerting", "alerting")
    ]


class _OptionsRecorder:
    """The one method of `IContributionRegistry` the module uses; any other call fails."""

    def __init__(self) -> None:
        self.pages: list[OptionsPageContribution] = []

    def contribute_options_page(self, contribution: OptionsPageContribution) -> None:
        self.pages.append(contribution)

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"alerting contributes only an options page, not {name}")


def test_it_contributes_the_alerts_page_of_tools_options_after_trading_and_market_data() -> (
    None
):
    """`EPIC-036D1`: orders 10 (trading) and 20 (market data) come first."""
    registry = _OptionsRecorder()

    AlertingModule().contribute(registry)  # type: ignore[arg-type]

    [page] = registry.pages
    assert (page.contributor_id, page.order) == ("alerting", 30)
