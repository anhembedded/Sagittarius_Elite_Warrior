"""How a `StrategyRegistry` key is shown to a user.

@details One function, two screens. Backtest had
`BackTestPresenter._humanize_strategy_key` and `EPIC-022` added a
byte-identical copy for the Trading screen's strategy card, with a comment
excusing it as "duplicated rather than imported across screens" — true
about the import direction (`EPIC-021L` removed `screens/trading/ →
screens/backtest/`), but the answer to that is a shared home, not a second
copy. `BOT-125` review moved it here, where `presentation/ui/common/`
already keeps the cross-screen helpers.

@par This exists because strategies have no display name
`BaseStrategy` declares parameters, indicators, colours and trend zones,
but no human-readable title, so the registry key is all a picker has to
show. Deriving the label is a workaround, not a design: the moment a
strategy wants a real name ("EMA Crossover" rather than "Ema Crossover"),
the fix is a `display_name` on the strategy itself and this function
becomes its fallback — which is exactly why both screens must already be
calling one function and not two.
"""

from __future__ import annotations


def humanize_strategy_key(key: str) -> str:
    """`ema_crossover` -> `Ema Crossover`."""
    return key.replace("_", " ").title()
