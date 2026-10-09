"""`EPIC-035U` — a catalog fetch that failed in transit is told apart from a symbol that is not listed.

Both are `SymbolRulesUnavailableError`, which a caller may read as a delisting; the
transit failure is the subclass `SymbolCatalogUnreachableError`, so a running bot
can halt for the one and not for the other.
"""

from __future__ import annotations

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.metadata_reads import (
    catalog_read_failures,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_catalog_unreachable_error import (
    SymbolCatalogUnreachableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)


def test_a_network_failure_is_an_unreachable_catalog_and_still_a_rules_error() -> None:
    with (
        pytest.raises(SymbolCatalogUnreachableError) as caught,
        catalog_read_failures("Spot symbol rules"),
    ):
        raise RequestsConnectionError("connection reset")

    assert isinstance(caught.value, SymbolRulesUnavailableError)
    assert "could not be read" in str(caught.value)
    assert isinstance(caught.value.__cause__, RequestsConnectionError)
