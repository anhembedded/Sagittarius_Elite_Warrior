"""`EPIC-010H` — the one place a screen asks "what symbol/interval do I start on?"

@par The problem this replaces
The same concept had several independent copies: `"ETHUSDT"` as a literal in
three modules, `"1m"` in four or more, each with a comment pointing at another
file it was supposed to match. Worse than the duplication, only
`BackTestPresenter` ever read `DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL` from config
— the Dev Board and Database screens ignored them outright. So editing those
values in Settings changed one screen out of three, silently, with nothing to
tell the user the other two were not listening.

Adding a remembered-value tier on top of that foundation is what forced the
issue: `EPIC-010H` defines

    ui_state  >  user_config DEFAULT_*  >  module constants

and the middle tier cannot mean anything on a screen that never consults it.

@par What is shared is the config reading, not the floor
Each function takes the caller's own `fallback`. That is deliberate, and a
correction: an earlier draft of this module owned one global fallback for every
screen, which silently changed the Database screen's starting symbol from
`BTCUSDT` to `ETHUSDT` and its interval from `1s` to `1m`. Its own tests caught
that, enforcing the rule this module set for itself — **change where a default
comes from, never what it is on an unconfigured install**. A behaviour change
smuggled in beside a refactor is invisible in review and indistinguishable from
a bug.

So the screens keep their floors and share the part that was actually
duplicated: "read Settings, validate it, fall back if unusable".
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

#: The Dev Board's own floor, unchanged from the constant it used to hold.
FALLBACK_SYMBOL = "ETHUSDT"
#: `.value`, not the bare enum member — `TimeFrame.ONE_MINUTE` does not
#: render as `"1m"` under `str()`/an f-string the way this constant's callers
#: (config comparisons, QML property defaults) expect a plain `str` to.
FALLBACK_INTERVAL = TimeFrame.ONE_MINUTE.value

#: The Database screen's picker offers several symbols rather than one. Its
#: own floor, also unchanged — note the first entry is `BTCUSDT`, not the Dev
#: Board's `ETHUSDT`, which is exactly why the fallback is per-screen.
FALLBACK_SYMBOL_OPTIONS: tuple[str, ...] = (
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
)

_SYMBOLS_CONFIG_KEY = "DEFAULT_SYMBOLS"
_INTERVAL_CONFIG_KEY = "DEFAULT_INTERVAL"


def _configured_symbols(config_values: Mapping[str, Any]) -> list[str]:
    raw = config_values.get(_SYMBOLS_CONFIG_KEY)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item.strip()]


def default_symbol(config_values: Mapping[str, Any], fallback: str) -> str:
    """The symbol a screen should start on, honouring Settings.

    @param config_values Whatever `IConfig.get_all()` returned. Passed in
    rather than resolved here so this module stays a pure function of its
    input — every caller already holds the mapping, and a screen that reads it
    twice would otherwise be able to see two different answers.
    @param fallback This screen's own floor, for an install that has declared
    nothing. See the module docstring for why it is not shared.
    """
    symbols = _configured_symbols(config_values)
    return symbols[0] if symbols else fallback


def default_symbol_options(
    config_values: Mapping[str, Any], fallback: Sequence[str]
) -> list[str]:
    """Every symbol Settings declares, for a screen that offers a choice."""
    return _configured_symbols(config_values) or list(fallback)


def default_interval(
    config_values: Mapping[str, Any], fallback: str, allowed: object = None
) -> str:
    """The interval a screen should start on, honouring Settings.

    @param allowed Optional collection the configured value must belong to —
    a screen whose timeframe picker offers a fixed set must not start on a
    value that picker cannot represent. An unusable configured value falls
    through to `fallback` rather than raising: Settings is free-text
    here, and a screen refusing to open is a worse answer than a screen
    opening on its default.
    """
    raw = config_values.get(_INTERVAL_CONFIG_KEY)
    candidate = raw.strip() if isinstance(raw, str) else ""
    if not candidate:
        return fallback
    if allowed is not None and candidate not in allowed:
        return fallback
    return candidate
