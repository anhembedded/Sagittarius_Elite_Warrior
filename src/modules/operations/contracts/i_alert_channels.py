"""Whether anything would tell the owner that a bot halted (`EPIC-038D`).

The host starts the bots' workers on a machine nobody watches, so the first
thing it asks is whether a halt would reach a person. Before a channel is
configured the honest answer is no, and the host says so at start
(a WARNING) and refuses to resume RECOVERING bots by itself unless the operator
types that they accept silent failures (`--i-accept-silent-failures`).

The port is the seam `EPIC-036G` filled (decision D5): `AlertingAlertChannels`
asks the alerting module, which answers `True` once a channel is configured on
this host (a Discord webhook is stored); then neither the warning nor the refusal
appears.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IAlertChannels(ABC):
    @abstractmethod
    def carries_bot_events(self) -> bool:
        """True when a bot halting is sent to a channel a person reads."""
