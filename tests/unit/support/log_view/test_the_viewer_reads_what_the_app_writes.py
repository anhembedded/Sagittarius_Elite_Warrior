"""The viewer parses the bytes the application's own formatter writes (`BOT-199`, `PRO-019`).

The format string is read from the configuration the app ships and from the one the
quiet-command routing builds, so the viewer's pattern cannot drift from either unseen."""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path

from Sagittarius_Elite_Warrior.src.shell.cli_log_routing import _LOG_FORMAT
from Sagittarius_Elite_Warrior.src.support.log_view.log_line import parse_head
from Sagittarius_Elite_Warrior.src.support.log_view.message_spans import message_spans
from Sagittarius_Elite_Warrior.src.support.log_view.param_span import SpanRole
from Sagittarius_Elite_Warrior.src.support.log_view.template_catalogue_file import (
    load_templates,
)
from Sagittarius_Elite_Warrior.src.support.log_view.template_matcher import (
    TemplateMatcher,
)

_CONFIG = Path(__file__).resolve().parents[4] / "src" / "config" / "app_config.json"


def _configured_format() -> str:
    return str(json.loads(_CONFIG.read_text(encoding="utf-8"))["LOG_FORMAT"])


def _written_by(fmt: str, logger_name: str, message: str, *args: object) -> str:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(fmt))
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        logger.info(message, *args)
    finally:
        logger.removeHandler(handler)
    return stream.getvalue().rstrip("\n")


def test_both_formats_in_the_app_are_the_one_the_viewer_reads() -> None:
    assert _configured_format() == _LOG_FORMAT


def test_a_line_the_real_formatter_wrote_parses_back_to_its_fields() -> None:
    line = _written_by(
        _LOG_FORMAT,
        "App.Bots.GridExit",
        "Bot %s: exit slice %d of %s",
        "uie03d",
        2,
        "5",
    )

    head = parse_head(line)

    assert head is not None
    assert (head.logger, head.level) == ("App.Bots.GridExit", "INFO")
    assert head.message == "Bot uie03d: exit slice 2 of 5"
    assert head.moment() is not None


def test_the_params_of_a_real_call_are_found_exactly_from_its_template() -> None:
    line = _written_by(
        _LOG_FORMAT,
        "App.Bots.GridExit",
        "Bot %s: exit slice %d of %s -> %s %s",
        "uie03d",
        2,
        "5",
        "SELL",
        "BTCUSDT",
    )
    head = parse_head(line)
    assert head is not None

    spans = message_spans(head.message, TemplateMatcher(load_templates()))

    assert [(s.role, head.message[s.start : s.end]) for s in spans] == [
        (SpanRole.PARAM, "uie03d"),
        (SpanRole.PARAM, "2"),
        (SpanRole.PARAM, "5"),
        (SpanRole.PARAM, "SELL"),
        (SpanRole.PARAM, "BTCUSDT"),
    ]
