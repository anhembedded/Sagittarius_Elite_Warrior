"""
@brief `IUserDataStream` — the port for starting/stopping Binance Futures'
User Data Stream (`EPIC-021H`): the exchange's own account of what happened
to an order, as opposed to a synchronous request's ack.

@details Same shape as `ILiveStreamService` (start/stop, `bool` return) —
deliberately a separate port, not a method added to that one: the two
streams need different credentials (this one signs; kline data does not),
have different failure consequences (losing kline data freezes a chart;
losing this one leaves the app blind about its own money — `EPIC-021H`
§2.1), and Interface Segregation already named this exact reasoning once
for `ITradingClient` vs `IExchangeClient` (`EPIC-021E`).
"""

from abc import ABC, abstractmethod


class IUserDataStream(ABC):
    """@brief Port for the exchange's authoritative order/position feed."""

    @abstractmethod
    def start(self) -> bool:
        """@brief Starts the stream as a background task.
        @return True if started, False if already running.
        """

    @abstractmethod
    def stop(self) -> bool:
        """@brief Signals cooperative cancellation and stops the stream.
        @return True if stopped, False if not running.
        """
