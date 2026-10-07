"""No UI module puts an exception, or the text of one, into a widget (`BOT-169`).

On 2026-10-07 the Bots panel drew a gateway's `502 Bad Gateway` page as its
status text, because `str(exc)` went straight into a label. An exception's text
is for the log and, behind Details…, for the person who asks. What a screen
says is a sentence its author wrote (what failed, what to do), told through
`INotifier` (`src/core/contracts/i_notifier.py`), which picks the surface
(`ui-presentation-rule.md` §10). The technical text travels as the notice's
`detail`, produced by `failure_detail()`, the one function that turns an
exception into screen text.

**What is found**, in every UI file (any path with a `ui` or `ui_kit` segment,
`src/presentation/ui`, `src/support/charting`), outside a logging call, a
`raise` and a `failure_detail(...)` call:

- `str(x)`, `repr(x)` or `format(x)` of an exception name;
- an f-string, a `%`, a `+` or a `.format()` that interpolates one;
- `traceback.format_*`.

An *exception name* is the name an enclosing `except ... as name` binds, or one
of `exc`, `exception`, `err`, `error`, `failure`: the names a worker's failure
text is carried under on its way to the UI thread. Name your values otherwise
(`detail`, `reason`) when they are not an exception's text.

Not seen, by design: text reached through a name the guard cannot know is an
exception's (a `str` parameter called `message` that a caller filled from one).
`failure_detail` on the producing side and the loose names above are what make
that path visible; review row H7 holds the rest.

Retire when: no screen takes a failure's text at all, only a `FailureNotice`.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
_UI_SEGMENTS = frozenset({"ui", "ui_kit"})
_UI_DIRS = ("src/presentation/ui", "src/support/charting")
_LOOSE_NAMES = frozenset({"exc", "exception", "err", "error", "failure"})
_LOG_METHODS = frozenset(
    {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
)
_FORMATTERS = frozenset({"str", "repr", "format"})
_TRACEBACK = frozenset({"format_exc", "format_exception", "format_tb", "print_exc"})
#: The files that are the Details… of an unhandled exception: the critical-error
#: dialog (a modal message box whose technical text is the traceback) and the
#: hook that builds it. Each must still hold a hit, so the entry cannot go stale.
_EXEMPT = {
    "src/presentation/ui/components/critical_error_dialog.py": "the crash dialog's Details",
    "src/presentation/ui/app_bootstrapper.py": "the hook that logs and shows the crash dialog",
}


def is_ui_file(rel: str) -> bool:
    parts = rel.split("/")
    return (
        any(segment in _UI_SEGMENTS for segment in parts[:-1])
        or rel.startswith(_UI_DIRS)
    ) and rel.startswith("src/")


def _is_logging_call(node: ast.Call) -> bool:
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr in _LOG_METHODS):
        return False
    owner = func.value
    name = owner.id if isinstance(owner, ast.Name) else getattr(owner, "attr", "")
    return "log" in str(name).lower()


def _is_failure_detail(node: ast.Call) -> bool:
    func = node.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
    return name == "failure_detail"


def _is_type_of(node: ast.Call) -> bool:
    """`type(exc)`: the class, whose name is not the exception's text."""
    return isinstance(node.func, ast.Name) and node.func.id == "type"


class _Seen(ast.NodeVisitor):
    def __init__(self) -> None:
        self.found: list[str] = []
        self._bound: list[str] = []
        self._safe = 0

    def _is_exception(self, node: ast.AST) -> bool:
        return isinstance(node, ast.Name) and (
            node.id in self._bound or node.id in _LOOSE_NAMES
        )

    def _mentions_exception(self, node: ast.AST) -> bool:
        """Whether `node` reads an exception name outside `failure_detail(...)`,
        `type(...)` and a logging call, which the guard accepts."""
        if self._is_exception(node):
            return True
        if isinstance(node, ast.Call) and (
            _is_failure_detail(node) or _is_type_of(node) or _is_logging_call(node)
        ):
            return False
        return any(self._mentions_exception(c) for c in ast.iter_child_nodes(node))

    def _flag(self, node: ast.AST, what: str) -> None:
        if not self._safe:
            self.found.append(f"line {node.lineno}: {what}")  # type: ignore[attr-defined]

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self._bound.append(node.name)
        self.generic_visit(node)
        if node.name:
            self._bound.pop()

    def visit_Raise(self, node: ast.Raise) -> None:
        self._safe += 1
        self.generic_visit(node)
        self._safe -= 1

    def visit_Call(self, node: ast.Call) -> None:
        safe = _is_logging_call(node) or _is_failure_detail(node)
        func = node.func
        if safe:
            self._safe += 1
        else:
            name = func.id if isinstance(func, ast.Name) else ""
            if name in _FORMATTERS and any(self._is_exception(a) for a in node.args):
                self._flag(node, f"{name}() of an exception")
            elif isinstance(func, ast.Attribute):
                if func.attr in _TRACEBACK:
                    self._flag(node, f"traceback.{func.attr}()")
                elif func.attr == "format" and any(
                    self._mentions_exception(a) for a in node.args
                ):
                    self._flag(node, ".format() of an exception")
        self.generic_visit(node)
        if safe:
            self._safe -= 1

    def visit_FormattedValue(self, node: ast.FormattedValue) -> None:
        if self._mentions_exception(node.value):
            self._flag(node, "an exception in an f-string")
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, ast.Mod | ast.Add) and (
            self._is_exception(node.left) or self._is_exception(node.right)
        ):
            self._flag(node, "an exception in a % or + expression")
        self.generic_visit(node)


def exception_text_sites(source: str) -> list[str]:
    """Each place in `source` that turns an exception into text for a screen."""
    seen = _Seen()
    seen.visit(ast.parse(source))
    return seen.found


def _ui_sources() -> list[tuple[str, Path]]:
    if not _SRC_ROOT.is_dir():
        raise FileNotFoundError(f"{_SRC_ROOT} does not exist; retarget this guard")
    return [
        (rel, path)
        for path in sorted(_SRC_ROOT.rglob("*.py"))
        if "__pycache__" not in path.parts
        and is_ui_file(rel := path.relative_to(_REPO_ROOT).as_posix())
    ]


def test_the_scan_has_a_subject() -> None:
    assert len(_ui_sources()) > 150, "the scan found almost no UI file"


def test_no_ui_module_puts_an_exception_into_a_widget() -> None:
    found = {
        rel: hits
        for rel, path in _ui_sources()
        if rel not in _EXEMPT
        and (hits := exception_text_sites(path.read_text("utf-8")))
    }
    assert not found, (
        "tell the user through INotifier (src/core/contracts/i_notifier.py): a "
        "headline you write, the technical text as `detail=failure_detail(exc)`:\n"
        + "\n".join(f"{rel}: {', '.join(hits)}" for rel, hits in sorted(found.items()))
    )


def test_every_exemption_still_has_a_hit() -> None:
    for rel in _EXEMPT:
        assert exception_text_sites((_REPO_ROOT / rel).read_text("utf-8")), rel


def test_failure_detail_inside_an_f_string_and_type_of_are_allowed() -> None:
    source = (
        "try:\n    run()\nexcept OSError as e:\n"
        "    show(f'failed: {failure_detail(e)} ({type(e).__name__})')\n"
    )
    assert exception_text_sites(source) == []


def test_a_planted_str_of_the_bound_exception_is_seen() -> None:
    source = (
        "try:\n    run()\nexcept Exception as boom:\n    label.setText(str(boom))\n"
    )
    assert exception_text_sites(source) == ["line 4: str() of an exception"]


def test_a_planted_f_string_is_seen_for_a_bound_and_a_loose_name() -> None:
    bound = "try:\n    run()\nexcept OSError as e:\n    show(f'failed: {e}')\n"
    loose = "def on_failed(error):\n    status.setText(f'Could not read: {error}')\n"
    assert exception_text_sites(bound) == ["line 4: an exception in an f-string"]
    assert exception_text_sites(loose) == ["line 2: an exception in an f-string"]


def test_an_exception_attribute_in_an_f_string_is_seen() -> None:
    source = "try:\n    run()\nexcept OSError as e:\n    show(f'{e.args[0]}')\n"
    assert len(exception_text_sites(source)) == 1


def test_a_planted_concatenation_and_format_are_seen() -> None:
    plus = "def f(exc):\n    show('failed: ' + exc)\n"
    fmt = "def f(exc):\n    show('failed: {}'.format(exc))\n"
    assert len(exception_text_sites(plus)) == 1
    assert len(exception_text_sites(fmt)) == 1


def test_a_traceback_in_a_widget_is_seen() -> None:
    source = "def f():\n    show(traceback.format_exc())\n"
    assert exception_text_sites(source) == ["line 2: traceback.format_exc()"]


def test_logging_a_raising_and_failure_detail_are_allowed() -> None:
    source = (
        "try:\n    run()\nexcept OSError as e:\n"
        "    logger.warning('failed: %s', e)\n"
        "    logger.error(f'failed: {e}')\n"
        "    detail = failure_detail(e)\n"
        "    raise RuntimeError(f'wrapped: {e}') from e\n"
    )
    assert exception_text_sites(source) == []


def test_a_name_that_is_not_an_exception_is_left_alone() -> None:
    source = "def f(symbol, detail):\n    show(f'{symbol}: {detail}')\n"
    assert exception_text_sites(source) == []


def test_a_ui_file_is_one_under_a_ui_segment() -> None:
    assert is_ui_file("src/modules/bots/ui/bots_screen/bots_view.py")
    assert is_ui_file("src/support/ui_kit/message_bar.py")
    assert is_ui_file("src/presentation/ui/main_window.py")
    assert not is_ui_file("src/modules/bots/application/services/grid_executor.py")
    assert not is_ui_file("src/presentation/cli/order_dry_run_cmd.py")
