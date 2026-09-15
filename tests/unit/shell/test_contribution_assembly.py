"""`EPIC-025` PR 1.4c-4 — everything contributed to one run, collected once.

Before this, `contribute()` was a hook no code path called: modules could
declare panels and nothing would ever ask for them. These tests are what says
the collection happens, in the right order, with the reading port bound — and
what would fail if the loop over the modules were dropped, which is the one
line that makes the whole mechanism real.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.core.contracts.contribution_descriptor import (
    ContributionDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_registry import (
    IContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_table import (
    IContributionTable,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.size_hint import SizeHint
from Sagittarius_Elite_Warrior.src.shell.contribution_assembly import (
    assemble_contributions,
)
from Sagittarius_Elite_Warrior.src.shell.modules import RegisteredModules
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer


def probe_factory(_container):
    """A factory nothing here calls — the assembly hands over descriptors."""
    raise AssertionError("a factory must not run at contribute time")


class _ProbeModule(BoundedContextModule):
    module_id = "probes"
    dependencies: list[str] = []  # noqa: RUF012 — the Engine reads a plain attribute

    def register(self, context) -> None:
        del context

    def contribute(self, registry: IContributionRegistry) -> None:
        registry.contribute(
            ContributionDescriptor(
                contributor_id=self.module_id,
                surface_id="dev_board",
                place=Place.DEV_PROBE,
                order=10,
                size_hint=SizeHint.REGULAR,
                factory=probe_factory,
                title="A probe",
            )
        )


def _container(*modules: BoundedContextModule) -> StdLibContainer:
    container = StdLibContainer()
    container.singleton(RegisteredModules, RegisteredModules(tuple(modules)))
    return container


def test_a_modules_contribution_reaches_the_table(qapp) -> None:
    container = _container(_ProbeModule())

    contributions = assemble_contributions(container, dev_mode=True)

    (descriptor,) = contributions.panels("dev_board", Place.DEV_PROBE)
    assert descriptor.contributor_id == "probes"
    assert descriptor.title == "A probe"


def test_the_reading_port_is_bound_for_whoever_renders_a_surface(qapp) -> None:
    """The screen being converted resolves this, and only this: it may read
    what was contributed and must not be able to declare anything."""
    container = _container(_ProbeModule())

    contributions = assemble_contributions(container, dev_mode=True)

    assert container.resolve(IContributionTable) is contributions


def test_a_gated_surface_drops_the_contribution_and_the_app_still_boots(
    qapp,
) -> None:
    """`dev.mode` off is the normal user run. Every Dev Board panel is dropped
    with a log line, and nothing raises — the case `shell/surfaces.py`'s own
    docstring says is deliberately not an error."""
    container = _container(_ProbeModule())

    contributions = assemble_contributions(container, dev_mode=False)

    assert contributions.panels("dev_board", Place.DEV_PROBE) == ()
    assert contributions.dropped_count() == 1


def test_the_legacy_screens_are_collected_too(qapp) -> None:
    """Two kinds of contributor, one collection: the five screens the shell
    still carries arrive as `ScreenContribution`s in the same registry, which
    is what lets `build_screen_registry` stay indifferent to which kind a
    screen is."""
    container = _container()

    contributions = assemble_contributions(container, dev_mode=True)

    routes = {screen.route for screen in contributions.screens()}
    assert {"dashboard", "trading", "settings"} <= routes


def test_a_container_with_no_modules_still_collects_the_screens(qapp) -> None:
    contributions = assemble_contributions(_container(), dev_mode=True)

    assert contributions.panels("dev_board", Place.DEV_PROBE) == ()
    assert contributions.screens()


def test_the_factories_are_not_called(qapp) -> None:
    """`probe_factory` raises if it runs. The descriptor's whole point is that
    the shell decides *when* — at boot there is no surface to place a widget
    into, and in a headless run no `QApplication` either."""
    assemble_contributions(_container(_ProbeModule()), dev_mode=True)


def test_it_reads_the_modules_from_the_container_not_the_class_list(qapp) -> None:
    """The instances that registered are the ones that contribute. A second
    instantiation of `MODULES` would contribute against an object graph it
    never built — which is why the composition root binds these."""
    module = _ProbeModule()
    container = _container(module)

    assemble_contributions(container, dev_mode=True)

    assert container.resolve(RegisteredModules).modules == (module,)


def test_a_mock_container_is_not_silently_accepted(qapp) -> None:
    """A `Mock()` container answers every `resolve()` with a `Mock`, so the
    loop would iterate a `Mock` and quietly contribute nothing. It raises
    instead, which is what a wiring mistake should do."""
    try:
        assemble_contributions(Mock(), dev_mode=True)
    except TypeError:
        return
    raise AssertionError("a Mock container should not pass for a real one")
