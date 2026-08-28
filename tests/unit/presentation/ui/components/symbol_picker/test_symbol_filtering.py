"""Tests for the symbol picker's pure logic — no Qt, no event loop."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker.filtering import (
    QUOTE_ANY,
    QUOTE_FIAT,
    FilterState,
    Scope,
    apply_filter,
    available_quotes,
    build_entries,
    partition_favourites,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker.quote_asset import (
    split_symbol,
)

_LISTED = [
    "BTCUSDT",
    "ETHUSDT",
    "ETHBTC",
    "ETHFDUSD",
    "ETHEUR",
    "ETHTRY",
    "AAVEETH",
    "BNBETH",
]


def _entries(current: str = "ETHUSDT", favourites=(), recents=()):
    return build_entries(
        _LISTED, favourites=favourites, recents=recents, current=current
    )


# --------------------------------------------------------------------- #
# Splitting
# --------------------------------------------------------------------- #


def test_splits_a_symbol_at_its_quote():
    parts = split_symbol("ETHUSDT")
    assert (parts.base, parts.quote) == ("ETH", "USDT")


def test_longest_quote_wins_so_fdusd_does_not_read_as_usd():
    """The whole reason the match is longest-first: ETHFDUSD ends in both
    FDUSD and USD, and the short match would invent a coin called ETHF."""
    parts = split_symbol("ETHFDUSD")
    assert (parts.base, parts.quote) == ("ETH", "FDUSD")


def test_a_coin_quoted_in_another_coin_splits_too():
    assert split_symbol("AAVEETH").quote == "ETH"
    assert split_symbol("ETHBTC").quote == "BTC"


def test_fiat_quotes_are_flagged_as_fiat():
    assert split_symbol("ETHTRY").is_fiat is True
    assert split_symbol("ETHUSDT").is_fiat is False


def test_an_unknown_quote_keeps_the_symbol_whole_rather_than_hiding_it():
    """A newly listed quote this module has not heard of must not make the
    symbol unrenderable — it just carries no quote label."""
    parts = split_symbol("NEWCOINXYZQ")
    assert parts.base == "NEWCOINXYZQ"
    assert parts.quote == ""
    assert parts.has_known_quote is False


def test_a_symbol_that_is_only_a_quote_keeps_a_non_empty_base():
    """Splitting "USDT" into base "" + quote "USDT" would render an empty
    bold half and read as a bug."""
    parts = split_symbol("USDT")
    assert parts.base == "USDT"
    assert parts.quote == ""


# --------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------- #


def test_no_filter_shows_everything_in_the_order_given():
    entries = _entries()
    assert [e.symbol for e in apply_filter(entries, FilterState())] == _LISTED


def test_search_matches_anywhere_in_the_symbol_not_just_the_base():
    """Typing a quote to see every pair in it is as common as typing a coin."""
    entries = _entries()
    found = apply_filter(entries, FilterState(query="usdt"))
    assert [e.symbol for e in found] == ["BTCUSDT", "ETHUSDT"]

    found = apply_filter(entries, FilterState(query="eth"))
    assert "AAVEETH" in [e.symbol for e in found]
    assert "ETHBTC" in [e.symbol for e in found]


def test_quote_tab_narrows_to_one_quote():
    entries = _entries()
    found = apply_filter(entries, FilterState(quote="ETH"))
    assert [e.symbol for e in found] == ["AAVEETH", "BNBETH"]


def test_the_fiat_tab_covers_every_national_currency_at_once():
    entries = _entries()
    found = apply_filter(entries, FilterState(quote=QUOTE_FIAT))
    assert sorted(e.symbol for e in found) == ["ETHEUR", "ETHTRY"]


def test_scope_favourites_shows_only_starred_symbols():
    entries = _entries(favourites=["ETHBTC", "ETHUSDT"])
    found = apply_filter(entries, FilterState(scope=Scope.FAVOURITES))
    assert sorted(e.symbol for e in found) == ["ETHBTC", "ETHUSDT"]


def test_scope_recent_shows_only_recently_used_symbols():
    entries = _entries(recents=["ETHFDUSD"])
    found = apply_filter(entries, FilterState(scope=Scope.RECENT))
    assert [e.symbol for e in found] == ["ETHFDUSD"]


def test_filters_combine_with_and_not_or():
    entries = _entries(favourites=["ETHBTC", "ETHUSDT"])
    found = apply_filter(
        entries, FilterState(query="eth", scope=Scope.FAVOURITES, quote="BTC")
    )
    assert [e.symbol for e in found] == ["ETHBTC"]


def test_history_matching_ignores_case():
    """A value remembered from an older run, or typed into Dev Board's
    editable combo, still has to match the exchange's own casing."""
    entries = _entries(favourites=["ethusdt"], recents=["EthBtc"])
    by_symbol = {e.symbol: e for e in entries}
    assert by_symbol["ETHUSDT"].is_favourite is True
    assert by_symbol["ETHBTC"].is_recent is True


def test_the_current_symbol_is_marked():
    entries = _entries(current="ethbtc")
    assert [e.symbol for e in entries if e.is_current] == ["ETHBTC"]


# --------------------------------------------------------------------- #
# Sections and tabs
# --------------------------------------------------------------------- #


def test_favourites_are_partitioned_out_of_the_filtered_list():
    entries = _entries(favourites=["ETHBTC", "ETHUSDT"])
    favourites, rest = partition_favourites(apply_filter(entries, FilterState()))

    assert sorted(e.symbol for e in favourites) == ["ETHBTC", "ETHUSDT"]
    assert "ETHBTC" not in [e.symbol for e in rest], "must not appear twice"


def test_a_favourite_that_does_not_match_the_search_stays_hidden():
    """Pinning favourites above the results must not defeat searching."""
    entries = _entries(favourites=["ETHBTC"])
    favourites, _ = partition_favourites(
        apply_filter(entries, FilterState(query="aave"))
    )
    assert favourites == []


def test_quote_tabs_offer_only_quotes_that_actually_have_symbols():
    """A tab that yields nothing is worse than a missing tab."""
    quotes = available_quotes(_entries())
    assert "USDT" in quotes
    assert "ETH" in quotes
    assert QUOTE_FIAT in quotes
    assert "BNB" not in quotes, "nothing listed is quoted in BNB here"
    assert QUOTE_ANY not in quotes, "the 'all' tab is not a quote"


def test_quote_tabs_are_ranked_by_how_many_symbols_they_cover():
    """The tabs a user reaches for should sit leftmost."""
    quotes = available_quotes(_entries())
    assert quotes.index("USDT") < quotes.index("BTC")
    assert quotes[-1] == QUOTE_FIAT, "fiat is a catch-all, so it goes last"
