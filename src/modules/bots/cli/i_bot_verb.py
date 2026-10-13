"""One word after `bot` (`EPIC-038C`, `EPIC-038I`)."""

from __future__ import annotations

import argparse
from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import CliOutcome
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verb_world import BotVerbWorld


class IBotVerb(ABC):
    """One word after `bot`."""

    #: The word, exactly as `cli_commands.json` spells it.
    name: str

    @abstractmethod
    def run(
        self,
        args: argparse.Namespace,
        world: BotVerbWorld,
    ) -> CliOutcome | None:
        """Do the verb; the outcome is its exit code (`None` is success)."""
