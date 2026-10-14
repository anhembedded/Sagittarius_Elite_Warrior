"""`EPIC-039J` — the rows of a Grid's editor that exist because the venue has a position:
Direction, Leverage, the margin mode and the Liquidation read-out.

@details The rows are listed by the venue's profile (`VenueProfile`), so a market, a direction
or a margin mode is one more entry there and no widget names it. A Spot profile lists
none of them: the rows stay hidden, `config()` adds no key, and a Spot definition keeps the
seven keys and the bytes it always had.

The Liquidation row only words the guard's verdicts (`grid_liquidation.py`); it computes no
figure. Direction and leverage start where decision O4 put them (long, 2×) and are written
into the definition with the other parameters, so a Futures bot never falls back to the
legacy long-at-1 reading of a definition that names neither (`grid_params.py`).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QComboBox, QLabel, QSpinBox, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    VenueProfile,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_field_errors import (
    DIRECTION,
    LEVERAGE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_liquidation import (
    NOT_ESTIMATED,
    liquidation_lines,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

#: What a new Futures Grid's leverage starts at (decision O4: "UI starts at 2×"); the plan is
#: warned above `FuturesGridThresholds.leverage_warn` and refused above the ceiling.
DEFAULT_LEVERAGE = 2

#: The definition's keys for the two parameters (`GridParams.to_config`).
DIRECTION_KEY, LEVERAGE_KEY = "direction", "leverage"

#: The keys of the two read-only rows.
MARGIN_MODE, LIQUIDATION = "margin_mode", "liquidation"

#: What the editor labels the read-only rows (the two editable ones are in `FIELD_LABELS`).
ROW_LABELS: Mapping[str, str] = {
    MARGIN_MODE: "Margin mode",
    LIQUIDATION: "Liquidation (est.)",
}


class ExposureFields:
    """@brief The position-venue rows of one Grid editor, shown as the profile lists them."""

    def __init__(self) -> None:
        self.direction = QComboBox()
        self.direction.setObjectName("cmbGridDirection")
        self.leverage = QSpinBox()
        self.leverage.setObjectName("spinGridLeverage")
        self.leverage.setSuffix("×")
        self.margin_mode: QLabel = plain_label()
        self.margin_mode.setObjectName("lblGridMarginMode")
        self.liquidation: QLabel = plain_label()
        self.liquidation.setObjectName("lblGridLiquidation")
        self.liquidation.setWordWrap(True)
        self._profile: VenueProfile | None = None

    def read_only_rows(self) -> Iterable[tuple[str, QWidget]]:
        return ((MARGIN_MODE, self.margin_mode), (LIQUIDATION, self.liquidation))

    def visible_rows(self) -> dict[str, bool]:
        """Which rows the profile lists: all hidden until one is given."""
        profile = self._profile
        return {
            DIRECTION: profile is not None and len(profile.directions) > 1,
            LEVERAGE: profile is not None and profile.max_leverage > 1,
            MARGIN_MODE: profile is not None and bool(profile.margin_modes),
            LIQUIDATION: profile is not None and bool(profile.margin_modes),
        }

    def set_profile(self, profile: VenueProfile) -> None:
        self._profile = profile
        self.direction.clear()
        for direction in TradeDirection:
            if direction in profile.directions:
                self.direction.addItem(direction.value.capitalize(), direction.name)
        with QSignalBlocker(self.leverage):
            self.leverage.setRange(1, max(profile.max_leverage, 1))
            self.leverage.setValue(self._start_leverage())
        self.margin_mode.setText(
            ", ".join(mode.value.capitalize() for mode in sorted(profile.margin_modes))
        )
        self.liquidation.setText(NOT_ESTIMATED)

    def config(self) -> dict[str, str]:
        """`direction` and `leverage` for a venue with a position only: a Spot definition
        keeps exactly the keys it always had."""
        if not self.exposes_position:
            return {}
        return {
            DIRECTION_KEY: str(self.direction.currentData()),
            LEVERAGE_KEY: str(self.leverage.value()),
        }

    def show_config(self, config: Mapping[str, str]) -> None:
        """A saved definition's direction and leverage; the start (long, 2×) when it names
        none, as a new bot's rows start. Emits nothing."""
        if not self.exposes_position:
            return
        with QSignalBlocker(self.leverage):
            self.leverage.setValue(
                _int_or(config.get(LEVERAGE_KEY, ""), self._start_leverage())
            )
        index = self.direction.findData(config.get(DIRECTION_KEY, "").upper())
        self.direction.setCurrentIndex(max(index, 0))

    def show_liquidation(self, verdicts: tuple[Verdict, ...]) -> None:
        lines = liquidation_lines(verdicts)
        self.liquidation.setText(
            "\n".join(line.text for line in lines) if lines else NOT_ESTIMATED
        )

    @property
    def exposes_position(self) -> bool:
        """Whether the profile gave this editor a leverage to write."""
        return self._profile is not None and self._profile.max_leverage > 1

    def _start_leverage(self) -> int:
        return min(DEFAULT_LEVERAGE, self.leverage.maximum())


def _int_or(text: str, default: int) -> int:
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError):
        return default
