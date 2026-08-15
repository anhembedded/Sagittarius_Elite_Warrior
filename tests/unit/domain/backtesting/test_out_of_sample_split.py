"""Tests for split_klines_for_out_of_sample (BOT-080)."""

from Sagittarius_Elite_Warrior.src.domain.backtesting.out_of_sample_split import (
    DEFAULT_IN_SAMPLE_RATIO,
    split_klines_for_out_of_sample,
)


def test_default_ratio_is_70_30():
    assert DEFAULT_IN_SAMPLE_RATIO == 0.7


def test_splits_a_list_of_ten_into_seven_and_three():
    klines = list(range(10))

    in_sample, out_of_sample = split_klines_for_out_of_sample(klines)

    assert in_sample == [0, 1, 2, 3, 4, 5, 6]
    assert out_of_sample == [7, 8, 9]


def test_preserves_chronological_order_within_each_half():
    klines = list(range(10))

    in_sample, out_of_sample = split_klines_for_out_of_sample(klines)

    assert in_sample + out_of_sample == klines


def test_a_custom_ratio_is_honored():
    klines = list(range(10))

    in_sample, out_of_sample = split_klines_for_out_of_sample(
        klines, in_sample_ratio=0.5
    )

    assert len(in_sample) == 5
    assert len(out_of_sample) == 5


def test_empty_input_produces_two_empty_lists():
    in_sample, out_of_sample = split_klines_for_out_of_sample([])

    assert in_sample == []
    assert out_of_sample == []


def test_a_single_element_all_goes_to_in_sample_leaving_out_of_sample_empty():
    in_sample, out_of_sample = split_klines_for_out_of_sample([1])

    assert in_sample == [1]
    assert out_of_sample == []
