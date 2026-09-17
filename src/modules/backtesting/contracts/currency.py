from enum import Enum


class Currency(str, Enum):
    """
    @brief Domain Value Object representing supported trading capital currencies.
    @details Adding new enum members automatically exposes them across the UI
    and application layer without hardcoded list changes (Open/Closed Principle).
    """

    USD = "USD"
    VND = "VND"
    USDT = "USDT"

    @classmethod
    def list_values(cls) -> list[str]:
        """Returns a list of all string values declared on the enum."""
        return [item.value for item in cls]
