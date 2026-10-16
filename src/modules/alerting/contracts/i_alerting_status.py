"""`IAlertingStatus` — what another module may ask of alerting (`EPIC-036G`, decision D5).

The headless host asks one question before it leaves bots alone: would a bot
that halts reach a person? `operations` binds its own `IAlertChannels` over this
port, so `alerting` depends on no module for it and `operations` reads only
`alerting/contracts`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IAlertingStatus(ABC):
    @abstractmethod
    def carries_bot_events(self) -> bool:
        """True when a bot's alerts have a channel to go to: at least one channel
        is configured on this host (its secret is present) and not disabled."""
