# BUG-066: Dev Board UI Freeze When Opening Symbol Picker With Large Symbol List

- **Reported:** 2026-08-30
- **Severity:** High (UI Freeze > 5.0s detected by UIWatchdog)
- **Status:** ✅ Fixed 2026-08-30 (root-caused / reproduced / regression-tested / verified)
- **Component:** `ui/dashboard` (`DevBoardPanel`, `DashboardSymbolPickerDialog`, `SymbolPickerModal`)

---

## Symptom

When opening the Symbol Picker on Dev Board after connecting to Binance and loading 1,358 tradeable symbols, the entire application UI freezes completely for over 5 seconds. `UIWatchdog` detects and logs the thread hang:

```text
2026-08-30 16:33:47,394 - App - WARNING - 🚨 UI FREEZE DETECTED: Qt Main Thread unresponsive for 5.0s (Threshold: 5.0s).
Current Main Thread Stack Trace:
  File "src/presentation/ui/main_window.py", line 242, in <module>
    main()
  File "src/presentation/ui/app_bootstrapper.py", line 355, in main
    exit_code = runtime.app.exec()
  File "src/presentation/ui/screens/dashboard/dev_board_panel.py", line 402, in _open_symbol_picker
    self._symbol_picker.show()
  File "src/presentation/ui/components/symbol_picker/overlay.py", line 235, in showEvent
    self.refresh()
  File "src/presentation/ui/components/symbol_picker/overlay.py", line 250, in refresh
    self._rebuild()
  File "src/presentation/ui/components/symbol_picker/overlay.py", line 319, in _rebuild
    self._fill_grid(self._results_grid, rest)
  File "src/presentation/ui/components/symbol_picker/overlay.py", line 335, in _fill_grid
    card = SymbolCard(entry)
  File "src/presentation/ui/components/symbol_picker/symbol_card.py", line 61, in __init__
    row.addWidget(self._build_star(entry), 0, Qt.AlignmentFlag.AlignTop)
  File "src/presentation/ui/components/symbol_picker/symbol_card.py", line 108, in _build_star
    star.clicked.connect(lambda: self.favourite_toggled.emit(entry.symbol))

2026-08-30 16:33:47,781 - App - INFO - UI Thread recovered from freeze. Event loop responsive.
```

---

## Root Cause

`DevBoardPanel` (`src/presentation/ui/screens/dashboard/dev_board_panel.py`) was still using the legacy QtWidgets `SymbolPickerOverlay` (`src/presentation/ui/components/symbol_picker/overlay.py`).

`SymbolPickerOverlay` has no virtualization or pagination mechanism. When `ListAvailableSymbolsQuery` returns 1,358 symbols from Binance:
1. `_open_symbol_picker` calls `self._symbol_picker.show()`, triggering `showEvent` -> `refresh()` -> `_rebuild()`.
2. `_fill_grid` iterates synchronously over all 1,358 entries, instantiating a full `SymbolCard` widget for each entry.
3. Each `SymbolCard` instantiates 1 `QFrame`, 2 `QLayout`s, 2 `QLabel`s, 1 `StyledButton`, and computes CSS styles for `StyleRole.TABLE_CELL_STRONG`, `StyleRole.CAPTION`, and `StyleRole.GHOST_BUTTON`.
4. Over 8,000 QObjects and QWidgets are synchronously created and laid out into `QGridLayout` on the Qt Main Thread, freezing the UI for ~5.3 seconds.

---

## Fix

1. **Virtualized QML Modal:** Migrated `DevBoardPanel` to `DashboardSymbolPickerDialog` (subclassing `SymbolPickerModal`), hosting `SymbolPicker.qml` with virtualized `GridView(reuseItems: true)` via `DashboardSymbolPickerSource`.
2. **Offline Symbol Catalog:** Saved 1,358 tradeable symbols into `src/config/tradeable_symbols.json`. Created `ISymbolCatalogRepository` port and `JsonSymbolCatalogRepository` infrastructure adapter.
3. **Smart CQRS Query:** `ListAvailableSymbolsQuery` loads from local catalog cache in 0ms without hitting the network on app/picker startup.
4. **On-Demand Refresh:** Added a "Refresh" button (🔄) on `SymbolPicker.qml` to explicitly refetch symbols from Binance and update local cache with `force_refresh=True`.

---

## Regression Test

- `tests/unit/presentation/ui/screens/test_dev_board_panel.py::test_symbol_picker_handles_large_symbol_list_without_freezing`: Confirmed opening the picker with 1,358 symbols runs in < 50ms with zero UI freeze.
- `tests/unit/application/use_cases/test_list_available_symbols.py`: Confirmed local catalog cache returns symbols without calling exchange client, and `force_refresh=True` updates the catalog.
- `tests/unit/infrastructure/persistence/test_json_symbol_catalog_repository.py`: Tested JSON persistence and graceful recovery.
- `tests/unit/presentation/ui/qml/test_symbol_picker_modal_host.py`: Verified refresh button interaction.
