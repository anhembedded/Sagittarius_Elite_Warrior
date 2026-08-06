from PySide6.QtCore import QObject, Signal
from Binace_Bot.src.presentation.ui.utils.ui_safeguard import safe_ui_action


class MockFSM:
    def __init__(self):
        from Binace_Bot.src.presentation.ui.constants import UIMode

        self.state = UIMode.IDLE
        self.history = [self.state]

    def transition_to(self, state):
        self.state = state
        self.history.append(state)


class MockView:
    class MockControlCard:
        def __init__(self):
            from Binace_Bot.src.presentation.ui.constants import UIMode

            self.mode = UIMode.LIVE

        def apply_ui_mode(self, mode):
            self.mode = mode

    def __init__(self):
        self.control_card = self.MockControlCard()


class MockPresenter(QObject):
    ui_log_signal = Signal(str)

    def __init__(self, with_fsm=False, with_view=False):
        super().__init__()
        self.last_log = None
        self.ui_log_signal.connect(self._on_log)
        if with_fsm:
            self.fsm = MockFSM()
        if with_view:
            self.view = MockView()

    def _on_log(self, msg):
        self.last_log = msg

    @safe_ui_action
    def success_action(self):
        return "SUCCESS"

    @safe_ui_action
    def failing_action(self):
        raise ValueError("Intentional crash")


def test_safe_ui_action_success():
    presenter = MockPresenter()
    assert presenter.success_action() == "SUCCESS"
    assert presenter.last_log is None


def test_safe_ui_action_catches_exception():
    presenter = MockPresenter()
    presenter.failing_action()
    assert "Intentional crash" in presenter.last_log
    assert "failing_action failed" in presenter.last_log


def test_safe_ui_action_fsm_recovery():
    from Binace_Bot.src.presentation.ui.constants import UIMode

    presenter = MockPresenter(with_fsm=True)
    assert presenter.fsm.state == UIMode.IDLE

    presenter.failing_action()

    # Should transition to ERROR then IDLE
    assert presenter.fsm.history == [UIMode.IDLE, UIMode.ERROR, UIMode.IDLE]
    assert presenter.fsm.state == UIMode.IDLE


def test_safe_ui_action_fallback_recovery():
    from Binace_Bot.src.presentation.ui.constants import UIMode

    presenter = MockPresenter(with_view=True)
    assert presenter.view.control_card.mode == UIMode.LIVE

    presenter.failing_action()

    # Should unlock UI via fallback
    assert presenter.view.control_card.mode == UIMode.IDLE
