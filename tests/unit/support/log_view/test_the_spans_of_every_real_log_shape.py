"""Which words of each real shape of line are params, tags or guesses (`BOT-199`).

A line a template fits has its params exact; any other line is guessed and says so
(`GUESS`), so the screen never shows a guess as certain."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.log_view.log_line import parse_head
from Sagittarius_Elite_Warrior.src.support.log_view.message_spans import message_spans
from Sagittarius_Elite_Warrior.src.support.log_view.template_catalogue_file import (
    load_templates,
)
from Sagittarius_Elite_Warrior.src.support.log_view.template_matcher import (
    TemplateMatcher,
)
from Sagittarius_Elite_Warrior.tests.unit.support.log_view import (
    log_view_samples as samples,
)

_MATCHER = TemplateMatcher(load_templates())


def _spans(line: str) -> list[tuple[str, str]]:
    head = parse_head(line)
    assert head is not None
    return [
        (span.role.value, head.message[span.start : span.end])
        for span in message_spans(head.message, _MATCHER)
    ]


def test_the_values_a_call_substituted_are_params_and_the_fixed_text_is_not() -> None:
    assert _spans(samples.EXIT_SLICE) == [
        ("param", "uie03d"),
        ("param", "2"),
        ("param", "5"),
        ("param", "SELL"),
        ("param", "BTCUSDT"),
    ]


def test_a_tag_is_a_tag_and_the_free_text_after_it_is_a_param() -> None:
    assert _spans(samples.BOOT_RECOVERY) == [
        ("param", "uie03d"),
        ("tag", "[boot-recovery]"),
        ("param", "no snapshot"),
    ]


def test_a_trailing_tag_is_found_too() -> None:
    spans = _spans(samples.TRAILING_TAG)

    assert spans[0] == ("param", "uie03d")
    assert spans[-1] == ("tag", "[halt-closes-position]")


def test_a_message_with_no_params_has_only_its_tag() -> None:
    assert _spans(samples.ERROR_HEAD) == [("tag", "[cli-exit]")]


def test_a_line_with_no_template_is_guessed_and_marked_as_a_guess() -> None:
    line = (
        "2026-10-20 02:00:07,000 - App.X - INFO - [no-such-call] widgets=4 bot ab12cd"
    )

    spans = _spans(line)

    assert ("tag", "[no-such-call]") in spans
    assert ("guess", "4") in spans
    assert all(role in {"tag", "guess"} for role, _ in spans)


def test_the_health_line_values_are_guessed_whole_so_a_list_is_one_value() -> None:
    spans = {text: role for role, text in _spans(samples.HEALTH)}

    assert spans["[health]"] == "tag"
    assert spans["SERVING"] == "guess"
    assert (
        spans[
            "running:3,paused:1,halted:0,recovering:0,error:0,starting:0,stopping:0,awaiting_recovery:0"
        ]
        == "guess"
    )
    assert spans["-120"] == "guess"


def test_every_span_lies_inside_the_message_and_none_overlap() -> None:
    for line in (
        samples.EXIT_SLICE,
        samples.HEALTH,
        samples.REDUCE_ONLY,
        samples.UNTAGGED,
    ):
        head = parse_head(line)
        assert head is not None
        spans = message_spans(head.message, _MATCHER)
        edges = [(s.start, s.end) for s in spans]
        assert edges == sorted(edges)
        assert all(0 <= a < b <= len(head.message) for a, b in edges)
        assert all(edges[i][1] <= edges[i + 1][0] for i in range(len(edges) - 1))
