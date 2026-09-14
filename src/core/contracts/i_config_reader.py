"""
@brief `IConfigReader` — read-only configuration access for the Application
layer.

@details
`EPIC-008F`'s stated acceptance bar is that `src/domain/` and
`src/application/` import nothing from `sagittarius_engine` except the two
Shared Kernel symbols. Its numbered requirements listed the `IEventBus`
dependencies but missed this one and `ICommandDispatcher`, both of which sit
in `bulk_sync_market_data/handler.py`. Meeting the bar means porting them too.

Deliberately narrower than the engine's `IConfig`, which also offers
`get_all()`, `set()` and typed casts. A use case needs to *read one key with a
fallback* and nothing more; widening this port later requires a reason, while
starting wide would never be narrowed back.
"""

from abc import ABC, abstractmethod
from typing import Any


class IConfigReader(ABC):
    """
    @brief Reads configuration values by key.
    """

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """
        @brief Returns the value for `key`, or `default` when it is absent.

        @details Returning `default` rather than raising on a missing key is
        the contract: configuration is expected to be incomplete, and every
        call site here already supplies the fallback it wants.
        """
        ...
