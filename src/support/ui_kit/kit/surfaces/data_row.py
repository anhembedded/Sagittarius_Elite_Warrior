"""
@brief `DataRow` — a `Panel` laying out one record as a row of cells.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..controls import StyledButton
from ..style import StyleRole, Tone, apply_role, semantic_colour, tone_colour


@dataclass(frozen=True)
class Column:
    """
    @brief One column: its heading, its share of the width, and how its
    cells align.

    @details Shared with `TableCard`, which draws the heading strip these
    same specs describe. The reference consumer keeps three incompatible
    versions of this — a `(label, stretch, alignment)` triple, a
    `(label, stretch)` pair whose header sets no alignment at all, and a
    pair of parallel tuples that must be kept the same length by hand. One
    of those also duplicates its stretch list between the row widget and
    the header builder, which is exactly the drift a single spec prevents.
    """

    label: str
    stretch: int = 1
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft


@dataclass(frozen=True)
class RowAction:
    """One trailing button on a row."""

    label: str
    #: Which button role it renders as — a destructive row action should
    #: not look like an ordinary one.
    #:
    #: Defaults to `GHOST_BUTTON`, not to one of the filled roles: every
    #: row action measured in the reference consumer is an outline, because
    #: a filled button repeated down forty rows reads as the loudest thing
    #: on the screen.
    role: StyleRole = StyleRole.GHOST_BUTTON


class DataRow(QWidget):  # base-exempt: a row inside a table is not a surface
    """
    @brief One label per column, optionally followed by a row of action
    buttons.

    @details
    **Not a `Surface`.** It was written as a `Panel`, which gave every row a
    card background, a border and a radius — so a forty-row table rendered
    as forty stacked cards. All three of the reference consumer's row
    widgets are transparent or zebra-striped and not one has a border; the
    surface in a table is the *table*, and a row is content sitting on it.

    That is the same call `TabBar` needed for the same reason, and the
    asymmetry is what decides it: a consumer that wants each row framed can
    put the row in a `Panel`, while a consumer that does not want a frame
    has no way to take a `Panel`'s away. Both widgets shipped as `Surface`
    subclasses before either had a real consumer to check against — the
    defect is the missing consumer, not the choice.

    Built from three of the reference consumer's four row widgets — its
    status row (6 cells + 4 action buttons), its candle row (8 cells, one
    of which is already written as exactly this loop over a column spec),
    and its gap row (5 cells + 1 button).

    **Its trade-log row is deliberately excluded**, and this is the call
    `EPIC-007B`'s own risk note asked for. That widget is not a wider
    version of this one: it *is* a `QPushButton`, three of its six columns
    stack two lines of differently-styled text, two of its cells are
    recoloured badges, it owns a collapsible detail pane of three further
    columns, and it emits a toggle signal. Fitting it would need a
    per-cell widget factory, an expandable-body hook and a click signal —
    at which point every part of the base is overridden and the base is
    carrying parameters that exist to please one caller.

    **Cells are filled by `set_cells`, never by the constructor.** Three of
    the four consumers already work this way, building empty and refilling
    on model change; the gap row instead takes its data as constructor
    arguments and therefore cannot be updated at all, which is why its own
    dialog has to destroy and rebuild every row on every refresh. Adopting
    the fillable shape is what lets a consumer stop doing that.
    """

    #: Emits the index of the action pressed, within the `actions` sequence
    #: this row was built with. Not the label: labels are display text and
    #: change with locale, while the position is what the caller wired up.
    action_triggered = Signal(int)

    def __init__(
        self,
        columns: Sequence[Column],
        *,
        actions: Sequence[RowAction] = (),
        action_stretch: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        """
        @param action_stretch How much of the row's width the action strip
        claims, on the same scale as `Column.stretch`. `0` — the default —
        gives the buttons their natural width and lets the cells share
        everything left over.

        Pass a value when the heading above the row lists actions as a
        column of its own: two of the reference consumer's three headers do
        (`ACTIONS` at 26, `Repair` at 18), and with the strip at natural
        width the cells expand into its slack and stop lining up with the
        headings that describe them.
        """
        super().__init__(parent)
        if not columns:
            raise ValueError("DataRow needs at least one column")

        self._columns = tuple(columns)
        self._cells: list[QLabel] = []

        row = QHBoxLayout(self)
        # No margins. A row draws no padding of its own — the table around
        # it owns the inset, and a row that adds Qt's default 9px on every
        # side cannot fit the item height its list gives it. That is not
        # hypothetical: it squashed the first real consumer's rows to
        # nothing, because a `QListView` sizes items from the model and the
        # row has to live inside whatever it gets.
        row.setContentsMargins(0, 0, 0, 0)
        for column in self._columns:
            cell = QLabel()
            cell.setAlignment(column.alignment | Qt.AlignmentFlag.AlignVCenter)
            # Every cell starts as `TABLE_CELL`, so a row reads as table
            # text without the consumer styling anything. A cell that should
            # recede or emphasise is moved with `set_cell_role`; leaving
            # them unstyled meant each consumer set a font size by hand, and
            # all three picked the same one.
            apply_role(cell, StyleRole.TABLE_CELL)
            row.addWidget(cell, column.stretch)
            self._cells.append(cell)

        self.action_buttons: list[StyledButton] = []
        # At stretch 0 the buttons go straight into the row and take their
        # natural width. At any other stretch they need a host widget to
        # claim that share — a stretch factor applies to one layout item,
        # and four buttons are four items.
        action_host = QHBoxLayout() if action_stretch else row
        for position, action in enumerate(actions):
            button = StyledButton(action.label, role=action.role)
            button.clicked.connect(
                lambda _checked=False, i=position: self.action_triggered.emit(i)
            )
            action_host.addWidget(button)
            self.action_buttons.append(button)
        if action_stretch and actions:
            row.addLayout(action_host, action_stretch)

    @property
    def columns(self) -> tuple[Column, ...]:
        return self._columns

    def cell_texts(self) -> list[str]:
        """@brief What every cell currently reads, left to right."""
        return [cell.text() for cell in self._cells]

    def set_cells(self, values: Sequence[str]) -> None:
        """
        @brief Fills every cell, left to right.

        @raise ValueError If `values` is not exactly as long as the column
        spec. Silently padding or truncating would put a record's columns
        out of alignment with the heading above them, and a row of data
        shifted one column left is worse than a loud failure — it still
        looks like data.
        """
        if len(values) != len(self._cells):
            raise ValueError(
                f"DataRow has {len(self._cells)} columns, got {len(values)} values"
            )
        for cell, value in zip(self._cells, values, strict=True):
            cell.setText(value)

    def set_action_visible(self, position: int, visible: bool) -> None:
        """@brief Shows or hides one action button — the consumer's status
        row hides its "gaps" button on healthy records rather than
        disabling it."""
        self.action_buttons[position].setVisible(visible)

    def set_cell_role(self, position: int, role: StyleRole) -> None:
        """@brief Restyles one cell — for a status cell that reads as a
        badge, or a value that should carry a section label's muted
        treatment."""
        apply_role(self._cells[position], role)

    def cell(self, position: int) -> QLabel:
        """
        @brief The label behind one cell, for the properties a role cannot
        carry — a monospace font on a column of figures, a tooltip.

        @details Public for the same reason `action_buttons` is: the
        alternative is a setter per property, and the consumer that needed
        this first wanted `setFont`, which is a widget API call and not a
        styling decision. Reach for `set_cell_role` first — anything
        expressible as *what the cell is* belongs in a role, where every
        consumer gets it.
        """
        return self._cells[position]

    def set_cell_tone(self, position: int, tone: Tone) -> None:
        """
        @brief Colours one cell positive / negative / neutral.

        @details The per-instance case `apply_role()` cannot express, and
        the one `Tone`'s own docstring names as its third consumer: whether
        a row's status reads as good or bad is decided per record at
        runtime, so it cannot be a role. Appends a scoped rule rather than
        replacing the sheet, so the cell keeps the size and weight its role
        gave it.

        Scoped, and appended after the role's own closing brace — a bare
        `color:` written after a block is discarded by Qt, which is how the
        same shortcut broke `StatCard`'s badge (`BUG-009`).
        """
        cell = self._cells[position]
        cell.setStyleSheet(
            f"{cell.styleSheet()}QLabel {{ color: {tone_colour(tone)}; }}"
        )

    def set_cell_colour(self, position: int, token: str) -> None:
        """
        @brief Colours one cell by naming a palette token.

        @details The last resort under `set_cell_tone`, for the cell whose
        colour is neither a property of what it is nor a good/bad/neutral
        reading — the reference consumer's gap row prints its duration in
        the accent colour purely to mark it as the notable field, and
        `Tone` has no entry for "notable" because that is not a judgement
        about the value.

        Reach for a role first, then a tone, then this. It takes a token
        name and never a literal, so `guards.find_inline_stylesheets` stays
        satisfied and a palette change still reaches the cell.

        @raise KeyError If no such token exists — the same fail-fast as an
        unknown role, rather than a cell rendered with an empty colour.
        """
        cell = self._cells[position]
        cell.setStyleSheet(
            f"{cell.styleSheet()}QLabel {{ color: {semantic_colour(token)}; }}"
        )

    def set_action_tone(self, position: int, tone: Tone) -> None:
        """
        @brief Recolours one action button's text and outline.

        @details `GHOST_BUTTON` is accent-coloured, which is right for the
        neutral row actions and wrong for the two that are not: a "Sync"
        reads as positive and a "Clear" as destructive. Same per-instance
        argument as `set_cell_tone` — and the same appended scoped rule, so
        the button keeps the role's chrome and only its colour moves.
        """
        button = self.action_buttons[position]
        colour = tone_colour(tone)
        button.setStyleSheet(
            f"{button.styleSheet()}"
            f"QPushButton {{ color: {colour}; border: 1px solid {colour}; }}"
        )
