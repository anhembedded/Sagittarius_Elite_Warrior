"""`EPIC-028A` — what every `VenueAssembly` is given, and nothing it builds.

@details Split out of `venue_assembly.py` (the 400-line ceiling, which it stood exactly at before
`BUG-216` needed lines for the position-mode memory). A plain value: it constructs no adapter, so
`test_only_the_venue_assembly_constructs_venue_adapters.py` is not concerned.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_sourced_secret_store import (
    ISourcedSecretStore,
)
from sagittarius_engine.interfaces.i_container import IContainer


@dataclass(frozen=True)
class SharedVenueInputs:
    """What every venue's assembly shares: the stateless session factories,
    the secrets-file path and the registry that owns each venue's session
    state. The container is only asked for `IEventBus`/`ITaskManager`, and
    only when a user data stream is built."""

    container: IContainer
    secrets_file_path: str
    session_states: VenueSessionStates
    #: Where a mainnet venue's key is kept (`EPIC-034` D10).
    secret_store: ISourcedSecretStore
    #: A copy of the app that may not trade gets read-only clients (`EPIC-035H`).
    instance: IInstanceAccess
