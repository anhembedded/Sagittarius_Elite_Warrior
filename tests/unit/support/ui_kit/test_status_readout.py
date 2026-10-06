"""`status_readout`: a read-out that fits a status bar (`EPIC-033N`)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QStatusBar
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_readout import status_readout
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    ReadoutForm,
)

_SPECS = (ColumnSpec("records", "Records", ColumnKind.QUANTITY),)


def test_a_status_readout_is_no_taller_than_a_status_bar_label(qapp):
    label_bar = QStatusBar()
    label_bar.addPermanentWidget(QLabel("Records: 1,250"))
    form = status_readout(_SPECS)
    form_bar = QStatusBar()
    form_bar.addPermanentWidget(form)

    assert form_bar.sizeHint().height() == label_bar.sizeHint().height()
    # The Engine's form unmodified is what the helper replaces: red there.
    plain = QStatusBar()
    plain.addPermanentWidget(ReadoutForm(_SPECS))
    assert plain.sizeHint().height() > label_bar.sizeHint().height()


def test_a_status_readout_writes_through_the_application_formatter(qapp):
    form = status_readout(_SPECS)

    form.set_values({"records": 1250})

    assert form.value_text("records") == "1,250"
