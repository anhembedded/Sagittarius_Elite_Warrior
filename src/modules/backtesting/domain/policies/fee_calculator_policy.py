from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.commission_type import (
    CommissionType,
)


class FeeCalculatorPolicy:
    """
    @brief Domain policy for commission and transaction fee calculations.
    @details Supports Percentage of Notional, Fixed Cash per Order, and Fixed Cash per Contract.
    """

    def calculate_entry_fee_and_quantity(
        self,
        notional_capital: float,
        effective_price: float,
        commission_type: CommissionType,
        commission_value: float,
    ) -> tuple[float, float]:
        """
        @brief Calculates (entry_fee, quantity) for opening a position.
        @return tuple of (entry_fee, quantity). If net notional or quantity is non-positive, returns (0.0, 0.0).
        """
        if notional_capital <= 0 or effective_price <= 0:
            return 0.0, 0.0

        if commission_type is CommissionType.PERCENT:
            entry_fee = notional_capital * (commission_value / 100.0)
            net_notional = notional_capital - entry_fee
            if net_notional <= 0:
                return 0.0, 0.0
            quantity = net_notional / effective_price
        elif commission_type is CommissionType.CASH_PER_ORDER:
            entry_fee = commission_value
            net_notional = notional_capital - entry_fee
            if net_notional <= 0:
                return 0.0, 0.0
            quantity = net_notional / effective_price
        elif commission_type is CommissionType.CASH_PER_CONTRACT:
            quantity = notional_capital / (effective_price + commission_value)
            if quantity <= 0:
                return 0.0, 0.0
            entry_fee = quantity * commission_value
        else:
            entry_fee = 0.0
            quantity = notional_capital / effective_price

        return entry_fee, quantity

    def entry_fee_for_quantity(
        self,
        quantity: float,
        effective_price: float,
        commission_type: CommissionType,
        commission_value: float,
    ) -> float:
        """
        @brief The entry fee of a position of exactly `quantity` (`EPIC-027C`).
        @details The inverse of `calculate_entry_fee_and_quantity()`: once an
        exchange filter floors the quantity it sized, the fee is that of the
        smaller order. Every model keeps `notional_capital == quantity *
        effective_price + entry_fee`, so the capital an entry commits follows
        from this fee.
        """
        if commission_type is CommissionType.PERCENT:
            rate = commission_value / 100.0
            return quantity * effective_price * rate / (1.0 - rate)
        if commission_type is CommissionType.CASH_PER_ORDER:
            return commission_value
        if commission_type is CommissionType.CASH_PER_CONTRACT:
            return quantity * commission_value
        return 0.0

    def calculate_exit_fee(
        self,
        quantity: float,
        exit_price: float,
        commission_type: CommissionType,
        commission_value: float,
    ) -> float:
        """
        @brief Calculates exit fee upon realizing a position.
        """
        if quantity <= 0 or exit_price <= 0:
            return 0.0

        notional = quantity * exit_price
        if commission_type is CommissionType.PERCENT:
            return notional * (commission_value / 100.0)
        elif commission_type is CommissionType.CASH_PER_ORDER:
            return commission_value
        elif commission_type is CommissionType.CASH_PER_CONTRACT:
            return quantity * commission_value
        return 0.0
