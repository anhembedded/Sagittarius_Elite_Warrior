"""
@brief `IEventPublisher` — the Application layer's only way to publish a
domain event.

@details
Before `EPIC-008F`, eight use-cases and services took the engine's own
`IEventBus` as a constructor dependency. That handed the Application layer the
engine's whole bus API — `on()`, `off()`, subscriber bookkeeping — to use one
method of it, and made the layer's dependency on a specific framework
unavoidable.

**Publish only, on purpose.** This port has exactly one method. Subscribing is
deliberately absent: an Application-layer use case that could subscribe would
be able to keep a handler alive past its own lifetime, and deciding *when* to
listen is a Presentation-layer concern (that layer is allowed to know the
engine — see `code-rule.md` §5). A use case fires an event and is done.

The parameter is `IDomainEvent`, one of the two Shared Kernel symbols
`code-rule.md` §5 permits here — see that rule for why those two, and only
those two, are exempt from the port requirement.
"""

from abc import ABC, abstractmethod

from sagittarius_engine.domain.i_domain_event import IDomainEvent


class IEventPublisher(ABC):
    """
    @brief Publishes a domain event to whoever is listening.
    """

    @abstractmethod
    def publish(self, event: IDomainEvent) -> None:
        """
        @brief Publishes `event`.

        @details Fire-and-forget by contract: there is no return value and no
        delivery guarantee a caller can branch on. An implementation that
        cannot deliver must report the failure itself rather than signalling
        it back here — a use case has no sensible recovery for "the bus did
        not accept my event" and must not grow one.
        """
        ...
