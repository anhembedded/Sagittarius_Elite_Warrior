"""The kernel contracts: what the shell and a bounded context agree on (HLD §2.4).

`src/core/` holds two things and nothing else: these contracts — the
contribution descriptor, the registry port, places, navigation metadata, the
config-writer port and the errors those contracts raise — and, once two modules
consume the same value object, a `vo/` package for the Published Language. Phase
0 has no such value object, so there is no `vo/` yet; the first one arrives with
the second module that needs it, not before.

Nothing here imports a bounded context, a support package or the legacy tree,
and nothing here imports a UI toolkit at runtime — the two guards
`test_module_boundaries` and `test_module_domain_is_qt_free` hold both.
"""

from Sagittarius_Elite_Warrior.src.core.contracts.contribution_descriptor import (
    SHELL_CONTRIBUTOR_ID,
    ContributionDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.errors import ContributionError
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_registry import (
    IContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_place_host import IPlaceHost
from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import (
    NavLocation,
    NavMetadata,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.screen_contribution import (
    ScreenContribution,
)
from Sagittarius_Elite_Warrior.src.core.contracts.size_hint import SizeHint

__all__ = [
    "SHELL_CONTRIBUTOR_ID",
    "ContributionDescriptor",
    "ContributionError",
    "IConfigWriter",
    "IContributionRegistry",
    "IPlaceHost",
    "NavLocation",
    "NavMetadata",
    "Place",
    "ScreenContribution",
    "SizeHint",
]
