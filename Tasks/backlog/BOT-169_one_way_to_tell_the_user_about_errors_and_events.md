# BOT-169 — The app tells the user about an error or an event one way, everywhere, never by printing it into a panel

**Status:** 🔵 Backlog
**Priority:** P2
**Board:** Errors, exceptions and notices are written straight into panels as raw text (the Bots panel showed an exchange's HTML error page). Decide one mechanism for each kind of message and apply it across the app.
**Source:** the owner, 2026-10-07, on the Bots panel showing "502 Bad Gateway": *"mấy cái thông báo error, exception, hay info đều phải là box message hoặc là popup chứ gì, sao lại in trực tiếp lên khung UI. cái này không nằm ở epic, nhưng hãy tạo task hoặc bug doc trước"* (error, exception or info notices should be a message box or a popup; why are they printed straight into the UI frame? This is not in the epic, but file a task or bug document first.)
**Risk:** 🟡 — every module's error path changes; a wrong choice either hides failures or interrupts the user with dialogs
**Complexity:** M — one shared notification service and its presenter, then each module's error paths moved onto it
**Depends on:** None; [BUG-168](../bug_report/incomplete/BUG-168_an_exchange_error_page_is_rendered_as_html_in_the_bots_panel.md) is the defect that prompted it and can be fixed first

---

## 1. Context and problem
- Each panel writes its own failures into its own label. The Bots panel puts `str(exc)` in a status label (`src/modules/bots/ui/bots_screen/bots_view.py:114`, `bots_presenter.py:355`). The planner failure shows as a Plan verdict. The chart's messages go nowhere (`EPIC-034A`).
- One outage of the Spot Testnet on 2026-10-07 produced four failed reads within 50 ms. A modal dialog per failure would have opened four dialogs.
- `ui-presentation-rule.md` §10 requires only that errors name what failed and what to do, and that an alarm never lives only in the status bar. It does not say where a message appears.
- The owner asks for message boxes or popups instead of text printed into panels.

## 2. Acceptance criteria
- [ ] A written rule in `ui-presentation-rule.md` §10 says which mechanism each kind of message uses. The owner approves it before code changes.
- [ ] One notification service carries every user-facing error and notice: plain text, deduplicated, with the technical detail available on demand but never as the headline.
- [ ] No panel shows an exception's text directly; a guard fails on a UI module that puts `str(exc)` or an exception into a widget.
- [ ] A burst of the same failure (one outage, many reads) produces one message, not one per read.

## 3. Design
Proposed, pending the owner's decision. It follows Microsoft's Windows guidance on error messages (`mess-error`) and notifications, and KDE's HIG on message boxes versus inline messages.

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
Not started.
