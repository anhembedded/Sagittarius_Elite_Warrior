"""
@brief `INotificationChannel` — one way to surface a notable failure to a human.

@details
`BOT-018`. Narrow on purpose, mirroring `IEventPublisher`: one method, no
subscribe, no channel-specific configuration exposed through the port — each
implementation reads what it needs (a window, a bot token) at its own
construction. `NotificationEventHandler` fans the same plain-text `message`
out to every configured channel.
"""

from abc import ABC, abstractmethod


class INotificationChannel(ABC):
    """
    @brief Delivers a plain-text notification message to one destination.
    """

    @abstractmethod
    def send(self, message: str) -> None:
        """
        @brief Delivers `message`.

        @details Fire-and-forget: no return value, no delivery guarantee a
        caller can branch on. An implementation that cannot deliver (a
        network failure, an unconfigured destination) must catch and log
        that itself; it must never raise out of this method, the same
        contract `IEventPublisher.publish()` states for its own callers.
        """
        ...
