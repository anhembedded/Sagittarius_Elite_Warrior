"""The shared "choose a trading pair" dialog and the pure logic behind it.

Capability: Choose a trading pair, with favourites and recents
    Also: symbol picker, pair chooser, ticker selector, market combo, symbol field
    Use: SymbolPickerOverlay, ISymbolPickerSource
    User: src/modules/bots/ui/bots_screen/new_bot_dialog.py
    Status: stable
"""

from .filtering import (
    QUOTE_ANY,
    QUOTE_FIAT,
    FilterState,
    Scope,
    SymbolEntry,
    apply_filter,
    available_quotes,
    build_entries,
    partition_favourites,
)
from .i_symbol_picker_source import ISymbolPickerSource
from .overlay import RECENT_LIMIT, SymbolPickerOverlay
from .preferences import SymbolPreferences, find_symbol_preferences
from .quote_asset import CRYPTO_QUOTES, FIAT_QUOTES, SymbolParts, split_symbol
from .symbol_list_reader import SymbolListReader
from .symbol_table_model import SymbolTableModel

__all__ = [
    "CRYPTO_QUOTES",
    "FIAT_QUOTES",
    "QUOTE_ANY",
    "QUOTE_FIAT",
    "RECENT_LIMIT",
    "FilterState",
    "ISymbolPickerSource",
    "Scope",
    "SymbolEntry",
    "SymbolListReader",
    "SymbolParts",
    "SymbolPickerOverlay",
    "SymbolPreferences",
    "SymbolTableModel",
    "apply_filter",
    "available_quotes",
    "build_entries",
    "find_symbol_preferences",
    "partition_favourites",
    "split_symbol",
]
