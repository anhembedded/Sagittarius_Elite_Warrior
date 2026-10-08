"""`EPIC-035H` — the graph `create_app()` builds honours the instance it is given.

A test that constructs a read-only wrapper proves the wrapper, not that the app
uses it (`CS-002`), so this asks the real composition root: given the access of
a second copy, every venue's client factory, the bot store and the bot runner
are the read-only ones; given nothing, none is.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.infrastructure.instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.read_only_bot_runner import (
    ReadOnlyBotRunner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.read_only_bot_store import (
    ReadOnlyBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.read_only_trading_client_factory import (
    ReadOnlyTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.interfaces.i_container import IContainer


@pytest.fixture
def second_copy(tmp_path: Path) -> InstanceAccess:
    first = InstanceAccess.acquire(tmp_path / "instance.lock")
    assert first.read_only is False
    return InstanceAccess.acquire(tmp_path / "instance.lock")


def _graph(instance: IInstanceAccess | None) -> IContainer:
    return create_app(ConfigManager(), instance).context.container


def test_the_app_is_writable_when_it_is_given_no_instance() -> None:
    container = _graph(None)

    assert container.resolve(IInstanceAccess).read_only is False
    assert not isinstance(container.resolve(IBotRunner), ReadOnlyBotRunner)
    assert not isinstance(container.resolve(IBotStore), ReadOnlyBotStore)


def test_a_second_copy_gets_read_only_bots(second_copy: InstanceAccess) -> None:
    container = _graph(second_copy)

    assert container.resolve(IInstanceAccess) is second_copy
    assert isinstance(container.resolve(IBotRunner), ReadOnlyBotRunner)
    assert isinstance(container.resolve(IBotStore), ReadOnlyBotStore)


def test_a_second_copy_gets_read_only_trading_on_every_venue(
    second_copy: InstanceAccess,
) -> None:
    contexts = _graph(second_copy).resolve(IVenueContexts)

    factories = [contexts.get(venue).client_factory for venue in contexts.enabled()]

    assert factories, "at least one venue is enabled"
    assert all(isinstance(f, ReadOnlyTradingClientFactory) for f in factories)
