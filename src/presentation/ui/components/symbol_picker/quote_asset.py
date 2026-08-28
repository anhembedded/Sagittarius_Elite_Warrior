"""Splitting a Binance symbol into its base and quote asset.

A symbol arrives as one undivided string (`ETHUSDT`), but the picker needs the
two halves apart: to show `ETH` bold against a dimmed `USDT`, to say "Quote
USDT" under it, and to filter by quote. Binance's own `exchangeInfo` carries
`baseAsset`/`quoteAsset` per symbol, but the picker is handed a plain
`list[str]` (that is what `ListAvailableSymbolsQuery` returns), so the split is
derived from the text.

Derivation is a longest-suffix match against a declared list — not a guess.
The order matters and is the whole correctness question: `ETHUSDT` ends in both
`USDT` and `T`-nothing, and `ETHFDUSD` ends in both `FDUSD` and `USD`. Matching
the LONGEST known quote first is what keeps `ETHFDUSD` from reading as
base `ETHF` + quote `USD`.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Crypto quote assets Binance actually quotes spot pairs in.
CRYPTO_QUOTES: tuple[str, ...] = (
    "USDT",
    "USDC",
    "FDUSD",
    "TUSD",
    "BUSD",
    "DAI",
    "BTC",
    "ETH",
    "BNB",
    "XRP",
    "SOL",
    "DOGE",
    "TRX",
)

#: National currencies. Kept apart from `CRYPTO_QUOTES` because the picker
#: offers "FIAT" as one filter tab: a user looking for a fiat pair does not
#: care which of a dozen currencies it is, but a user looking for USDT very
#: much does.
FIAT_QUOTES: tuple[str, ...] = (
    "TRY",
    "EUR",
    "BRL",
    "ARS",
    "IDR",
    "JPY",
    "MXN",
    "PLN",
    "RON",
    "ZAR",
    "CZK",
    "UAH",
    "NGN",
    "COP",
    "AUD",
    "GBP",
    "RUB",
    "UAH",
)

#: Every known quote, longest first — the order the matcher depends on. Built
#: once here rather than sorted per call: this is read for every symbol in a
#: list that runs to ~1400 entries, on every keystroke in the search box.
_QUOTES_LONGEST_FIRST: tuple[str, ...] = tuple(
    sorted(set(CRYPTO_QUOTES) | set(FIAT_QUOTES), key=len, reverse=True)
)

_FIAT_SET = frozenset(FIAT_QUOTES)


@dataclass(frozen=True)
class SymbolParts:
    """One symbol seen as its two halves.

    `quote` is empty when no known quote matched — the symbol is still offered
    (a new listing must not vanish from the picker just because this module has
    not heard of its quote yet), it simply carries no quote label and answers
    no quote filter but "Tất cả".
    """

    symbol: str
    base: str
    quote: str

    @property
    def is_fiat(self) -> bool:
        return self.quote in _FIAT_SET

    @property
    def has_known_quote(self) -> bool:
        return bool(self.quote)


def split_symbol(symbol: str) -> SymbolParts:
    """Splits `symbol` at its longest known quote suffix.

    A symbol that is nothing BUT a quote (`USDT` alone, were the exchange ever
    to list it) keeps its whole text as the base and reports no quote: a base
    of `""` would render as an empty bold half and read as a rendering bug.
    """
    upper = symbol.upper()
    for quote in _QUOTES_LONGEST_FIRST:
        if upper.endswith(quote) and len(upper) > len(quote):
            return SymbolParts(symbol, upper[: -len(quote)], quote)
    return SymbolParts(symbol, upper, "")
