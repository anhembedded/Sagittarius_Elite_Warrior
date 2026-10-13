"""What the host tells a service manager about itself (`EPIC-038D`).

systemd's `Type=notify` units want to hear that the service is ready, that it is
still alive (the watchdog) and that it is stopping; other managers want to hear
nothing. The host says all three to an `IHostSignal` and does not care who
listens. `NullHostSignal` is the default; `SdNotifyHostSignal` speaks the
sd_notify protocol and is chosen with `--host-signal sdnotify`.

Every method is best effort: a manager that cannot be reached must never stop
the host from serving or from stopping, so an adapter swallows its own failure
(logging it once) and returns.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IHostSignal(ABC):
    @abstractmethod
    def ready(self) -> None:
        """The host is serving."""

    @abstractmethod
    def watchdog(self) -> None:
        """The host is alive. Called often; the adapter decides how often to pass it on."""

    @abstractmethod
    def stopping(self) -> None:
        """The host has begun to drain."""
