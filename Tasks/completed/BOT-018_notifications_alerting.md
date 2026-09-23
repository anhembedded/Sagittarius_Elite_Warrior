# Nhiệm vụ: Notifications / Alerting

**Status:** ✅ **Done (2026-09-23)** — see §5 for what actually shipped and where it diverges from §3's original action items.

## 1. Mục tiêu (Objective)
Cảnh báo người dùng khi có sự kiện quan trọng xảy ra trong lúc app chạy nền (sync lỗi, WebSocket stream mất kết nối, phát hiện gap dữ liệu) — hiện tại các lỗi này chỉ nằm trong log file, dễ bị bỏ sót nếu người dùng không mở app.

## 2. Mô tả (Description)
Tận dụng `IEventBus` đã có sẵn (dùng để phát `MarketTickEvent`, `BulkSyncEvents`...): thêm một `NotificationEventHandler` lắng nghe các sự kiện lỗi/cảnh báo hiện có và mới, hiển thị toast/banner trong UI, đồng thời hỗ trợ gửi qua kênh ngoài (Telegram Bot) khi app chạy headless/CLI.

## 3. Các bước thực hiện (Action Items)
- [ ] Rà soát các event hiện có (`BulkSyncEvents`, WebSocket reconnect trong `binance_websocket_service.py`) — bổ sung event còn thiếu nếu cần (vd `StreamDisconnectedEvent`, `DataGapDetectedEvent`) mà không phá vỡ hợp đồng hiện tại.
- [ ] `INotificationChannel` (port) với 2 implementation ban đầu: `UiToastNotificationChannel` (banner trong `MainWindow`/`DashboardView`) và `TelegramNotificationChannel` (dùng Bot Token từ config, chỉ kích hoạt nếu được cấu hình).
- [ ] `NotificationEventHandler` đăng ký qua `IEventBus`, map event → message, gọi channel(s) tương ứng.
- [ ] Cấu hình bật/tắt kênh Telegram qua `user_config.json` (`notifications.telegram.bot_token`, `notifications.telegram.chat_id`) — đọc qua `IConfig`, không hard-code.
- [ ] Unit test cho `NotificationEventHandler` (mock channel, assert đúng message cho từng loại event) theo `.claude/rules/testing-rule.md`.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Không log/lưu Bot Token ra ngoài `user_config.json`.
- Lỗi gửi Telegram (mất mạng, token sai) không được làm crash luồng chính — bắt exception cục bộ trong channel, chỉ log cảnh báo.
- Cân nhắc rate-limit/debounce để tránh spam thông báo khi 1 sự kiện lỗi lặp lại liên tục (vd reconnect loop).

---

## 5. Implementation notes (what actually shipped)

**Events wired — 3 real ones, no new event invented.** `BulkSyncProgressEvent`
(`has_error=True`), `UiActionFailedEvent` and `TaskFailed` already exist and
already publish everywhere the task's own §3 first bullet asks to "review" —
`WebSocket reconnect`/`gap-detected` events it also suggested
(`StreamDisconnectedEvent`/`DataGapDetectedEvent`) do not exist anywhere in
the codebase and were **not** added: inventing a new event with no real
publisher would be dead code, and this task's real gap was the missing
*subscriber*, not a missing event.

**`SystemFailureLog` (`BUG-126`) already logs `UiActionFailedEvent`/
`TaskFailed` at `ERROR`.** `NotificationEventHandler`
(`src/shell/notification_event_handler.py`) is a second, independent
subscriber to the same two events (a bus supports more than one), plus the
sync-error event neither of them covered — it does not replace or duplicate
the log line, it adds the UI/Telegram escalation the task actually asks for.
Message text for the two shared events is read from
`system_error_report.py`'s existing `from_ui_action_failed`/
`from_task_failed().summary` rather than re-derived.

**`INotificationChannel`** (`src/core/contracts/i_notification_channel.py`) —
one `send(message: str) -> None` method, mirroring `IEventPublisher`'s
"fire-and-forget, an implementation that cannot deliver must report the
failure itself" contract.

**`UiToastNotificationChannel`** (`src/presentation/ui/`) — `QMainWindow.
statusBar().showMessage(...)`, not a new hand-drawn toast widget:
`ui-presentation-rule.md` §1 names `QStatusBar` as exactly the standard part
for "temporary status/notification text", and no app-wide banner surface
existed to reuse or extend.

**`TelegramNotificationChannel`** (`src/infrastructure/notifications/`) —
stdlib `urllib.request` rather than adding `requests`/`httpx`: neither is an
existing dependency, and `commit-rule.md` §3 requires prior user confirmation
to add one, which a single fixed-endpoint POST does not justify asking for.
Reads `ConfigKeys.NOTIFICATIONS_TELEGRAM_BOT_TOKEN`/`_CHAT_ID` fresh on every
`send()`; either empty makes `send()` a silent no-op (§3's "chỉ kích hoạt nếu
được cấu hình"). Never logs the token — verified by
`test_send_logs_a_warning_on_delivery_failure_without_leaking_the_token`.

**Wiring** — `NotificationEventHandler` is constructed once in
`composition_root.py::create_app()` (the one place both entry points pass
through, same reasoning as `SystemFailureLog`) with the Telegram channel
already attached, so the headless/CLI entry point gets Telegram delivery
with zero GUI dependency. The UI channel is added afterwards, in
`app_bootstrapper.py`, once `MainWindow` exists — the same two-phase
"construct now, wire the window-dependent part later" pattern already used
there for `INavigationService`.

**Debounce, deliberately minimal**: only the immediately-previous message is
remembered, and an identical repeat is dropped — enough to stop a tight
reconnect loop from spamming the exact same line, not a time-windowed rate
limiter nothing here has asked for yet (`architecture-rule.md` §7.2.1).

**Tests**: `tests/unit/shell/test_notification_event_handler.py` (8 cases —
the real graph from `create_app()` has a live subscriber for all three event
types, one test per event → message mapping, the has_error=False sync step
notifies nobody, debounce suppresses an identical repeat but not a genuinely
different one, a channel that raises does not stop the remaining channels or
crash); `tests/unit/infrastructure/notifications/
test_telegram_notification_channel.py` (4 cases — unconfigured/partially
configured is a no-op, a configured send posts the right URL/JSON body
(`urlopen` mocked, never a real network call), a delivery failure logs a
warning without the token); `tests/unit/presentation/ui/
test_ui_toast_notification_channel.py` (2 cases — the status bar shows the
message, a second message replaces the first).

**Verification**: `ruff check`/`ruff format --check` clean (three genuine
S105/S310/S107 false positives — a config key name, a fixed `https://`
template, a test fixture value — each closed with a scoped `# noqa` and
rationale, the same pattern already used elsewhere in this codebase for the
identical false-positive classes) plus one real `BLE001` at the
`NotificationEventHandler` fan-out boundary, `# noqa`'d with the same
rationale the module docstring states. `tests/unit/shell` +
`tests/unit/infrastructure` + `tests/unit/presentation/ui/
test_ui_toast_notification_channel.py`: 136 passed;
`tests/unit/architecture`: 440 passed (the bus-subscriber-is-constructed
guard and the module-boundary guards both accept the new wiring);
`tests/sanity`: 31 passed, confirming boot stays clean through both new
composition-root and `app_bootstrapper` lines (a stray `ResourceWarning: gc:
5 uncollectable objects at shutdown` is pre-existing — reproduced identically
on the pre-change tree via `git stash`, unrelated to this change). `mypy`
(`src` + `scripts`, this repo's own invocation): zero errors on every new
file; `composition_root.py`/`app_bootstrapper.py` (both touched, neither
excluded) show the same 3 pre-existing errors as before this change, at
shifted line numbers only.
