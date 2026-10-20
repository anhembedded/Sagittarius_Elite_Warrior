"""
@brief `INotificationChannel` — one way to surface a notable failure to a human.

@details
`BOT-018`. Narrow on purpose, mirroring `IEventPublisher`: one method, no
subscribe, no channel-specific configuration exposed through the port — each
implementation reads what it needs (a window, a bot token) at its own
construction. `SystemFailureRelay` fans the same plain-text `message`
out to every configured channel.

`Protocol`, not `ABC`, under `architecture-rule.md` §2.1 reason (a):
`UiToastNotificationChannel` must be a `QObject` (its `send()` hops onto the
main thread via a queued signal before touching `QMainWindow.statusBar()`),
and Shiboken's metaclass conflicts with `ABCMeta`. `@runtime_checkable` so
`test_channels_satisfy_the_port.py` can assert conformance without either
implementer declaring inheritance — mirrors `IBacktestChartHost`'s own
`PythonBacktestChartHost`, which conforms the same structural way.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class INotificationChannel(Protocol):
    """
    @brief Delivers a plain-text notification message to one destination.
    """

    def send(self, message: str) -> None:
        """
        @brief Delivers `message`.

        @details Fire-and-forget: no return value, no delivery guarantee a
        caller can branch on. An implementation that cannot deliver (a
        network failure, an unconfigured destination) must catch and log
        that itself; it must never raise out of this method, the same
        contract `IEventPublisher.publish()` states for its own callers.
        `SystemFailureRelay` calls this on whatever thread published the
        failure — an implementation that touches Qt must hop back to the main
        thread itself, and one that blocks must not be added to it.
        """
        ...
