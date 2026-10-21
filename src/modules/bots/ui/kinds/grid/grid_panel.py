"""`EPIC-029F` — the Grid's parameter editor.

Every parameter is a field the user owns (the user's rule, 2026-10-03: the
parameters are the user's; the bot judges them, never fixes them). The two
suggestions are the one exception, and only when asked: they write a whole plan
(`suggest_plan`, `BUG-211`: the range and any price exit it invalidates), say what
moved, and the user may change it again.

They are the Grid's own commands (`EPIC-033K` stage 2; SPEC-014): two actions on the
Grid toolbar, and the same commands in the Bots menu (`kind_commands.py`).

The fields read and write the definition's strings (`GridParams.to_config`
spells them): an exit is `off`, `price:<p>` or `percent:<n>`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from PySide6.QtCore import QSignalBlocker
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
    SuggestedRange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureLimits,
    VenueProfile,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    ExitKind,
    GridSpacing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_editor_parts import (
    EditedPlan,
    PlanFacts,
    decimal_field,
    int_or,
    offer_suggestion,
    suggest_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_exit_field import (
    ExitField,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_exposure_fields import (
    ROW_LABELS,
    ExposureFields,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_field_display import (
    price_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_field_errors import (
    CAPITAL,
    DIRECTION,
    FIELD_LABELS,
    FIELDS_OF_CODE,
    GRID_COUNT,
    LEVERAGE,
    LOWER,
    SPACING,
    STOP_LOSS,
    TAKE_PROFIT,
    UPPER,
    field_errors,
    field_of_code,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_field_hints import (
    MAX_GRIDS,
    MIN_GRIDS,
    FieldHints,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_suggestion_log import (
    log_suggestion,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_commands import (
    SUGGEST_FROM_ATR,
    SUGGEST_FROM_BOLLINGER,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

#: What a new Grid's count field starts at; the user changes it.
_DEFAULT_GRIDS = 10


class GridPanel(BotKindPanel):
    """@brief Edits one Grid's parameters."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._market: PlannerMarket | None = None
        self._editable = True
        self._facts = PlanFacts()
        self.lower_price = decimal_field("editGridLower")
        self.upper_price = decimal_field("editGridUpper")
        self.grid_count = QSpinBox()
        self.grid_count.setObjectName("spinGridCount")
        self.grid_count.setRange(MIN_GRIDS, MAX_GRIDS)
        self.grid_count.setValue(_DEFAULT_GRIDS)
        self.spacing = QComboBox()
        self.spacing.setObjectName("cmbGridSpacing")
        for spacing in GridSpacing:
            self.spacing.addItem(spacing.value.capitalize(), spacing.value)
        self.capital = decimal_field("editGridCapital")
        self.exposure = ExposureFields()
        self.stop_loss = ExitField("StopLoss")
        self.take_profit = ExitField("TakeProfit")
        self.toolbar = QToolBar("Grid")
        self.toolbar.setObjectName("toolbarGridKind")
        # Worded as the Bots menu's commands, without their access keys.
        self.suggest_atr = self._add_action("actSuggestAtr", "Suggest from ATR")
        self.suggest_bollinger = self._add_action(
            "actSuggestBollinger", "Suggest from Bollinger"
        )
        self.suggestion_note = plain_label()
        self.suggestion_note.setObjectName("lblGridSuggestion")
        self.suggestion_note.setWordWrap(True)
        self.suggestion_note.setVisible(False)
        self._hints = FieldHints(self)
        #: `BOT-209`: the Grids field's one-click answer to a hint that names a count.
        self.use_suggested_grids = self._hints.use_suggested_grids
        self._form = QFormLayout()
        self._rows: dict[str, QWidget] = {}
        self._build_field_layout()
        self._connect()
        self.set_planner_market(None)

    # -- BotKindPanel ----------------------------------------------------- #

    def set_config(self, config: Mapping[str, str]) -> None:
        """Programmatic writes emit nothing: every signal used below is a
        user-edit signal (`textEdited`, `activated`, and the count's
        `valueChanged`, which a write would also raise, so it is blocked)."""
        self.lower_price.setText(price_text(config.get("lower", "")))
        self.upper_price.setText(price_text(config.get("upper", "")))
        with QSignalBlocker(self.grid_count):
            self.grid_count.setValue(
                int_or(config.get("grid_count", ""), _DEFAULT_GRIDS)
            )
        index = self.spacing.findData(
            config.get("spacing", GridSpacing.ARITHMETIC.value)
        )
        self.spacing.setCurrentIndex(max(index, 0))
        self.capital.setText(config.get("capital_quote", ""))
        self.stop_loss.show_encoded(config.get("stop_loss", ExitKind.OFF.value))
        self.take_profit.show_encoded(config.get("take_profit", ExitKind.OFF.value))
        self.exposure.show_config(config)
        self.suggestion_note.setVisible(False)

    def set_profile(self, profile: VenueProfile) -> None:
        """Offers the rows `profile` lists. A row appears because the profile has something
        for it, never because a market is named here (`EPIC-039J`)."""
        self.exposure.set_profile(profile)
        limits = ExposureLimits(
            profile.directions, profile.max_leverage, profile.exposure_kind
        )
        self._facts = replace(self._facts, limits=limits)
        for key, shown in self.exposure.visible_rows().items():
            self._show_row(key, shown)

    def config(self) -> dict[str, str]:
        return {
            "lower": self.lower_price.text().strip(),
            "upper": self.upper_price.text().strip(),
            "grid_count": str(self.grid_count.value()),
            "spacing": GridSpacing(self.spacing.currentData()).value,
            "capital_quote": self.capital.text().strip(),
            "stop_loss": self.stop_loss.encode(),
            "take_profit": self.take_profit.encode(),
            **self.exposure.config(),
        }

    def set_plan_facts(
        self, account: AccountView | None, risk: PlanRiskFacts | None
    ) -> None:
        self._facts = replace(self._facts, account=account, risk=risk)

    def set_planner_market(self, market: PlannerMarket | None) -> None:
        self._market = market
        self._offer_suggestions()

    def kind_actions(self) -> Mapping[str, QAction]:
        return {
            SUGGEST_FROM_ATR: self.suggest_atr,
            SUGGEST_FROM_BOLLINGER: self.suggest_bollinger,
        }

    def set_editable(self, editable: bool) -> None:
        for field in (
            self.lower_price,
            self.upper_price,
            self.grid_count,
            self.spacing,
            self.capital,
            self.stop_loss,
            self.take_profit,
            self.exposure.direction,
            self.exposure.leverage,
        ):
            field.setEnabled(editable)
        self.use_suggested_grids.setEnabled(editable)
        self._editable = editable
        self._offer_suggestions()

    # -- internals -------------------------------------------------------- #

    def _offer_suggestions(self) -> None:
        """A suggestion is offered while the planner has its range and the
        fields can take it: the planner may answer after the editor was made
        read-only."""
        market = self._market
        offer_suggestion(self.suggest_atr, market.atr_range if market else None, "ATR")
        offer_suggestion(
            self.suggest_bollinger, market.bollinger if market else None, "Bollinger"
        )
        if not self._editable:
            self.suggest_atr.setEnabled(False)
            self.suggest_bollinger.setEnabled(False)

    def _add_action(self, object_name: str, text: str) -> QAction:
        action = QAction(text, self)
        action.setObjectName(object_name)
        self.toolbar.addAction(action)
        return action

    def _build_field_layout(self) -> None:
        form = self._form
        rows = (
            (DIRECTION, self.exposure.direction),
            (LOWER, self.lower_price),
            (UPPER, self.upper_price),
            (GRID_COUNT, self.grid_count),
            (SPACING, self.spacing),
            (CAPITAL, self.capital),
            (LEVERAGE, self.exposure.leverage),
            (STOP_LOSS, self.stop_loss),
            (TAKE_PROFIT, self.take_profit),
        )
        for key, editor in rows:
            self._rows[key] = editor
            form.addRow(FIELD_LABELS[key], editor)
            form.addRow(self._hints.hint_line(key))
        for key, widget in self.exposure.read_only_rows():
            self._rows[key] = widget
            form.addRow(ROW_LABELS[key], widget)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.suggestion_note)
        layout.addLayout(form)
        for key in self.exposure.visible_rows():
            self._show_row(key, False)

    def _show_row(self, key: str, shown: bool) -> None:
        """A field's row, with the line under it, offered or not."""
        self._form.setRowVisible(self._rows[key], shown)
        self._hints.set_row_shown(key, shown)

    # -- constraints on the fields (EPIC-034F) ----------------------------- #

    def show_verdicts(self, verdicts: tuple[Verdict, ...]) -> None:
        shown = field_errors(verdicts, self.exposure.selected_direction())
        self._hints.show(shown)
        for key in self._hints.fields():
            error = shown.get(key)
            self._editor_of(key).setToolTip(error.full if error else "")
        self._hints.offer_grid_count(
            shown.get(GRID_COUNT), self.grid_count.value(), self._editable
        )
        self.exposure.show_liquidation(verdicts)

    def focus_field(self, code: str) -> bool:
        key = field_of_code(code)
        if key is None:
            return False
        editor = self._editor_of(key)
        if isinstance(editor, ExitField) and not editor.value.isEnabled():
            editor.kind.setFocus()
        else:
            (editor.value if isinstance(editor, ExitField) else editor).setFocus()
        return True

    def field_label(self, code: str) -> str | None:
        keys = FIELDS_OF_CODE.get(code)
        return " and ".join(FIELD_LABELS[key] for key in keys) if keys else None

    def field_error_text(self, key: str) -> str:
        """What a field says now, `""` when nothing is about it."""
        return self._hints.text_of(key)

    def _editor_of(self, key: str) -> QWidget:
        return {
            LOWER: self.lower_price,
            UPPER: self.upper_price,
            GRID_COUNT: self.grid_count,
            SPACING: self.spacing,
            CAPITAL: self.capital,
            STOP_LOSS: self.stop_loss,
            TAKE_PROFIT: self.take_profit,
            DIRECTION: self.exposure.direction,
            LEVERAGE: self.exposure.leverage,
        }[key]

    def _connect(self) -> None:
        for field in (self.lower_price, self.upper_price, self.capital):
            field.textEdited.connect(self._emit)
        # The arrows, the wheel and Up/Down change the count without a
        # `textEdited` or an `editingFinished` (`BUG-193`): only `valueChanged`
        # hears every way a person sets it, typing included.
        self.grid_count.valueChanged.connect(self._emit)
        self.spacing.activated.connect(self._emit)
        self.exposure.direction.activated.connect(self._emit)
        self.exposure.leverage.valueChanged.connect(self._emit)
        self.stop_loss.edited.connect(self._emit)
        self.take_profit.edited.connect(self._emit)
        self.use_suggested_grids.clicked.connect(self._use_suggested_grids)
        self.suggest_atr.triggered.connect(
            lambda: self._apply_suggestion(
                "ATR", self._market.atr_range if self._market else None
            )
        )
        self.suggest_bollinger.triggered.connect(
            lambda: self._apply_suggestion(
                "Bollinger", self._market.bollinger if self._market else None
            )
        )

    def _use_suggested_grids(self) -> None:
        self.grid_count.setValue(self._hints.suggested_grids)

    def _apply_suggestion(self, source: str, band: SuggestedRange | None) -> None:
        """Writes the plan `suggest_plan` makes of `band` (`BUG-211`) and says what moved."""
        market = self._market
        edited = EditedPlan(self.config(), self._facts)
        suggestion = suggest_for(source, band, market, edited)
        if suggestion is None or market is None or band is None:
            return
        self.lower_price.setText(price_text(suggestion.lower))
        self.upper_price.setText(price_text(suggestion.upper))
        editors = {"stop_loss": self.stop_loss, "take_profit": self.take_profit}
        for key, encoded in suggestion.exits:
            editors[key].show_encoded(encoded)
        self._emit()
        self.suggestion_note.setText(suggestion.panel_line)
        self.suggestion_note.setVisible(bool(suggestion.panel_line))
        log_suggestion(suggestion, band, market)

    def _emit(self, *_args: object) -> None:
        self.suggestion_note.setVisible(False)
        self.config_changed.emit(self.config())
