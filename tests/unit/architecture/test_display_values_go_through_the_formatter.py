"""A number or a time shown in the UI is written by the app's formatter
(`EPIC-033N`, `ui-presentation-rule.md`).

`AppValueFormatter` (`src/support/ui_kit/value_formatter.py`) is the one place
a price, quantity, money amount, percent, duration or timestamp becomes text:
precision per symbol, one timestamp format, one percent format. Before it,
each screen kept its own `_format_price` and f-string, and the same figure
read three ways. `EPIC-033N` moved every display site onto it; this ban keeps
a new one from writing its own.

What is scanned: UI code, meaning every `ui/` package of a module,
`support/ui_kit`, `support/charting`, `presentation` and `shell`. What is found:
- an f-string field with a numeric format spec (`{x:.2f}`, `{x:,}`, `{x:g}`,
  `{x:.1%}`);
- a `.strftime(...)` call.

Text inside a logging call is not display, and is not counted.

The exemptions are files, each with its reason. A file whose formatting is
not display (a file name, an editable field's text read back, a log line
built by a helper, the formatter's own internals) is named here, never a
line.

Retire when: the app stops writing display text in Python (no such plan).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"

_UI_PREFIXES = (
    "src/support/ui_kit/",
    "src/support/charting/",
    "src/presentation/",
    "src/shell/",
)

#: Outside the scan: text a terminal prints is not a widget's, and the CLI
#: has its own formatters (`order_preview_formatter.py`, ...).
_NOT_UI = ("src/presentation/cli/",)

#: A format spec that writes a number or a time: grouping, a precision, a
#: float, exponent or percent presentation type, or a `%` directive of a
#: `datetime` spec anywhere in it (`{when:%Y-%m-%d %H:%M}`, review of PR #389).
_NUMERIC_SPEC = re.compile(r"[,_%]|\.\d|[eEfFgG]$")

_LOGGING_CALLS = frozenset(
    {"trace", "debug", "info", "warning", "error", "exception", "critical", "log"}
)

#: path -> why its formatting is not display text.
EXEMPT: dict[str, str] = {
    "src/support/ui_kit/value_formatter.py": "the formatter itself",
    "src/support/ui_kit/services/display_timezone_service.py": (
        "the formatter's timestamp backend (format_display_datetime)"
    ),
    "src/support/ui_kit/time_range_picker/instant_text.py": (
        "format_instant/parse_instant: an editable field's text, read back"
    ),
    "src/support/ui_kit/time_range_picker/dialog.py": (
        "converts the editable text to a QDateTime, read back"
    ),
    "src/modules/backtesting/ui/backtest_modals/backtest_time_range_source.py": (
        "seeds the picker's editable From/To text, parsed back by strptime"
    ),
    "src/modules/market_data/ui/data_management_widgets/shard_dialogs.py": (
        "an editable QDateTimeEdit's text, read back by strptime"
    ),
    "src/modules/trading/ui/desk/order_entry/amount_text.py": (
        "the order amount field's editable text, already rounded to the step"
    ),
    "src/modules/backtesting/ui/logic/report_export.py": "a file name's stamp",
    "src/modules/market_data/ui/logic/export_paths.py": "a file name's stamp",
    "src/support/charting/chart_card/cached_frame_interaction.py": (
        "frame and region summaries built for log lines"
    ),
    "src/support/charting/chart_card/squashed_price_band_report.py": (
        "a diagnostic report written to the log"
    ),
    "src/support/charting/chart_card/fps_meter.py": (
        "the developer FPS overlay, a diagnostic and not a figure"
    ),
}


def is_ui(rel: str) -> bool:
    if rel.startswith(_NOT_UI):
        return False
    return "/ui/" in rel or rel.startswith(_UI_PREFIXES)


def _in_logging_call(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    while node in parents:
        node = parents[node]
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _LOGGING_CALLS
        ):
            return True
    return False


def display_formatting(source: str) -> list[str]:
    """Each place in `source` that formats a number or a time itself."""
    tree = ast.parse(source)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FormattedValue) and node.format_spec is not None:
            spec = "".join(
                part.value
                for part in node.format_spec.values
                if isinstance(part, ast.Constant) and isinstance(part.value, str)
            )
            if _NUMERIC_SPEC.search(spec) and not _in_logging_call(node, parents):
                found.append(f"line {node.lineno}: format spec {spec!r}")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "strftime"
            and not _in_logging_call(node, parents)
        ):
            found.append(f"line {node.lineno}: strftime")
    return found


def _ui_sources() -> list[tuple[str, Path]]:
    if not _SRC_ROOT.is_dir():
        raise FileNotFoundError(f"{_SRC_ROOT} does not exist; retarget this guard")
    sources = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        rel = path.relative_to(_REPO_ROOT).as_posix()
        if "__pycache__" not in path.parts and is_ui(rel):
            sources.append((rel, path))
    return sources


def test_the_scan_has_a_subject() -> None:
    assert len(_ui_sources()) > 100, "the UI scan found almost nothing in src"


def test_no_ui_code_formats_a_number_or_a_time_itself() -> None:
    found = {
        rel: hits
        for rel, path in _ui_sources()
        if rel not in EXEMPT
        and (hits := display_formatting(path.read_text(encoding="utf-8")))
    }
    assert not found, (
        "write the value with AppValueFormatter / write_value "
        "(src/support/ui_kit/value_formatter.py), or, if it is not display "
        "text, exempt the file in EXEMPT with its reason:\n"
        + "\n".join(f"{rel}: {', '.join(hits)}" for rel, hits in sorted(found.items()))
    )


def test_every_exemption_names_a_ui_file_that_still_formats() -> None:
    """An exemption whose file moved, or no longer formats, is a free pass."""
    stale = [
        rel
        for rel in EXEMPT
        if not (_REPO_ROOT / rel).is_file()
        or not is_ui(rel)
        or not display_formatting((_REPO_ROOT / rel).read_text(encoding="utf-8"))
    ]
    assert not stale, f"drop or retarget these exemptions: {stale}"


def test_each_display_formatting_is_seen() -> None:
    source = (
        "a = f'{price:,.2f}'\nb = f'{pct:.1%}'\nc = f'{size:g}'\n"
        "d = f'{n:,}'\ne = moment.strftime('%H:%M')\nf = f'{when:%Y-%m-%d %H:%M}'\n"
    )
    assert len(display_formatting(source)) == 6


def test_a_log_line_and_plain_text_are_not_display_formatting() -> None:
    source = (
        "logger.info(f'took {ms:.1f} ms')\n"
        "self._log.debug(f'{a:.2f} {when.strftime(\"%H\")}')\n"
        "label = f'{name} {count}'\nwidth = f'{name:>10}'\n"
    )
    assert display_formatting(source) == []


def test_the_scope_is_ui_code_and_not_the_cli() -> None:
    assert is_ui("src/modules/bots/ui/bots_view.py")
    assert is_ui("src/support/charting/chart_card/marker_layer.py")
    assert not is_ui("src/modules/bots/application/bot_service.py")
    assert not is_ui("src/presentation/cli/order_preview_formatter.py")
