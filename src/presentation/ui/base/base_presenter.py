from PySide6.QtCore import QObject
from abc import abstractmethod
from typing import Any
from sagittarius_engine import App


class BasePresenter(QObject):
    """
    @brief Abstract Base Class for all Presenters in the application.
    @details Enforces a strict initialization contract and lifecycle hooks.
             Inherits from QObject to allow PyQt Signal/Slot definitions.
    """

    def __init__(self, view: Any, app: App):
        # QObject must be initialized first
        super().__init__()

        self.view = view
        self.app = app

        # Child classes MUST call self._connect_ui_signals() and self._connect_engine_events()
        # at the end of their own __init__ methods to avoid Template Method Initialization Trap.

    @abstractmethod
    def _connect_ui_signals(self) -> None:
        """
        @brief Abstract method to connect UI actions (e.g. button clicks) to Presenter slots.
        """
        raise NotImplementedError("Subclasses must implement _connect_ui_signals")

    @abstractmethod
    def _connect_engine_events(self) -> None:
        """
        @brief Abstract method to connect Sagittarius Engine EventBus to Presenter callbacks.
        """
        raise NotImplementedError("Subclasses must implement _connect_engine_events")
