"""`EPIC-034C` (decision D3, option A) — no live order can be sent unless the
reconciliation ran: the successor of the rule "`TradingSessionState.enable()`
has one call site", now that no switch exists to call it.

@details The proof is four facts, each read from `src/` by `ast`, so a change
to any of them goes red here rather than in production:

1. **One way to open the session.** `session_state.enable(...)` is called from
   `SessionReadiness` and nowhere else, and `SessionReadiness` reads the whole
   account (`get_positions()`) before it. So "the session is open" implies "the
   account was reconciled".
2. **Every order needs the session open.** `ExecuteOrderCommandHandler`'s
   safety gate refuses (`TRADING_SWITCH_OFF`) while `session_state.enabled` is
   false, and it is the one place a live order is placed. So no order path
   skips fact 1, by any road.
3. **Only the three actions open it.** `ensure_ready()` is called from Start
   bot (`GridStartPreconditions`), Arm strategy (`ArmStrategyCommandHandler`)
   and the manual order (`ExecuteOrderCommandHandler`, when the request
   `opens_session`), plus the command handler behind the port
   (`ITradingSession.ensure_ready` dispatches to it). An automated caller — a
   bot's tick, a strategy's signal — never opens it, so a late order cannot
   undo an Emergency Stop.
4. **Every live-order caller is accounted for.** Each file that calls
   `submit(..., live=True)` is declared below with how its orders are covered.
   A new caller fails here until its author says so, which is the point.

Mutation-verified by `test_the_scanners_can_fail`. The testnet tier proves the
real lifecycle with no enable step (`tests/testnet/`), not run without
credentials.

Retire when: the order session is no longer a state a handler checks (orders
carry their own reconciliation proof), or `ExecuteOrderCommandHandler` stops
being the one place a live order is placed.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"
_SESSION_READINESS = "src/modules/trading/application/session/session_readiness.py"
_EXECUTE_ORDER = "src/modules/trading/application/orders/execute_order/handler.py"

#: Where `ensure_ready()` may be called from, and why.
_ENSURE_READY_CALLERS = {
    "src/modules/bots/application/services/grid_start_preconditions.py": "Start bot",
    "src/modules/strategy/application/use_cases/arm_strategy/handler.py": (
        "Arm strategy"
    ),
    _EXECUTE_ORDER: "a manual order (`opens_session`)",
    "src/modules/trading/application/session/ensure_session_ready/handler.py": (
        "the command behind the port"
    ),
}

#: Every file that sends a live order through `IOrderSubmission.submit`.
_LIVE_ORDER_CALLERS = {
    "src/modules/trading/ui/desk/order_entry/order_entry_presenter.py": (
        "the manual order: sends `opens_session=True`, so the handler reconciles"
    ),
    "src/modules/bots/application/services/bot_order_gateway.py": (
        "a bot's order: Start bot opened the session (`GridStartPreconditions`)"
    ),
    "src/modules/strategy/application/services/live_trading_coordinator.py": (
        "a strategy's order: Arm strategy opened the session "
        "(`ArmStrategyCommandHandler`)"
    ),
    "src/modules/trading/ui/desk/account_tabs/account_tab_actions.py": (
        "closes a position the session placed; reduce-only, session required"
    ),
    "src/modules/trading/ui/desk/order_entry/protective_order_follower.py": (
        "protects a position the session placed; reduce-only, session required"
    ),
}


def _source_files() -> list[Path]:
    """Production code: the verified fakes and contract suites under
    `contracts/testing/` are doubles, not callers."""
    return [
        path
        for path in sorted(_SRC.rglob("*.py"))
        if "contracts/testing" not in path.as_posix()
    ]


def _relative(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _calls(source: str) -> list[ast.Call]:
    return [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Call)]


def calls_state_enable(source: str) -> bool:
    """A call of `<...>session_state.enable(...)`."""
    return any(
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "enable"
        and ast.unparse(call.func.value).endswith("session_state")
        for call in _calls(source)
    )


def calls_ensure_ready(source: str) -> bool:
    return any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "ensure_ready"
        for call in _calls(source)
    )


def sends_a_live_order(source: str) -> bool:
    """A call of `<...>.submit(..., live=True)`."""
    return any(
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "submit"
        and any(
            kw.arg == "live"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in call.keywords
        )
        for call in _calls(source)
    )


def passes_opens_session(source: str) -> bool:
    """A call with the keyword `opens_session=True`."""
    return any(
        kw.arg == "opens_session"
        and isinstance(kw.value, ast.Constant)
        and kw.value.value is True
        for call in _calls(source)
        for kw in call.keywords
    )


def _files_where(scan) -> list[str]:
    return [
        _relative(path)
        for path in _source_files()
        if scan(path.read_text(encoding="utf-8"))
    ]


def first_call_line(source: str, attr: str) -> int | None:
    """The first line calling `<...>.attr(...)`, comments and docstrings aside."""
    lines = [
        call.lineno
        for call in _calls(source)
        if isinstance(call.func, ast.Attribute) and call.func.attr == attr
    ]
    return min(lines) if lines else None


def first_gate_refuses_a_closed_session(source: str) -> bool:
    """`_first_blocked_safety_gate`'s first statement refuses, as
    `TRADING_SWITCH_OFF`, when `scope.session_state.enabled` is false."""
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "_first_blocked_safety_gate"
        ):
            body = [s for s in node.body if not isinstance(s, ast.Expr)]
            first = body[0]
            return (
                isinstance(first, ast.If)
                and ast.unparse(first.test) == "not scope.session_state.enabled"
                and "TRADING_SWITCH_OFF" in ast.unparse(first.body[0])
            )
    return False


def test_the_session_opens_in_one_place_and_that_place_reads_the_account() -> None:
    assert _files_where(calls_state_enable) == [_SESSION_READINESS]
    readiness = (_REPO_ROOT / _SESSION_READINESS).read_text(encoding="utf-8")
    read = first_call_line(readiness, "get_positions")
    opened = first_call_line(readiness, "enable")
    assert read is not None and opened is not None
    assert read < opened


def test_every_live_order_needs_the_session_open() -> None:
    handler = (_REPO_ROOT / _EXECUTE_ORDER).read_text(encoding="utf-8")
    assert first_gate_refuses_a_closed_session(handler)


def test_only_the_three_actions_open_the_session() -> None:
    assert sorted(_files_where(calls_ensure_ready)) == sorted(_ENSURE_READY_CALLERS)


def test_a_manual_order_opens_the_session_and_an_automated_one_does_not() -> None:
    """Only the order panel states `opens_session=True`; the submission service
    merely carries the request's value through."""
    assert _files_where(passes_opens_session) == [
        "src/modules/trading/ui/desk/order_entry/order_entry_presenter.py"
    ]


def test_every_caller_of_a_live_order_is_accounted_for() -> None:
    assert sorted(_files_where(sends_a_live_order)) == sorted(_LIVE_ORDER_CALLERS)


def test_the_scanners_can_fail() -> None:
    """Mutation-verify (`testing-rule.md` §2): each scanner fires on the shape
    it guards and ignores a docstring that merely names it."""
    assert calls_state_enable("scope.session_state.enable(set())\n")
    assert not calls_state_enable('"""session_state.enable(set())"""\n')
    assert not calls_state_enable("widget.enable(True)\n")
    assert calls_ensure_ready("session.ensure_ready()\n")
    assert not calls_ensure_ready('"""ensure_ready()"""\nx = 1\n')
    assert sends_a_live_order("ports.order_submission.submit(request, live=True)\n")
    assert not sends_a_live_order("ports.order_submission.submit(request)\n")
    assert not sends_a_live_order("ports.order_submission.submit(request, live=live)\n")
    assert passes_opens_session("replace(request, opens_session=True)\n")
    assert not passes_opens_session("replace(request, opens_session=False)\n")
    assert not passes_opens_session("Command(opens_session=request.opens_session)\n")
    gate = "class C:\n    def _first_blocked_safety_gate(c, s):\n        {}\n"
    refusing = (
        "if not scope.session_state.enabled:\n            return G.TRADING_SWITCH_OFF"
    )
    assert first_gate_refuses_a_closed_session(gate.format(refusing))
    assert not first_gate_refuses_a_closed_session(gate.format("return None"))
    assert first_call_line("x = 1\nread.get_positions()\n", "get_positions") == 2
    assert first_call_line('"""get_positions()"""\n', "get_positions") is None
