"""`EPIC-035D` — a venue session that applies the call policy to every request.

The python-binance client is the one object every adapter of a venue talks to, so
the policy wraps it there once: reads and cancels retry, everything else (an order's
submit, a leverage change) is sent at most once, and every call stops at a closed
gate. What a method is called decides which; a name nobody classified is sent once.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_policy import (
    ExchangeCallPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limit_gate import (
    RateLimitGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limited_api_exception import (
    RateLimitedApiException,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.resilient_session import (
    CallMode,
    ResilientSession,
    call_mode_of,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.exchange_answers import (
    rate_limited,
    timeout,
)


class _RawClient:
    """The few things of python-binance's `Client` the session touches."""

    def __init__(self) -> None:
        self.timestamp_offset = -37
        self.response: SimpleNamespace | None = None
        self.calls: list[str] = []
        self.failures: dict[str, list[Exception]] = {}

    def _answer(self, name: str) -> str:
        self.calls.append(name)
        queued = self.failures.get(name)
        if queued:
            raise queued.pop(0)
        return f"{name} answered"

    def get_order(self, **_: object) -> str:
        return self._answer("get_order")

    def cancel_order(self, **_: object) -> str:
        return self._answer("cancel_order")

    def create_order(self, **_: object) -> str:
        return self._answer("create_order")

    def futures_cancel_order(self, **_: object) -> str:
        return self._answer("futures_cancel_order")

    def futures_account(self, **_: object) -> str:
        return self._answer("futures_account")

    def futures_change_leverage(self, **_: object) -> str:
        return self._answer("futures_change_leverage")


class _Session:
    def __init__(self) -> None:
        self.at = 0.0
        self.sleeps: list[float] = []
        self.raw = _RawClient()
        self.gate = RateLimitGate(lambda: self.at)
        self.policy = ExchangeCallPolicy(
            self.gate, sleep=self.sleeps.append, wall_seconds=lambda: 0.0
        )
        self.session = ResilientSession(self.raw, self.policy)


@pytest.mark.parametrize(
    ("name", "mode"),
    [
        ("get_order", CallMode.RETRIED),
        ("get_open_orders", CallMode.RETRIED),
        ("get_all_orders", CallMode.RETRIED),
        ("get_my_trades", CallMode.RETRIED),
        ("get_account", CallMode.RETRIED),
        ("get_server_time", CallMode.RETRIED),
        ("ping", CallMode.RETRIED),
        ("cancel_order", CallMode.RETRIED),
        ("cancel_all_open_orders", CallMode.RETRIED),
        ("futures_cancel_order", CallMode.RETRIED),
        ("futures_cancel_all_open_orders", CallMode.RETRIED),
        ("futures_cancel_algo_order", CallMode.RETRIED),
        ("futures_get_order", CallMode.RETRIED),
        ("futures_get_open_orders", CallMode.RETRIED),
        ("futures_account", CallMode.RETRIED),
        ("futures_position_information", CallMode.RETRIED),
        ("futures_time", CallMode.RETRIED),
        ("create_order", CallMode.ONCE),
        ("create_test_order", CallMode.ONCE),
        ("futures_create_order", CallMode.ONCE),
        ("futures_create_test_order", CallMode.ONCE),
        ("futures_create_algo_order", CallMode.ONCE),
        ("futures_change_leverage", CallMode.ONCE),
        ("futures_change_margin_type", CallMode.ONCE),
        ("order_market_buy", CallMode.ONCE),
        ("a_method_nobody_classified", CallMode.ONCE),
    ],
)
def test_what_a_method_is_called_decides_whether_it_may_be_retried(
    name: str, mode: CallMode
) -> None:
    assert call_mode_of(name) is mode


def test_a_cancel_that_timed_out_is_sent_again() -> None:
    world = _Session()
    world.raw.failures["cancel_order"] = [timeout()]

    assert world.session.cancel_order(symbol="BTCUSDT") == "cancel_order answered"
    assert world.raw.calls == ["cancel_order", "cancel_order"]


def test_a_submit_that_timed_out_is_sent_once_and_the_failure_surfaces() -> None:
    world = _Session()
    world.raw.failures["create_order"] = [timeout(), timeout()]

    with pytest.raises(type(timeout())):
        world.session.create_order(symbol="BTCUSDT")

    assert world.raw.calls == ["create_order"]


def test_a_leverage_change_that_timed_out_is_not_repeated() -> None:
    world = _Session()
    world.raw.failures["futures_change_leverage"] = [timeout()]

    with pytest.raises(type(timeout())):
        world.session.futures_change_leverage(symbol="BTCUSDT", leverage=3)

    assert world.raw.calls == ["futures_change_leverage"]


def test_a_rate_limit_on_a_submit_is_named_and_the_order_is_not_resent() -> None:
    world = _Session()
    world.raw.failures["create_order"] = [rate_limited(retry_after="20")]

    with pytest.raises(RateLimitedApiException):
        world.session.create_order(symbol="BTCUSDT")
    with pytest.raises(RateLimitedApiException):
        world.session.create_order(symbol="BTCUSDT")

    assert world.raw.calls == ["create_order"], "the second never left the machine"


def test_a_closed_gate_stops_every_method_not_only_the_one_that_was_limited() -> None:
    world = _Session()
    world.raw.failures["get_order"] = [rate_limited(retry_after="20")]
    with pytest.raises(RateLimitedApiException):
        world.session.get_order(symbol="BTCUSDT")

    with pytest.raises(RateLimitedApiException):
        world.session.futures_cancel_order(symbol="BTCUSDT")
    with pytest.raises(RateLimitedApiException):
        world.session.create_order(symbol="BTCUSDT")

    assert world.raw.calls == ["get_order"]


def test_attributes_are_passed_through_untouched() -> None:
    world = _Session()
    assert world.session.timestamp_offset == -37


def test_the_used_weight_header_of_the_last_answer_is_read_after_a_success() -> None:
    world = _Session()
    seen: list[str | None] = []
    world.policy.note_used_weight_header = seen.append  # type: ignore[method-assign]
    world.raw.response = SimpleNamespace(headers={"x-mbx-used-weight-1m": "321"})

    world.session.get_order(symbol="BTCUSDT")

    assert seen == ["321"]


def test_a_client_with_no_response_yet_is_not_an_error() -> None:
    world = _Session()
    world.raw.response = None
    assert world.session.futures_account() == "futures_account answered"
