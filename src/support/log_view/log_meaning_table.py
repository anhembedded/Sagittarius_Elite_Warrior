"""The one table of what each part of a log line means, and the style it gets.

The same shape as `src/shell/rich_text_report_renderer.py`: names to styles in one
place, nothing coloured anywhere else. Sixteen named colours only, never a
background, never "bright black" or blue for text (a terminal draws these in its own
palette and some themes make them unreadable): the timestamp is `dim`, which follows
the terminal's own foreground. A word or tag is always printed too; colour is never the
only signal (WCAG 2.1 SC 1.4.1, `PRO-019` §2).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.log_view.param_span import SpanRole

TIMESTAMP_STYLE = "dim"
SEPARATOR_STYLE = "dim"
LOGGER_STYLE = "cyan"
#: The substituted values: the loudest colour besides the level (the owner's request).
PARAM_STYLE = "bold green"
#: A guess, when no template fits the line: the same hue, not bold, so it reads as less sure.
GUESS_STYLE = "green"
TAG_STYLE = "magenta"
TRACEBACK_STYLE = "dim red"

_LEVEL_STYLES = {
    "CRITICAL": "bold red",
    "ERROR": "red",
    "WARNING": "yellow",
    "INFO": "",
    "DEBUG": "dim",
    "TRACE": "dim",
}
#: The text of the message that is not a param or a tag, by level (journalctl's ladder).
_MESSAGE_STYLES = {"CRITICAL": "bold red", "ERROR": "red", "WARNING": "yellow"}
_SPAN_STYLES = {
    SpanRole.PARAM: PARAM_STYLE,
    SpanRole.GUESS: GUESS_STYLE,
    SpanRole.TAG: TAG_STYLE,
}


def level_style(level: str) -> str:
    return _LEVEL_STYLES.get(level.upper(), "")


def message_style(level: str) -> str:
    return _MESSAGE_STYLES.get(level.upper(), "")


def span_style(role: SpanRole) -> str:
    return _SPAN_STYLES[role]
