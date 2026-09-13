"""`register()` may bind; it may not resolve, and it may not claim twice
(SDD, "register() versus boot()", boot steps 3–5).

These two rules are why the shell hands each module a `RegisteringContainer`
instead of the real one. The tests use fake modules because the real list is
empty until PR 0.4 — the mechanism is what Phase 0 ships, and a mechanism
nobody has exercised is a mechanism nobody can trust.
"""

from __future__ import annotations

from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.core.bounded_context_module import (
    BoundedContextModule,
)
from Sagittarius_Elite_Warrior.src.shell.double_claim_check import DoubleClaimError
from Sagittarius_Elite_Warrior.src.shell.module_registration import register_modules
from Sagittarius_Elite_Warrior.src.shell.registering_container import (
    ResolveDuringRegisterError,
)
from sagittarius_engine import App
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


class IKlines:
    pass


class SqliteKlines(IKlines):
    pass


class RestKlines(IKlines):
    pass


class _MarketData(BoundedContextModule):
    module_id = "market_data"

    def register(self, context: Any) -> None:
        context.container.singleton(IKlines, SqliteKlines)


class _TradingClaimingKlines(BoundedContextModule):
    module_id = "trading"

    def register(self, context: Any) -> None:
        context.container.singleton(IKlines, RestKlines)


class _ResolvesTooEarly(BoundedContextModule):
    module_id = "impatient"

    def register(self, context: Any) -> None:
        context.container.resolve(IKlines)


class _RecordsOrder(BoundedContextModule):
    #: Class attribute so both instances append to one list.
    order_seen: list[str] = []  # noqa: RUF012

    def register(self, context: Any) -> None:
        type(self).order_seen.append(self.module_id)


class _First(_RecordsOrder):
    module_id = "first"


class _Second(_RecordsOrder):
    module_id = "second"


@pytest.fixture
def app() -> App:
    container = StdLibContainer()
    return App(container, MemoryEventBus(None))


def test_a_module_registers_through_the_real_container(app: App) -> None:
    modules, _check = register_modules(app, [_MarketData])
    assert [module.module_id for module in modules] == ["market_data"]
    assert app.container.resolve(IKlines).__class__ is SqliteKlines


def test_the_spy_is_removed_again_afterwards(app: App) -> None:
    real_container = app.context.container
    register_modules(app, [_MarketData])
    assert app.context.container is real_container


def test_resolving_from_register_fails_and_names_the_module(app: App) -> None:
    with pytest.raises(ResolveDuringRegisterError) as failure:
        register_modules(app, [_ResolvesTooEarly])
    message = str(failure.value)
    assert "impatient" in message
    assert "boot()" in message


def test_the_spy_is_removed_even_when_register_fails(app: App) -> None:
    real_container = app.context.container
    with pytest.raises(ResolveDuringRegisterError):
        register_modules(app, [_ResolvesTooEarly])
    assert app.context.container is real_container


def test_two_modules_claiming_one_type_fail_before_boot(app: App) -> None:
    with pytest.raises(DoubleClaimError, match="IKlines"):
        register_modules(app, [_MarketData, _TradingClaimingKlines])


def test_modules_register_in_the_list_order(app: App) -> None:
    _RecordsOrder.order_seen.clear()
    register_modules(app, [_Second, _First])
    assert _RecordsOrder.order_seen == ["second", "first"]


def test_a_module_without_an_id_is_rejected() -> None:
    class _Nameless(BoundedContextModule):
        def register(self, context: Any) -> None: ...

    with pytest.raises(ValueError, match="module_id"):
        _Nameless()


def test_the_module_id_is_the_extension_name_the_engine_sees() -> None:
    module = _MarketData()
    assert module.name == "market_data"
    assert module.descriptor.name == "market_data"
