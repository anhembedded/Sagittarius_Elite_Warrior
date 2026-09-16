"""`ArmedStrategySnapshot` — what is armed right now, as one atomic answer.

HLD §3.4 names this DTO; PR 2.1c is what decided its two fields, by reading the
call site that needed them:

```python
armed_config = self._strategy_session.config          # one lock acquisition
strategy_owns_symbol = (
    self._strategy_session.is_armed                   # ...and a second one
    and armed_config is not None
    and armed_config.symbol == symbol
)
```

That is `dashboard_presenter.py`, deciding whether a manual order would collide
with an armed strategy on the same symbol. It reads **two** facts that are not
the same fact — `config` is the value the user chose, `is_armed` is whether the
engine was actually built from it — and it reads them through two separate
acquisitions of the session's lock, so a strategy armed between the two reads is
observable as a torn state.

Answering both in one snapshot, under one acquisition, is why this type exists
rather than the port having two getters. It is also the one behaviour this pull
request changes, and it changes it in the safe direction: the pair can no longer
disagree with itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)


@dataclass(frozen=True, slots=True)
class ArmedStrategySnapshot:
    """The armed state of the live session at one instant."""

    #: What the user armed, or `None` when nothing is armed. The value object
    #: already carries `symbol`, `interval`, the strategy key and its
    #: parameters — which is why no separate snapshot of *those* fields was
    #: written; see `Docs/SDD/05` §5.
    config: LiveStrategyConfig | None

    #: Whether an engine is actually built and running for that config.
    #: Distinct from `config is not None` on purpose: arming records the value
    #: and then builds the engine, so a caller that must not act while a
    #: strategy owns a symbol has to ask about the engine, not the intent.
    engine_running: bool
