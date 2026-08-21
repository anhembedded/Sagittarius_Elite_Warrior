"""Tests for split_klines_for_out_of_sample (BOT-080) and its count-only
counterpart split_count_for_out_of_sample (BUG-025)."""

from Sagittarius_Elite_Warrior.src.domain.backtesting.out_of_sample_split import (
    DEFAULT_IN_SAMPLE_RATIO,
    split_count_for_out_of_sample,
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


# ---------------------------------------------------------------------------
# split_count_for_out_of_sample (BUG-025) — must agree with the list-based
# split on every count, since the streaming Backtest data path uses this to
# compute offset/limit *before* fetching anything.
# ---------------------------------------------------------------------------


def test_count_split_of_ten_matches_the_list_based_split():
    assert split_count_for_out_of_sample(10) == (7, 3)


def test_count_split_honors_a_custom_ratio():
    assert split_count_for_out_of_sample(10, in_sample_ratio=0.5) == (5, 5)


def test_count_split_of_zero_is_two_zeros():
    assert split_count_for_out_of_sample(0) == (0, 0)


def test_count_split_of_one_leaves_out_of_sample_empty():
    assert split_count_for_out_of_sample(1) == (1, 0)


def test_count_split_agrees_with_list_split_across_many_totals():
    for total in range(50):
        klines = list(range(total))
        expected_in_sample, expected_out_of_sample = split_klines_for_out_of_sample(
            klines
        )

        in_sample_count, out_of_sample_count = split_count_for_out_of_sample(total)

        assert in_sample_count == len(expected_in_sample)
        assert out_of_sample_count == len(expected_out_of_sample)
