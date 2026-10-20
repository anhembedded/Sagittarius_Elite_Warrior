"""Read every log call's message template out of the source with `ast` (`PRO-019`, option C).

Nothing is imported or run: the files are parsed. The result is the catalogue the
viewer matches a plain line against; `scripts/render_log_templates.py` writes it and
`test_the_log_template_catalogue_is_current.py` fails when it is stale, so a new log
call cannot reach a viewer that does not know it.

A call is recognised by the name its receiver ends in (`logger`, `_logger`,
`self._log`, `_decision_log`, `log`, ...) and by a level method or `.log(level, ...)`.
`BacktestEventLogger.info` and an indicator script's `self.info` write to a pane,
not to `logging`, so they are not records and are not read. Messages it reads:

* a string literal with arguments: a `%`-template, each conversion a hole;
* a string literal with none: all fixed text (it has no params, and a line that
  matches it is exact, not a guess);
* an f-string: its literal parts are fixed text, each `{...}` a hole.

Anything else (`logger.warning(message, *args)`, a `.format` call) cannot be known
from the source; it is only counted, and the viewer falls back to its heuristic.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from Sagittarius_Elite_Warrior.src.support.log_view.template_model import LogTemplate

_LEVEL_METHODS = frozenset(
    {"trace", "debug", "info", "warning", "warn", "error", "critical", "exception"}
)
_RECEIVER = re.compile(r"(^|\.)_*(\w*_)?(log|logger)\w*$", re.IGNORECASE)
_CONVERSION = re.compile(
    r"%(?:\([^)]*\))?[#0\- +]*(?:\*|\d+)?(?:\.(?:\*|\d+))?[hlL]?([diouxXeEfFgGcrsa%])"
)
_KIND_OF_CONVERSION = {
    **dict.fromkeys("diu", "d"),
    **dict.fromkeys("eEfFgG", "f"),
    **dict.fromkeys("xXo", "x"),
    **dict.fromkeys("rsac", "s"),
}


@dataclass(frozen=True, slots=True)
class Catalogue:
    """The templates of every recognised log call, and what could not be read."""

    templates: tuple[LogTemplate, ...]
    #: Calls whose message is not a literal or an f-string (the viewer guesses these).
    variable_template_calls: int
    #: Templates left out because their fixed text is too short to tell lines apart.
    too_generic_templates: int


def percent_template(text: str) -> LogTemplate:
    """A `%`-style message: each conversion a hole, `%%` a fixed percent sign."""
    pieces: list[str] = []
    kinds: list[str] = []
    current = ""
    cursor = 0
    for found in _CONVERSION.finditer(text):
        current += text[cursor : found.start()]
        cursor = found.end()
        letter = found.group(1)
        if letter == "%":
            current += "%"
            continue
        pieces.append(current)
        kinds.append(_KIND_OF_CONVERSION[letter])
        current = ""
    pieces.append(current + text[cursor:])
    return LogTemplate(tuple(pieces), tuple(kinds))


def fstring_template(node: ast.JoinedStr) -> LogTemplate:
    """An f-string: constant parts are fixed text, every `{...}` is a hole."""
    pieces: list[str] = []
    kinds: list[str] = []
    current = ""
    for part in node.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            current += part.value
        else:
            pieces.append(current)
            kinds.append("h")
            current = ""
    pieces.append(current)
    return LogTemplate(tuple(pieces), tuple(kinds))


def _message_node(call: ast.Call) -> tuple[ast.expr | None, bool]:
    """The message argument of a log call and whether `%` arguments follow it.

    `logger.log(level, message, ...)` carries its message second."""
    if not isinstance(call.func, ast.Attribute):
        return None, False
    method = call.func.attr
    if method not in _LEVEL_METHODS and method != "log":
        return None, False
    if not _RECEIVER.search(ast.unparse(call.func.value)):
        return None, False
    position = 1 if method == "log" else 0
    if len(call.args) <= position:
        return None, False
    return call.args[position], len(call.args) > position + 1


def _templates_of(tree: ast.AST) -> Iterator[LogTemplate | None]:
    """One entry per log call in `tree`: its template, or `None` when unreadable."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        message, has_arguments = _message_node(node)
        if message is None:
            continue
        if isinstance(message, ast.Constant) and isinstance(message.value, str):
            if has_arguments:
                yield percent_template(message.value)
            else:
                yield LogTemplate((message.value,), ())
        elif isinstance(message, ast.JoinedStr):
            yield fstring_template(message)
        else:
            yield None


def extract_catalogue(source_root: Path) -> Catalogue:
    """Parse every `.py` file under `source_root` and collect its log templates."""
    found: set[LogTemplate] = set()
    variable = 0
    generic: set[LogTemplate] = set()
    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for template in _templates_of(tree):
            if template is None:
                variable += 1
            elif template.is_specific_enough():
                found.add(template)
            else:
                generic.add(template)
    ordered = tuple(sorted(found, key=lambda t: (t.pieces, t.kinds)))
    return Catalogue(ordered, variable, len(generic))
