"""The shipped template catalogue is what the source says it is (`BOT-199`, `PRO-019` option C).

A new log call changes the generated text; `python3 scripts/render_log_templates.py
--write` brings the file up to date, and this test fails until it does."""

from __future__ import annotations

import ast
from pathlib import Path

from Sagittarius_Elite_Warrior.src.support.log_view.template_catalogue_file import (
    CATALOGUE_PATH,
    catalogue_text,
    parse_catalogue_text,
)
from Sagittarius_Elite_Warrior.src.support.log_view.template_extractor import (
    _templates_of,
    extract_catalogue,
    fstring_template,
    percent_template,
)
from Sagittarius_Elite_Warrior.src.support.log_view.template_matcher import (
    TemplateMatcher,
)

_SRC = Path(__file__).resolve().parents[4] / "src"
#: Calls whose message is a variable: the viewer guesses their params. It only falls.
_VARIABLE_TEMPLATE_CALLS_CEILING = 33
#: Templates two lines of the catalogue cannot tell apart. It only falls.
_AMBIGUOUS_TEMPLATES_CEILING = 1
#: Log calls the extractor leaves out as too generic to match a line. It only falls (`BOT-230`: the
#: committed file used to show a change in this count; it no longer carries it).
_TOO_GENERIC_TEMPLATES_CEILING = 1
_FILL = {"s": "SENT{}", "d": "{}", "f": "{}.5", "x": "ff{}", "h": "HOLE{}"}


def test_the_committed_catalogue_is_what_the_source_generates() -> None:
    assert CATALOGUE_PATH.read_text(encoding="utf-8") == catalogue_text(
        extract_catalogue(_SRC)
    ), "run: python3 scripts/render_log_templates.py --write"


def test_the_catalogue_file_parses_back_to_the_same_templates() -> None:
    generated = extract_catalogue(_SRC)

    assert parse_catalogue_text(catalogue_text(generated)) == generated.templates


def test_the_header_holds_nothing_that_changes_with_the_templates() -> None:
    """`BOT-230`: a count in the header made every pull request that adds a log call conflict
    with every other on the same line."""
    header = CATALOGUE_PATH.read_text(encoding="utf-8").splitlines()[1]

    assert header == '{"schema": "sew.log-templates/1"},'


def test_log_calls_with_a_variable_message_only_fall() -> None:
    assert (
        extract_catalogue(_SRC).variable_template_calls
        <= _VARIABLE_TEMPLATE_CALLS_CEILING
    )


def test_templates_left_out_as_too_generic_only_fall() -> None:
    assert (
        extract_catalogue(_SRC).too_generic_templates <= _TOO_GENERIC_TEMPLATES_CEILING
    )


def test_a_percent_template_splits_into_fixed_text_and_typed_holes() -> None:
    template = percent_template("Bot %s: 100%% of %d at %.2f (%r)")

    assert template.pieces == ("Bot ", ": 100% of ", " at ", " (", ")")
    assert template.kinds == ("s", "d", "f", "s")


def test_an_f_string_splits_into_fixed_text_and_holes() -> None:
    node = ast.parse('f"{tag} {who} detail:\\n{text}"', mode="eval").body
    assert isinstance(node, ast.JoinedStr)

    template = fstring_template(node)

    assert template.pieces == ("", " ", " detail:\n", "")
    assert template.kinds == ("h", "h", "h")


def test_every_template_finds_its_own_params_exactly() -> None:
    templates = extract_catalogue(_SRC).templates
    matcher = TemplateMatcher(templates)
    unclear = 0
    for template in templates:
        if "\n" in "".join(template.pieces) or "" in template.pieces[1:-1]:
            continue  # a newline is read line by line; two holes side by side cannot be split
        message, expected = template.pieces[0], []
        for position, kind in enumerate(template.kinds):
            value = _FILL[kind].format(7 + position)
            expected.append((len(message), len(message) + len(value)))
            message += value + template.pieces[position + 1]
        if matcher.values_in(message) != tuple(expected):
            unclear += 1

    assert unclear <= _AMBIGUOUS_TEMPLATES_CEILING


def test_a_log_call_with_a_level_argument_and_a_receiver_ending_in_log_is_read() -> (
    None
):
    source = (
        "import logging\n"
        "_decision_log = logging.getLogger('App.X')\n"
        "def f(level, bot):\n"
        "    _decision_log.info('[x-tag] Bot %s: first', bot)\n"
        "    logger.log(level, 'Bot %s: second', bot)\n"
        "    self.info('a pane message, not a record')\n"
    )
    found = {t.pieces for t in _templates_of(ast.parse(source)) if t is not None}

    assert found == {("[x-tag] Bot ", ": first"), ("Bot ", ": second")}
