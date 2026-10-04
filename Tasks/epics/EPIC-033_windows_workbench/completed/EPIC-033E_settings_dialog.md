# EPIC-033E — One Options dialog (Tools → Options) with sections, OK, Cancel and Apply

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟡 — a shared surface changes shape
**Complexity:** M
**Epic:** [EPIC-033](../README.md)
**Depends on:** Engine W4; 033C

---

## 1. Context and problem
Settings is a sidebar route (`src/shell/settings/settings_screen.py`) rendering a scrolling page of group boxes, each with its own Save `StyledButton` (`trading_settings_view.py:238`, `market_data_settings_view.py:170`), and no Cancel. HLD §11.2 specifies one dialog, Qt Creator's Options shape.

## 2. Acceptance criteria
- [x] Tools → Options opens one `QDialog` titled "Options": a section list on the left, the section page on the right, a `QDialogButtonBox` with OK, Cancel and Apply in the platform's order. Its shortcut is `QKeySequence.Preferences` (empty on Windows, as the platform defines), never a hard-coded Ctrl+,.
- [x] Sections are contributed as pages implementing the Engine's options-page contract (apply, revert, dirty). They come through `contribute_options_page`, not `Place.SETTINGS_SECTION`; see the notes.
- [x] Cancel discards every unapplied change; Apply is enabled only when a page is dirty; a page that fails validation keeps OK disabled and says why.
- [x] The settings route and both Save buttons are deleted.

## 3. Design
Windows desktop guidance names this Tools → Options with no ellipsis (MS uxguide `cmd-menus`, `win-dialog-box`); Visual Studio and Qt Creator follow it (P5).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/shell/settings/` | Route deleted; dialog wiring |
| `src/modules/trading/ui/settings/`, `src/modules/market_data/ui/settings/` | Pages implement the contract |

## 5. Testing
Unit: each page's apply/revert/dirty. Integration: open, edit, Cancel leaves config unchanged; Apply writes it.

## Implementation notes (written when done)
- **A page is contributed, not placed.** `IContributionRegistry.contribute_options_page(OptionsPageContribution(contributor_id, order, factory))` replaces `Place.SETTINGS_SECTION`:
  - the dialog drives a page (apply, revert, dirty), so a contribution names a page, the way `ScreenContribution` names a screen, rather than a widget for a surface;
  - `Place.SETTINGS_SECTION`, the `settings` surface, `SettingsSurface`, `build_settings_surface`/`fill_settings_surface` and `src/shell/settings/` are deleted;
  - the modules name their page factory through a `Deferred`, so `contribute()` still imports no widget (`test_module_contribution_laziness.py`).
- **The page contract** is `core/contracts/i_options_section.py`, a `Protocol` (reason (a): the implementers are presenters, `QObject`s). It is the Engine's `IOptionsPage` restated, because `core/contracts` imports nothing from the Engine but the Shared Kernel.
- **One base for every page.** `support/ui_kit/options_section_presenter.py` holds the edit tracking the Trading and Market Data pages had identical:
  - the saved fields, `is_dirty`, `apply` (marks the page saved only when the save reached disk), `revert`, the change listener, and the title and widget;
  - a page supplies `_load_from_config`, `_current_fields`, `_save`, `_change_signals` and, if it has a rule, `validation_message`;
  - it uses `@abstractmethod` without `ABC`, the `BaseFeed`/`RowTableModel` pattern;
  - without it, the duplication ratchet rose 64 → 70; with it, it falls to **61**.
- **Pages, in order:** Trading (order 10), Market Data (order 20), then the shell's Developer page. They are assembled by `shell/options_pages.py`, which the composition root calls.
- **Validation:**
  - Market Data refuses empty Default Symbols.
  - Trading refuses a venue change while any venue is live (`BOT-125`), both in `validation_message()`, which keeps OK disabled, and in `_save()`, which covers a session switched on in between.
- **Guards touched:**
  - the preview guard no longer scans `src/shell`, which holds no presenter now;
  - `test_engine_port_calls_are_real.py` recognises presenters built on `OptionsSectionPresenter`, since the two settings presenters were its only subjects;
  - the shrink-only baselines fell: stock controls, god files, ruff debt, presenter duplication, and packages without a preview.
- **Proof:**
  - `tests/unit/support/ui_kit/test_options_section_presenter.py` covers the base; a mutation that marks a failed save as saved goes red.
  - `tests/integration/presentation/ui/test_options_pages.py` builds the pages from the real modules' contributions: the page order; an edit typed into a real field reaches `user_config.json` only on Apply; Cancel leaves the file and puts the value back; an empty field keeps OK disabled and names the page and the problem. Disconnecting the change listener turns it red.
- **A failed save (PR #348 review):** a page writes the live config before the disk write. When the write fails, `OptionsSectionPresenter.apply()` has the page put back what it wrote (`_undo_unsaved_writes`), so nothing unsaved stays in memory and Cancel reverts to what is really saved.
- **Engine follow-up, `BUG-018` (Engine PR anhembedded/Sagittarius_Engine#229, approved by the user 2026-10-04):**
  - The Engine's `OptionsDialog.accept()` closed after a failed apply. Until the fix is pinned, OK closes and the page reopens showing its unapplied edit and the error.
  - `show_options()` kept every dialog it built alive.
  - The fix is pinned by an `engine.ref` bump in the next Elite PR (P4c).
- **Not done here:** the `settings` icon stays in the required-assets list, unused since the route went.
