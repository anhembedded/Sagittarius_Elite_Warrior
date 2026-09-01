from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)


def test_trading_venue_enum_values():
    assert TradingVenue.DISABLED == "disabled"
    assert TradingVenue.FUTURES_TESTNET == "futures_testnet"


def test_trading_venue_has_no_mainnet_member():
    """`EPIC-021`'s ADR §3: real-money trading is not a config flip — it is
    a future epic that has to add a new enum member here. Locks that safety
    claim as a type-level fact, not just a docstring (`architecture-rule.md`
    §7). Checks by member *name*, not by value, so a future member spelled
    differently (`"live"`, `"real"`) can't reintroduce the same hazard under
    a different label without this test forcing a deliberate look."""
    member_names = {member.name for member in TradingVenue}
    forbidden = {name for name in member_names if "MAINNET" in name or "LIVE" in name}
    assert forbidden == set()
