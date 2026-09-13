"""A `BacktestResult` as plain JSON-ready data, in a stable shape.

Floats are written with `repr` and compared exactly: the arithmetic is pure
Python over the same inputs, so any difference is a behaviour change, not
noise. Datetimes become ISO strings, enums their value, mappings sort by key.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)


def serialise(result: BacktestResult) -> dict[str, Any]:
    return _plain(result)


def _plain(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, float):
        return repr(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {
            str(k): _plain(v)
            for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value
