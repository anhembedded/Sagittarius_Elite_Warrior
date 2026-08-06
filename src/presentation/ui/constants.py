from enum import Enum


class UIMode(str, Enum):
    """
    @brief Defines the operational modes of the Trading UI.
    @details These modes map directly to the keys defined in `ui_matrix.json`.
    Using an Enum prevents magic string typos and ensures strict state transitions.
    """

    IDLE = "IDLE"  # System is idle, user can configure all parameters.
    LIVE = "LIVE"  # System is actively streaming market data, inputs are locked.
    LOCKED = "LOCKED"  # System is busy (e.g., loading historical data), everything is disabled.
    ERROR = "ERROR"  # System encountered an error, transition state before recovering to IDLE.
