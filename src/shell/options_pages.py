"""The pages of Tools → Options, in the order the dialog lists them
(`EPIC-033E`).

Each module's page comes from its `OptionsPageContribution`, built here with
the container; the shell's own pages go last, after the pages about trading
and data, as an application's own options do: Appearance (`EPIC-043B`), then
Developer (`EPIC-033C`). Appearance is not first so that Options still opens on
Trading, where the keys are.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import (
    IConfigReader,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from Sagittarius_Elite_Warrior.src.core.contracts.i_options_section import (
    IOptionsSection,
)
from Sagittarius_Elite_Warrior.src.shell.appearance_options.appearance_options_page import (
    AppearanceOptionsPage,
)
from Sagittarius_Elite_Warrior.src.shell.contribution_registry import (
    ContributionRegistry,
)
from Sagittarius_Elite_Warrior.src.shell.developer_options.developer_options_page import (
    DeveloperOptionsPage,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.colour_scheme_preference import (
    ColourSchemePreference,
)
from sagittarius_engine.interfaces.i_container import IContainer


def build_options_pages(
    contributions: ContributionRegistry,
    container: IContainer,
    config: IConfigReader,
    *,
    running_with_dev_mode: bool,
) -> tuple[IOptionsSection, ...]:
    """Every page, built: the modules' in their contributed order, then
    Appearance, then Developer."""
    module_pages = tuple(
        contribution.factory(container)
        for contribution in contributions.options_pages()
    )
    developer = DeveloperOptionsPage(
        config,
        container.resolve(IConfigWriter),
        running_with_dev_mode=running_with_dev_mode,
    )
    appearance = AppearanceOptionsPage(container.resolve(ColourSchemePreference))
    return (*module_pages, appearance, developer)
