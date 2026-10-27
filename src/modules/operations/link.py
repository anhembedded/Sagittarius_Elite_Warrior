"""`operations` on the remote link: the host-facts view and the control door the bridge uses (`EPIC-047C`).

The second file of `modules/operations/` that `shell/` may import (`boundaries/zones.py`,
`is_module_entry_point`); `module.py` is the whole module and loads every handler, binding and
check. This file imports the facts file's reader and the control directory's writer, and nothing
that builds an app. It holds no behaviour of its own. The paths are the host's own
(`state/host-facts.json`, `state/control/`), given by the caller from the data root.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.core.contracts.wire_root import WireRoot
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.control_directory import (
    AUDIT_FILE_NAME,
    control_directory_of,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_host_facts_view import (
    FileHostFactsView,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.json_host_facts_codec import (
    JsonHostFactsCodec,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.replaying_command_door import (
    ReplayingCommandDoor,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.system_operations_clock import (
    SystemOperationsClock,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.wire_document_file import (
    WireDocumentView,
)
from Sagittarius_Elite_Warrior.src.modules.operations.composition.wire_roots import (
    HOST_FACTS_DOCUMENT_ROOT,
    HOST_READS_DOCUMENT_ROOT,
    MARKET_DATA_DOCUMENT_ROOT,
    OPERATIONS_WIRE_ROOTS,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HOST_FACTS_FILE_NAME,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_reads_document import (
    HOST_READS_FILE_NAME,
    HostReadsDocument,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.market_data_document import (
    MARKET_DATA_FILE_NAME,
    MarketDataDocument,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_facts import (
    IBridgeFacts,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_command_door import (
    ICommandDoor,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_wire_codec import (
    IWireCodec,
)


def wire_roots() -> tuple[WireRoot, ...]:
    """The types of this module's contracts that cross the remote link."""
    return OPERATIONS_WIRE_ROOTS


def bridge_facts(state_directory: Path) -> IBridgeFacts:
    """The host-facts file under `state_directory`, read for the bridge."""
    return FileHostFactsView(
        state_directory / HOST_FACTS_FILE_NAME,
        JsonHostFactsCodec(),
        SystemOperationsClock(),
        HOST_FACTS_DOCUMENT_ROOT,
    )


def bridge_documents(
    state_directory: Path, codec: IWireCodec
) -> Mapping[str, IBridgeFacts]:
    """The host's market-data file and host-reads file under `state_directory`, by the kind the protocol names
    them (`market`, `reads`), read for the bridge (`EPIC-047H`). `codec` is the build's registry of wire roots."""
    clock = SystemOperationsClock()
    return {
        "market": WireDocumentView[MarketDataDocument](
            state_directory / MARKET_DATA_FILE_NAME,
            codec,
            MARKET_DATA_DOCUMENT_ROOT,
            lambda document: document.header,
            clock,
        ),
        "reads": WireDocumentView[HostReadsDocument](
            state_directory / HOST_READS_FILE_NAME,
            codec,
            HOST_READS_DOCUMENT_ROOT,
            lambda document: document.header,
            clock,
        ),
    }


def bridge_door(state_directory: Path, probe: IInstanceProbe) -> ICommandDoor:
    """The host's control directory under `state_directory`, written for the bridge."""
    directory = control_directory_of(state_directory)
    return ReplayingCommandDoor(
        directory,
        directory / AUDIT_FILE_NAME,
        probe,
        SystemOperationsClock(),
        time.sleep,
        time.monotonic,
    )
