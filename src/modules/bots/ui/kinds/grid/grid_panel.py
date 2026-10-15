"""`EPIC-029F` — the Grid's parameter editor.

Every parameter is a field the user owns (the user's rule, 2026-10-03: the
parameters are the user's; the bot judges them, never fixes them). The two
suggestions are the one exception to "never fills a field", and only when
asked: they copy the planner's ATR or Bollinger range into the range fields,
rounded to the symbol's tick, and the user may change them again.

They are the Grid's own commands (`EPIC-033K` stage 2; SPEC-014: "each bot
type has its own toolbar"): two actions on the Grid toolbar at the top of
this editor, which is shown only while a Grid is selected, and the same
commands in the Bots menu (`kind_commands.py`). They were push buttons under
the fields.

The fields read and write the definition's strings (`GridParams.to_config`
spells them): an exit is `off`, `price:<p>` or `percent:<n>`.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QSignalBlocker, QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
    VenueProfile,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    ExitKind,
    GridSpacing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_exit_field import (
    ExitField,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_exposure_fields import (
    ROW_LABELS,
    ExposureFields,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_field_display import (
    marker_icon,
    price_text,
    snap_to_tick,
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
    FieldError,
    field_errors,
    field_of_code,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_commands import (
    SUGGEST_FROM_ATR,
    SUGGEST_FROM_BOLLINGER,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

#: Binance's own floor for a Spot grid; the planner refuses fewer anyway.
_MIN_GRIDS = 2
_MAX_GRIDS = 1000
#: What a new Grid's count field starts at; the user changes it.
_DEFAULT_GRIDS = 10
_NO_RANGE_YET = "The planner has no {name} range: it needs more stored daily candles."


class GridPanel(BotKindPanel):
    """@brief Edits one Grid's parameters."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._market: PlannerMarket | None = None
        self._editable = True
        self.lower_price = _decimal_field("editGridLower")
        self.upper_price = _decimal_field("editGridUpper")
        self.grid_count = QSpinBox()
        self.grid_count.setObjectName("spinGridCount")
        self.grid_count.setRange(_MIN_GRIDS, _MAX_GRIDS)
        self.grid_count.setValue(_DEFAULT_GRIDS)
        self.spacing = QComboBox()
        self.spacing.setObjectName("cmbGridSpacing")
        for spacing in GridSpacing:
            self.spacing.addItem(spacing.value.capitalize(), spacing.value)
        self.capital = _decimal_field("editGridCapital")
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
        self._error_labels: dict[str, QLabel] = {}
        self._marker_labels: dict[str, QLabel] = {}
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
                _int_or(config.get("grid_count", ""), _DEFAULT_GRIDS)
            )
        index = self.spacing.findData(
            config.get("spacing", GridSpacing.ARITHMETIC.value)
        )
        self.spacing.setCurrentIndex(max(index, 0))
        self.capital.setText(config.get("capital_quote", ""))
        self.stop_loss.show_encoded(config.get("stop_loss", ExitKind.OFF.value))
        self.take_profit.show_encoded(config.get("take_profit", ExitKind.OFF.value))
        self.exposure.show_config(config)

    def set_profile(self, profile: VenueProfile) -> None:
        """Offers the rows `profile` lists. A row appears because the profile has something
        for it, never because a market is named here (`EPIC-039J`)."""
        self.exposure.set_profile(profile)
        for key, shown in self.exposure.visible_rows().items():
            self._form.setRowVisible(self._rows[key], shown)

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
        self._editable = editable
        self._offer_suggestions()

    # -- internals -------------------------------------------------------- #

    def _offer_suggestions(self) -> None:
        """A suggestion is offered while the planner has its range and the
        fields can take it: the planner may answer after the editor was made
        read-only."""
        market = self._market
        _offer(self.suggest_atr, market.atr_range if market else None, "ATR")
        _offer(
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
            row = self._row(key, editor)
            self._rows[key] = row
            form.addRow(FIELD_LABELS[key], row)
        for key, widget in self.exposure.read_only_rows():
            self._rows[key] = widget
            form.addRow(ROW_LABELS[key], widget)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addLayout(form)
        for key in self.exposure.visible_rows():
            form.setRowVisible(self._rows[key], False)

    def _row(self, key: str, editor: QWidget) -> QWidget:
        """The editor with, under it, what the constraints say about it
        (`EPIC-034F`): empty and hidden until a verdict is about this field."""
        error = plain_label()
        error.setObjectName(f"lblGridError_{key}")
        error.setWordWrap(True)
        error.setVisible(False)
        self._error_labels[key] = error
        marker = plain_label()
        marker.setObjectName(f"lblGridMarker_{key}")
        marker.setVisible(False)
        self._marker_labels[key] = marker
        said = QHBoxLayout()
        said.setContentsMargins(0, 0, 0, 0)
        said.addWidget(marker, 0, Qt.AlignmentFlag.AlignTop)
        said.addWidget(error, 1)
        row = QWidget()
        column = QVBoxLayout(row)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(editor)
        column.addLayout(said)
        return row

    # -- constraints on the fields (EPIC-034F) ----------------------------- #

    def show_verdicts(self, verdicts: tuple[Verdict, ...]) -> None:
        shown = field_errors(verdicts, self.exposure.selected_direction())
        for key, label in self._error_labels.items():
            error = shown.get(key)
            label.setText(error.text if error else "")
            label.setVisible(error is not None)
            self._mark(key, error)
            self._editor_of(key).setToolTip(error.text if error else "")
        self.exposure.show_liquidation(verdicts)

    def _mark(self, key: str, error: FieldError | None) -> None:
        """A sign beside the sentence, from the platform's own icons: a stop sign
        for what blocks Start, information for advice, and its words for a screen
        reader. Colour is never the only signal."""
        marker = self._marker_labels[key]
        marker.setVisible(error is not None)
        if error is None:
            marker.clear()
            marker.setAccessibleName("")
            return
        icon = marker_icon(error.blocks)
        size = marker.fontMetrics().height()
        marker.setPixmap(
            self.style()
            .standardIcon(icon)
            .pixmap(QSize(size, size), marker.devicePixelRatioF())
        )
        marker.setAccessibleName("Blocks Start" if error.blocks else "Advice")

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
        label = self._error_labels[key]
        return label.text() if not label.isHidden() else ""

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
        self.suggest_atr.triggered.connect(lambda: self._fill_range(self._atr()))
        self.suggest_bollinger.triggered.connect(
            lambda: self._fill_range(self._bollinger())
        )

    def _atr(self) -> SuggestedRange | None:
        return self._market.atr_range if self._market else None

    def _bollinger(self) -> SuggestedRange | None:
        return self._market.bollinger if self._market else None

    def _fill_range(self, suggested: SuggestedRange | None) -> None:
        if suggested is None:
            return
        tick = (
            self._market.terms.tick_size
            if self._market and self._market.terms
            else None
        )
        self.lower_price.setText(price_text(snap_to_tick(suggested.lower, tick)))
        self.upper_price.setText(price_text(snap_to_tick(suggested.upper, tick)))
        self._emit()

    def _emit(self, *_args: object) -> None:
        self.config_changed.emit(self.config())


def _decimal_field(name: str) -> QLineEdit:
    field = QLineEdit()
    field.setObjectName(name)
    return field


def _offer(action: QAction, suggested: SuggestedRange | None, name: str) -> None:
    action.setEnabled(suggested is not None)
    if suggested is None:
        action.setToolTip(_NO_RANGE_YET.format(name=name))
    else:
        action.setToolTip(f"Fill the range with {suggested.lower} – {suggested.upper}.")


def _int_or(text: str, default: int) -> int:
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError):
        return default
