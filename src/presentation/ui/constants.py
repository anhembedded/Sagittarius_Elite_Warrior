from enum import Enum


class UIMode(str, Enum):
    """
    @brief Defines the operational modes of the Trading UI.
    @details Every screen's FSM (BasePresenter) transitions through these
    values; each QML screen's ViewModel mirrors the current one as a
    `uiMode` string property, which the QML binds `enabled:`/`visible:`
    states against directly (e.g. `enabled: viewModel.uiMode !== "LOCKED"`).
    Using an Enum prevents magic string typos and ensures strict state
    transitions.
    """

    IDLE = "IDLE"  # System is idle, user can configure all parameters.
    LIVE = "LIVE"  # System is actively streaming market data, inputs are locked.
    LOCKED = "LOCKED"  # System is busy (e.g., loading historical data), everything is disabled.
    ERROR = "ERROR"  # System encountered an error, transition state before recovering to IDLE.
    SCANNING = "SCANNING"  # System is scanning database status.
    SYNCING = "SYNCING"  # System is syncing market data.
    CLEARING = "CLEARING"  # System is clearing local data.


#: Default maximum log entries retained in LogListModel before trimming oldest lines.
DEFAULT_LOG_MAX_ENTRIES: int = 500
