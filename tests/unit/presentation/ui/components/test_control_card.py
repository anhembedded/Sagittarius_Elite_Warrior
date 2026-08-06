from Binace_Bot.src.presentation.ui.components.control_card import ControlCard


def test_control_card_initialization(qapp):
    card = ControlCard()
    assert card.objectName() == "TradingControlCard"

    # Assert defaults
    assert not card.stop_stream_button.isEnabled()
    assert card.start_stream_button.isEnabled()


def test_control_card_signals(qapp):
    card = ControlCard()

    # Track signal emissions
    load_emitted = False
    start_emitted = False
    stop_emitted = False

    def on_load():
        nonlocal load_emitted
        load_emitted = True

    def on_start():
        nonlocal start_emitted
        start_emitted = True

    def on_stop():
        nonlocal stop_emitted
        stop_emitted = True

    card.sig_load_clicked.connect(on_load)
    card.sig_start_clicked.connect(on_start)
    card.sig_stop_clicked.connect(on_stop)

    # Simulate clicks
    card.load_history_button.click()
    card.start_stream_button.click()

    # stop_stream_button is disabled by default, so clicking it won't emit a signal.
    # Enable it first to test the signal wiring.
    card.stop_stream_button.setEnabled(True)
    card.stop_stream_button.click()

    assert load_emitted
    assert start_emitted
    assert stop_emitted


def test_control_card_apply_ui_mode(qapp):
    card = ControlCard()

    matrix = {
        "main": {
            "IDLE": {"start_stream_button": True, "stop_stream_button": False},
            "LIVE": {"start_stream_button": False, "stop_stream_button": True},
            "ERROR": {"start_stream_button": True, "stop_stream_button": False},
        }
    }
    card.set_ui_matrix(matrix)
    from Binace_Bot.src.presentation.ui.constants import UIMode

    # Set active
    card.apply_ui_mode(UIMode.LIVE)
    assert not card.start_stream_button.isEnabled()
    assert card.stop_stream_button.isEnabled()

    # Set inactive
    card.apply_ui_mode(UIMode.IDLE)
    assert card.start_stream_button.isEnabled()
    assert not card.stop_stream_button.isEnabled()
