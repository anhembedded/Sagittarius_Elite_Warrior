"""When two templates fit a line equally well and disagree, nothing is claimed (`BOT-199`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.log_view.template_extractor import (
    percent_template,
)
from Sagittarius_Elite_Warrior.src.support.log_view.template_matcher import (
    TemplateMatcher,
)


def test_one_template_gives_the_span_of_each_value() -> None:
    matcher = TemplateMatcher((percent_template("Bot %s: opened at %s"),))

    assert matcher.values_in("Bot ab12cd: opened at 5") == ((4, 10), (22, 23))


def test_two_equal_templates_that_disagree_claim_nothing() -> None:
    first = percent_template("ab %s cd %s")
    second = percent_template("ab %s %s cd")
    # Four fixed characters each; "ab X cd Y cd" fits both, with different holes.
    matcher = TemplateMatcher((first, second))

    assert matcher.values_in("ab X cd Y cd") is None


def test_two_equal_templates_that_agree_on_the_values_still_claim_them() -> None:
    one = percent_template("Bot %s: stopped")
    same = percent_template("Bot %s: stopped")
    matcher = TemplateMatcher((one, same))

    assert matcher.values_in("Bot ab12cd: stopped") == ((4, 10),)


def test_the_template_with_more_fixed_text_wins() -> None:
    generic = percent_template("%s: stopped now")
    specific = percent_template("Bot %s: stopped now")
    matcher = TemplateMatcher((generic, specific))

    assert matcher.values_in("Bot ab12cd: stopped now") == ((4, 10),)


def test_no_template_means_none() -> None:
    assert TemplateMatcher(()).values_in("anything at all") is None
