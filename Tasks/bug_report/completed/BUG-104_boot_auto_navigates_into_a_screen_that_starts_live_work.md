# BUG-104 — Launching the app can silently start a live market-data stream, no click required

**Reported date:** 2026-09-03
**Fixed date:** 2026-09-03
**Severity:** 🟡 P2 — no money at risk (real order placement stays gated behind the separate "Bật
giao dịch" toggle, off by default), but the app performs real, unrequested network activity the
instant it launches.
**Status:** ✅ Fixed — see §3.

---

## 1. Hiện tượng (Symptom)

User báo trực tiếp sau khi BUG-101 vừa merge: *"vừa mở app lên là live stream tự chạy, tại sao?
bug này mới fix rồi mà"*. Mở app lên, **chưa bấm gì cả**, màn Giao dịch (Trading) tự động hiện ra
và tự động chạy `SyncMarketDataCommand` + `StartLiveStreamCommand` — y hệt lớp lỗi `BUG-101` vừa
sửa, nhưng ở một màn khác.

## 2. Root cause

Hai tính năng, mỗi cái hợp lý khi đứng riêng, **kết hợp lại** thành lỗi:

1. `main_window.py` (`EPIC-010C`, đã có test kỹ từ trước) nhớ `last_route` — màn hình cuối cùng
   user đang mở — và tự động `switch_screen()` vào đúng route đó ngay lúc boot, không cần user
   bấm gì.
2. `TradingPresenter.__init__` (`EPIC-021I`) tự thiết kế "mở màn này ra là live luôn" — không có
   bước Start riêng, comment gốc ghi rõ: *"the chart is always live while this screen is open"* —
   tức construct xong presenter là sync + live stream chạy ngay.

Hai điều đó tự nó không sai: (1) là tiện ích hợp lý (nhớ màn hình cũ), (2) là quyết định thiết kế
có chủ đích cho MỘT màn hình cụ thể (khi user **thật sự** bấm vào Trading). Nhưng ghép lại: nếu
phiên trước user đang ở Trading, phiên sau **chỉ cần mở app lên** — không bấm gì — cũng đủ để (1)
tự nhảy vào Trading, và (2) coi việc đó y hệt "user vừa bấm vào Trading", chạy job thật ngay.

`BUG-101` không bắt được lỗi này vì phạm vi sửa/test của nó chỉ nhắm đúng `BackTestPresenter`'s
restore-form — không đụng gì tới `main_window.py`'s route-restore hay `TradingPresenter`. Bug này
là lỗi **tương tác giữa hai tính năng khác nhau**, không nằm trong 1 file test đã viết trước đó.

## 3. Fix

Người dùng quyết định hướng sửa (2 lựa chọn khác có thể, xem thảo luận trong phiên): **bỏ hẳn việc
nhớ route lúc boot** — mọi lần khởi động app đều vào đúng route mặc định (`dashboard`), bất kể
phiên trước đang ở màn nào. Giữ nguyên: nhớ geometry cửa sổ + trạng thái thu gọn sidebar (thuần
cosmetic, không có tác dụng phụ khi áp dụng). `TradingPresenter`'s "mở ra là live" giữ nguyên —
chỉ còn chạy khi user **tự tay** bấm vào Trading từ sidebar.

`src/presentation/ui/main_window.py`:
- Xoá `_ROUTE_KEY`/`last_route` khỏi `capture_state()` và `restore_state()`.
- Xoá `_known_routes()` (chỉ tồn tại để validate route restore, không còn cần).
- Xoá field `self._registry` (chỉ được dùng bởi `_known_routes()`).
- `self._current_route` luôn là `screen_registry.get_default_route()`, không bao giờ bị
  `restore_state()` ghi đè — `switch_screen()` cuối `__init__` luôn vào đúng màn mặc định.
- Docstring class thêm mục "BUG-104" giải thích quyết định.

## 4. Regression test (viết trước, xác nhận đỏ đúng lý do trước khi sửa)

`tests/integration/presentation/ui/test_main_window_state.py` — 3 test sửa lại đúng theo hợp đồng
mới (route không bao giờ ảnh hưởng), 1 test xoá (không còn ý nghĩa vì route không được đọc nữa):

- `test_restores_sidebar_and_geometry_but_never_the_route` — stored `last_route: "backtest"` +
  `sidebar_collapsed: True` → boot vẫn vào `"dashboard"`, sidebar vẫn collapsed.
- `test_boot_never_constructs_a_non_default_screen_even_with_a_stored_route` — stored
  `last_route: "trading"` → `TradingPresenter` **không được construct** ở boot (chứng minh đúng cơ
  chế lazy-loading, đúng bằng route thật gây ra bug report này, không chỉ đọc `_current_route`).
- `test_sidebar_toggle_survives_a_restart_but_the_route_resets_to_default` — round-trip thật qua
  restart: sidebar collapsed sống sót, route reset về `dashboard`.
- `test_capture_state_never_includes_the_route` — `"last_route" not in captured`.

Trước khi sửa: **3 failed** đúng lý do (`assert 'backtest' == 'dashboard'`,
`assert 'data_management' == 'dashboard'`, và presenter Trading vẫn được construct). Sau khi sửa:
5/5 xanh.

`mypy --config-file pyproject.toml --namespace-packages --explicit-package-bases src scripts` →
`Success: no issues found in 245 source files`. `ruff check`/`ruff format --check` sạch.
