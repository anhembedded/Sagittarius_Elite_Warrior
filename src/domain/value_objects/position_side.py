from enum import Enum


class PositionSide(str, Enum):
    """
    @brief Which direction an open `PaperExchange` position bets on (BOT-050).
    """

    LONG = "long"
    SHORT = "short"
