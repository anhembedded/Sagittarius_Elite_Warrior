from Sagittarius_Elite_Warrior.src.domain.value_objects.currency import Currency


def test_currency_enum_values():
    assert Currency.USD == "USD"
    assert Currency.VND == "VND"
    assert Currency.USDT == "USDT"


def test_currency_list_values():
    values = Currency.list_values()
    assert values == ["USD", "VND", "USDT"]
