"""`EPIC-038L` - whether the parameters `bot edit` sets are a Grid's, judged without the exchange.

The Grid's own answer to `IBotKind.parameter_problem`. It lives beside `GridParams` and asks it, so
the readable-value rules are the ones `validate` applies and there is no second copy to drift.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
)

#: Every key a Grid's definition may hold, which `bot edit` (`EPIC-038L`) may set.
GRID_PARAMETER_KEYS: tuple[str, ...] = (
    "lower",
    "upper",
    "grid_count",
    "spacing",
    "capital_quote",
    "stop_loss",
    "take_profit",
    "direction",
    "leverage",
    "on_range_exit",
)

#: A valid Grid that every key of `GRID_PARAMETER_KEYS` the probe does not check is read from. The
#: range is as wide as `Decimal` makes useful, so a lower or an upper alone never trips `upper must
#: be above lower` against a stand-in.
_NEUTRAL_PARAMETERS: Mapping[str, str] = {
    "lower": "0.000000000001",
    "upper": "1000000000000",
    "grid_count": "10",
    "spacing": "ARITHMETIC",
    "capital_quote": "100",
    "stop_loss": "off",
    "take_profit": "off",
}


def grid_parameter_problem(
    config: Mapping[str, str], changed: Collection[str]
) -> str | None:
    """Why `config`, whose keys `changed` were just set, is not a Grid's parameters; `None` if it is.

    The question `bot edit` asks without an exchange: is every key known, and is each value *this edit*
    sets readable by `GridParams` and within its own bounds? It builds a probe from the neutral
    Grid plus the changed keys (plus the other end of the range, and the other of `direction` and
    `leverage`, which a change is judged against) and asks `GridParams.from_config`, so the rules are
    the one `validate` applies and no second copy can drift. What needs the venue (the position
    venue's `on_range_exit`, the exchange's filters, the account) is judged when the bot starts.
    """
    unknown = sorted(set(changed) - set(GRID_PARAMETER_KEYS))
    if unknown:
        return (
            f"{', '.join(unknown)} is not a parameter of a grid; they are "
            f"{', '.join(GRID_PARAMETER_KEYS)}"
        )
    probe = dict(_NEUTRAL_PARAMETERS)
    judged = set(changed)
    for pair in (("lower", "upper"), ("direction", "leverage")):
        if judged.intersection(pair):
            judged.update(pair)
    probe.update({key: config[key] for key in judged if config.get(key, "").strip()})
    try:
        GridParams.from_config(probe)
    except GridParamsError as exc:
        return str(exc)
    return None
