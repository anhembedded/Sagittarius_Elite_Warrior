# BOT-169 — The app tells the user about an error or an event one way, everywhere, never by printing it into a panel

**Status:** ✅ Done (2026-10-07)
**Board:** One `INotifier` port and one Qt presenter now tell the user about failures and events: a message box for a failed command, an inline message bar per mode for a background failure (one outage is one bar), a toast for events. Every module's error paths moved onto it, and a guard fails a UI file that puts an exception into a widget. Rule: `ui-presentation-rule.md` §10.
**Source:** the owner, 2026-10-07, on the Bots panel showing "502 Bad Gateway": *"mấy cái thông báo error, exception, hay info đều phải là box message hoặc là popup chứ gì, sao lại in trực tiếp lên khung UI. cái này không nằm ở epic, nhưng hãy tạo task hoặc bug doc trước"* (error, exception or info notices should be a message box or a popup; why are they printed straight into the UI frame? This is not in the epic, but file a task or bug document first.)
**Risk:** 🟡 — every module's error path changes; a wrong choice either hides failures or interrupts the user with dialogs
**Complexity:** M — one shared notification service and its presenter, then each module's error paths moved onto it
**Depends on:** None; [BUG-168](../bug_report/completed/BUG-168_an_exchange_error_page_is_rendered_as_html_in_the_bots_panel.md) is the defect that prompted it and can be fixed first

---

## 1. Context and problem
- Each panel writes its own failures into its own label. The Bots panel puts `str(exc)` in a status label (`src/modules/bots/ui/bots_screen/bots_view.py:114`, `bots_presenter.py:355`). The planner failure shows as a Plan verdict. The chart's messages go nowhere (`EPIC-034A`).
- One outage of the Spot Testnet on 2026-10-07 produced four failed reads within 50 ms. A modal dialog per failure would have opened four dialogs.
- `ui-presentation-rule.md` §10 requires only that errors name what failed and what to do, and that an alarm never lives only in the status bar. It does not say where a message appears.
- The owner asks for message boxes or popups instead of text printed into panels.

## 2. Acceptance criteria
- [x] A written rule in `ui-presentation-rule.md` §10 says which mechanism each kind of message uses (approved by the owner before code changed).
- [x] One notification service carries every user-facing error and notice: plain text, deduplicated, with the technical detail available on demand but never as the headline.
- [x] No panel shows an exception's text directly; a guard fails on a UI module that puts `str(exc)` or an exception into a widget.
- [x] A burst of the same failure (one outage, many reads) produces one message, not one per read.

## 3. Design
Approved by the owner on 2026-10-07 as proposed. It follows Microsoft's Windows guidance on error messages (`mess-error`) and notifications, and KDE's HIG on message boxes versus inline messages.

| Kind of message | Mechanism | Example |
| :--- | :--- | :--- |
| A command the user just ran failed and they must decide something | **Modal message box** (`QMessageBox`): what failed, what to do, Details… for the technical text | Start bot refused; order rejected; key refused on Apply |
| A background read or connection failed; the app keeps working and retries | **Inline message bar** at the top of the affected mode or panel (yellow or red), dismissible, with Retry and Details…; one bar per cause, never a stack | Spot Testnet unavailable (502); live chart could not connect |
| Something worth knowing happened while the user looked elsewhere | **Notification popup** (the system tray toast `BOT-018` already sends, or an in-app toast), plus a line in Output | A bot stopped on its stop loss; trading paused by a limit |
| Routine progress or state | **Status bar** or the Output dock only | Sync finished; 3 bots running |

**Why not a popup for everything:** a modal box for a background failure interrupts typing and stacks up during an outage (four boxes in 50 ms here). It also trains the user to click OK without reading, which hides the one message that matters, such as an order rejection.

**Mechanism:** an application-level `INotifier` port with `report_failure(kind, cause, detail)` and `notify(event)`, implemented once by a Qt presenter that picks the surface from the kind. Modules depend on the port, not on widgets. This follows `architecture-rule.md`'s ports and the existing `report_handler_failure` pattern.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `.claude/rules/ui-presentation-rule.md` §10 | the rule above, once approved |
| `src/core/contracts/` | the `INotifier` port |
| `src/presentation/ui/` | the presenter: message box, message bar, toast |
| each module's presenters | failures routed through the port; status labels for errors removed |
| `tests/unit/architecture/` | the guard on exception text in widgets |

## 5. Testing
Unit tests on the presenter for each kind, including deduplication of a burst. The guard with a probe. A booted test: an exchange outage yields one message bar and no dialog. Not run.

## Implementation notes (written when done)
- **Port and presenter:** `INotifier` (`src/core/contracts/i_notifier.py`) with `report_failure(FailureNotice)`, `clear_failure(cause)` and `notify(headline)`; the Qt `NotifierPresenter` (`src/presentation/ui/notifier.py`) picks the surface from the notice's `FailureKind`. It is bound before any screen is built (`install_notifier`) and adopts the window's modes afterwards (`adopt`); a headless run binds `LoggingNotifier`. Any thread may call it: delivery is queued to the UI thread.
- **Surfaces:** a failed command is a `QMessageBox` with the technical text behind its own Details; a background failure is a `MessageBar` in the mode's `ModeHost.message_bars` with Retry and Details…; a toast is the system notification where the platform has one and the status bar for ten seconds where it has not. The status bar stays for routine state.
- **Bursts:** one bar per failure. The same cause updates in place; a cause with the same technical text, or failing within `BURST_WINDOW_S` (3 s) of the last one the bar took, joins that bar ("and 3 more"); the bar goes when every cause on it recovered. Proven booted: `tests/integration/presentation/ui/test_exchange_outage_is_one_message.py` switches the fake server to an HTML `502` and finds one bar, no box and no page in any label.
- **Guard:** `test_ui_never_shows_an_exception.py` (AST): in a UI file, no `str`/`repr`/f-string/`%`/`+`/`.format`/traceback of an exception name outside a logging call, a `raise` and `failure_detail(...)`. Two named exemptions (the crash dialog and its hook). It does not see text that reaches a widget through a name it cannot know is an exception's.
- **Migration:** bots, trading (desk, market, settings), backtesting, market data, the live chart and the indicator runner. Worker threads carry `failure_detail(exc)` as `detail`; the UI thread tells the notifier with a headline the author wrote. The unknown-outcome order of `BUG-170` is its own headline ("may be live").
- **Not changed:** `UiToastNotificationChannel` (`BOT-018`, the Telegram fan-out's UI channel) still writes to the status bar; unifying it with `notify()` is a follow-up. A command box opened while Tools → Options is showing is parented to the main window; checked reachable offscreen, not on a real Windows or macOS desktop.
