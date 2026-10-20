"""`EPIC-040C` — which sandbox the Backtest tab holds, as the Bots selection moves.

Pure logic with no widget, so the rule is tested without one: selecting a bot copies its saved plan
into a fresh sandbox, *unless the person has edited the sandbox*; then the tab must ask before it
throws the edits away. The tab (`EPIC-040D`) shows the question and calls `confirm_switch` or
`keep_current`; this class never decides to discard on its own.

The Bots screen calls `follow` on every refresh of the selection (its clock, each planner answer), so
the same saved plan arriving again changes nothing.
"""

from __future__ import annotations

from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.sandbox_plan import (
    SandboxPlan,
)


class SandboxFollow(Enum):
    """What a selection did to the sandbox."""

    UNCHANGED = "unchanged"
    #: A fresh copy of the selected bot's saved plan replaced the sandbox.
    COPIED = "copied"
    #: The sandbox has edits and another plan was selected: ask before discarding them.
    NEEDS_CONFIRMATION = "needs_confirmation"


class SandboxSession:
    """@brief Holds the sandbox and the selection waiting on the person's answer."""

    def __init__(self) -> None:
        self._plan: SandboxPlan | None = None
        self._pending_copy: SandboxPlan | None = None

    @property
    def plan(self) -> SandboxPlan | None:
        return self._plan

    @property
    def pending_copy(self) -> SandboxPlan | None:
        """The copy that would replace the edited sandbox, while the question is open."""
        return self._pending_copy

    def follow(self, bot: BotSnapshot | None) -> SandboxFollow:
        """The Bots selection is now `bot` (`None`: nothing selected, which keeps the sandbox)."""
        if bot is None:
            return SandboxFollow.UNCHANGED
        copy = SandboxPlan.from_bot(bot)
        current = self._plan
        if current is not None and _same_source(current, copy):
            self._pending_copy = None
            return SandboxFollow.UNCHANGED
        if current is not None and current.edited:
            self._pending_copy = copy
            return SandboxFollow.NEEDS_CONFIRMATION
        self._plan, self._pending_copy = copy, None
        return SandboxFollow.COPIED

    def edit(self, plan: SandboxPlan) -> None:
        """The person changed the parameters being tried."""
        self._plan = plan

    def reset(self) -> None:
        if self._plan is not None:
            self._plan = self._plan.reset()

    def confirm_switch(self) -> None:
        """The person agreed to discard the edits: the pending copy becomes the sandbox."""
        if self._pending_copy is not None:
            self._plan, self._pending_copy = self._pending_copy, None

    def keep_current(self) -> None:
        """The person kept the edits: the selected bot's copy is dropped."""
        self._pending_copy = None


def _same_source(a: SandboxPlan, b: SandboxPlan) -> bool:
    return (a.source_bot_id, dict(a.source_config)) == (
        b.source_bot_id,
        dict(b.source_config),
    )
