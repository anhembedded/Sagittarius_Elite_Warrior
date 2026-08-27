"""Declarative schema for the Backtest screen's Broker Properties fields
(BOT-104): one row per property, shared so it is declared exactly once.

BUG-064 — before this, "which broker properties exist" was declared
independently in three places that all had to be kept in sync by hand:
`StrategyConfigCoordinator._BROKER_PROPERTIES` (applying a saved payload to
the ViewModel), and two hardcoded blocks inside `StrategyPropertiesDialog`
(`save_and_rerun()` reading widgets into a payload, `_sync_properties()`
writing the ViewModel back into widgets). A property added to one and
forgotten in another would silently never save, or never show its current
value — exactly the class of bug this module closes off, by making "key ->
ViewModel attribute (+ coercion)" a single, importable source of truth.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BrokerPropertyField:
    """One broker property: the payload dict key both the dialog and the
    coordinator agree on, the `BackTestViewModel` attribute it lives in, and
    how to coerce a raw payload value into that attribute's type."""

    key: str
    vm_attribute: str
    coerce: Callable[[Any], Any]


#: Order is cosmetic (matches the dialog's own field order) — lookups are by
#: `key`, never by position.
BROKER_PROPERTY_FIELDS: tuple[BrokerPropertyField, ...] = (
    BrokerPropertyField("initial_capital", "initialCapitalText", str),
    BrokerPropertyField("currency", "selectedCurrency", str),
    BrokerPropertyField("order_size_type", "orderSizeType", str),
    BrokerPropertyField("order_size_text", "orderSizeText", str),
    BrokerPropertyField("pyramiding", "pyramiding", int),
    BrokerPropertyField("commission_type", "commissionType", str),
    BrokerPropertyField("commission_text", "commissionText", str),
    BrokerPropertyField("slippage_ticks", "slippageTicks", int),
    BrokerPropertyField("long_leverage", "longLeverage", float),
    BrokerPropertyField("short_leverage", "shortLeverage", float),
    BrokerPropertyField("take_profit_enabled", "takeProfitPctEnabled", bool),
    BrokerPropertyField("take_profit_pct_text", "takeProfitPctText", str),
)
