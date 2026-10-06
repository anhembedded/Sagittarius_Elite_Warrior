"""`BOT-149` — a capped every-pair page reads the user's own pairs first."""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.trading.application.history_scope import (
    history_scope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.contract_account_history_reader import (
    CONTRACT_NOW,
    contract_trade,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_history_reader import (
    FakeAccountHistoryReader,
)

_SINCE = CONTRACT_NOW - timedelta(days=7)
_HELD = [f"{name}USDT" for name in ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG")]


def _reader(**kwargs: object) -> FakeAccountHistoryReader:
    return FakeAccountHistoryReader(now=CONTRACT_NOW, scan_limit=3, **kwargs)  # type: ignore[arg-type]


def test_a_capped_page_reads_the_open_order_pair_not_the_alphabet_first() -> None:
    """The Spot Testnet account holds hundreds of assets: the pair with an
    open order sorts last and used to be the one left out."""
    reader = _reader(held_symbols=_HELD, open_symbols=["ZZZUSDT"])

    scope = history_scope(reader, None, _SINCE)

    assert scope.symbols == ("ZZZUSDT", "AAAUSDT", "BBBUSDT")
    assert "3 of 8 active pairs" in scope.notices[0]


def test_the_order_is_open_orders_then_the_desk_pair_then_traded_then_held() -> None:
    reader = _reader(
        held_symbols=_HELD,
        open_symbols=["YYYUSDT", "ZZZUSDT"],
        trades=[contract_trade("TTTUSDT", 10)],
    )

    desk = history_scope(reader, None, _SINCE, "GGGUSDT")
    no_desk = history_scope(reader, None, _SINCE)

    assert desk.symbols == ("YYYUSDT", "ZZZUSDT", "GGGUSDT")
    assert no_desk.symbols == ("YYYUSDT", "ZZZUSDT", "TTTUSDT")


def test_a_desk_pair_with_an_open_order_is_not_read_twice() -> None:
    reader = _reader(held_symbols=_HELD, open_symbols=["ZZZUSDT"])

    scope = history_scope(reader, None, _SINCE, "ZZZUSDT")

    assert scope.symbols == ("ZZZUSDT", "AAAUSDT", "BBBUSDT")


def test_a_desk_pair_that_is_not_active_is_not_added() -> None:
    reader = _reader(held_symbols=_HELD)

    scope = history_scope(reader, None, _SINCE, "NOPEUSDT")

    assert scope.symbols == ("AAAUSDT", "BBBUSDT", "CCCUSDT")


def test_a_page_within_the_cap_keeps_symbol_order_and_has_no_notice() -> None:
    reader = FakeAccountHistoryReader(
        held_symbols=["BBBUSDT"],
        open_symbols=["ZZZUSDT"],
        now=CONTRACT_NOW,
        scan_limit=3,
    )

    scope = history_scope(reader, None, _SINCE)

    assert (scope.symbols, scope.notices) == (("BBBUSDT", "ZZZUSDT"), ())


def test_an_uncapped_reader_keeps_symbol_order() -> None:
    reader = FakeAccountHistoryReader(
        held_symbols=_HELD, open_symbols=["ZZZUSDT"], now=CONTRACT_NOW
    )

    scope = history_scope(reader, None, _SINCE)

    assert scope.symbols == tuple(sorted(_HELD + ["ZZZUSDT"]))
    assert scope.notices == ()


def test_a_named_symbol_is_read_alone() -> None:
    reader = _reader(held_symbols=_HELD, open_symbols=["ZZZUSDT"])

    assert history_scope(reader, "BBBUSDT", _SINCE, "AAAUSDT").symbols == ("BBBUSDT",)


def test_exactly_the_limit_of_pairs_is_read_in_symbol_order_without_a_notice() -> None:
    reader = _reader(held_symbols=["AAAUSDT", "BBBUSDT"], open_symbols=["ZZZUSDT"])

    scope = history_scope(reader, None, _SINCE)

    assert (scope.symbols, scope.notices) == (("AAAUSDT", "BBBUSDT", "ZZZUSDT"), ())


def test_one_pair_over_the_limit_ranks_and_says_one_was_left_out() -> None:
    reader = _reader(
        held_symbols=["AAAUSDT", "BBBUSDT", "CCCUSDT"], open_symbols=["ZZZUSDT"]
    )

    scope = history_scope(reader, None, _SINCE)

    assert scope.symbols == ("ZZZUSDT", "AAAUSDT", "BBBUSDT")
    assert "3 of 4 active pairs" in scope.notices[0]


def test_a_pair_held_and_with_an_open_order_ranks_as_an_open_order() -> None:
    reader = _reader(held_symbols=_HELD + ["ZZZUSDT"], open_symbols=["ZZZUSDT"])

    assert history_scope(reader, None, _SINCE).symbols[0] == "ZZZUSDT"
