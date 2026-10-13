"""Whether anything would tell the owner that a bot halted (`EPIC-038D`).

The host starts the bots' workers on a machine nobody watches, so the first
thing it asks is whether a halt would reach a person. Before `EPIC-036B` routes
bot events to a channel the honest answer is no, and the host says so at start
(a WARNING) and refuses to resume RECOVERING bots by itself unless the operator
types that they accept silent failures (`--i-accept-silent-failures`).

The port is the seam `EPIC-036B`/`036C` fill: when bot events reach a channel,
its adapter answers `True` and neither the warning nor the refusal appears. Until
then the binding is `NoAlertChannels`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IAlertChannels(ABC):
    @abstractmethod
    def carries_bot_events(self) -> bool:
        """True when a bot halting is sent to a channel a person reads."""
