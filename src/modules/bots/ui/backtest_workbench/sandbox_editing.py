"""`EPIC-040D` — the workbench's sandbox as the person edits it: the copy, its kind's editor and the
verdicts the kind's own rules give it.

@details One `SandboxSession` (`EPIC-040C`: copy unless edited, ask once) plus what hangs on it: the
editor of the plan's kind in the setup column, and the plan judged by that kind's `validate` with no
account. It knows nothing of a run; the presenter asks it what the sandbox is and what it says."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    UnknownBotKindError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.sandbox_plan import (
    SandboxPlan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest.sandbox_judge import (
    judge_sandbox,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest.sandbox_session import (
    SandboxFollow,
    SandboxSession,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_selection import (
    WorkbenchSelection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)


class SandboxEditing:
    """@brief The sandbox, its editor and its verdicts."""

    def __init__(
        self,
        view: BacktestWorkbenchView,
        kinds: Callable[[str], IBotKind],
        editors: Callable[[str], BotKindPanel],
    ) -> None:
        self._view = view
        self._kinds = kinds
        self._editors = editors
        self._session = SandboxSession()
        self._editor_kind = ""
        self.verdicts: tuple[Verdict, ...] = ()

    @property
    def plan(self) -> SandboxPlan | None:
        return self._session.plan

    @property
    def pending_copy(self) -> object | None:
        """The other bot's plan waiting for the person to say replace or keep."""
        return self._session.pending_copy

    def follow(self, selection: WorkbenchSelection) -> SandboxFollow:
        return self._session.follow(selection.bot)

    def show_copy(self) -> None:
        """Puts the kind's editor, venue profile and the copy's parameters in the setup column."""
        plan = self._session.plan
        if plan is None:
            return
        if plan.kind_id != self._editor_kind:
            self._editor_kind = plan.kind_id
            self._view.set_editor(self._editors(plan.kind_id))
        editor = self._view.editor
        profile = venue_profile_of(plan.venue)
        if editor is not None and profile is not None:
            editor.set_profile(profile)
        if editor is not None:
            editor.set_config(plan.config)

    def edit(self, config: Mapping[str, str]) -> None:
        plan = self._session.plan
        if plan is not None:
            self._session.edit(plan.with_config(config))

    def reset(self) -> None:
        self._session.reset()
        plan, editor = self._session.plan, self._view.editor
        if plan is not None and editor is not None:
            editor.set_config(plan.config)

    def confirm_switch(self) -> None:
        self._session.confirm_switch()

    def keep_current(self) -> None:
        self._session.keep_current()

    def judge(self, selection: WorkbenchSelection) -> None:
        """The sandbox judged by the kind's own rules with no account; the editor marks its fields."""
        plan = self._session.plan
        kind = self._kind_of(plan)
        self.verdicts = ()
        if plan is not None and kind is not None:
            self.verdicts = judge_sandbox(
                kind, plan, selection.market, selection.risk
            ).verdicts
        editor = self._view.editor
        if editor is not None:
            editor.set_planner_market(selection.market)
            editor.set_plan_facts(None, selection.risk)
            editor.show_verdicts(self.verdicts)

    def kind(self) -> IBotKind | None:
        return self._kind_of(self._session.plan)

    def _kind_of(self, plan: SandboxPlan | None) -> IBotKind | None:
        if plan is None:
            return None
        try:
            return self._kinds(plan.kind_id)
        except UnknownBotKindError:
            return None
