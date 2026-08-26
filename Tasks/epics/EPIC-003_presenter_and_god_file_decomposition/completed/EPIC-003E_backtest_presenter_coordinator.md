# EPIC-003E — `BacktestPresenter` → Coordinator Pattern

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** ✅ Xong 2026-08-26 — 6/6 coordinator; presenter **2.803 → 2.135** dòng
**Phụ thuộc:** [`003A`](EPIC-003A_shared_action_ownership_tracker.md) ✅ · [`003B`](EPIC-003B_data_management_coordinator_pilot.md) ✅ (kiểm tra trước khi bắt đầu, đúng ràng buộc §1)

---

## Kết quả

| | Trước | Sau |
| :--- | ---: | ---: |
| `backtest_presenter.py` | **2.803** dòng | **2.135** |
| Coordinator | 0 | **6 file, 1.473 dòng** |
| Test riêng cho coordinator | 0 | **53 test, 1.170 dòng** |

| Coordinator | Dòng |
| :--- | ---: |
| `execution_coordinator.py` | 357 |
| `chart_render_coordinator.py` | 271 |
| `indicator_coordinator.py` | 256 |
| `strategy_config_coordinator.py` | 246 |
| `data_sync_coordinator.py` | 205 |
| `trade_log_coordinator.py` | 108 |

## Ranh giới: FSM và action-ownership **ở lại presenter**

Đây là quyết định xuyên suốt, không phải cho từng ca. `003B` để presenter giữ *FSM
transitions, signal binding, action ownership* — nên mọi thứ sau **không** chuyển đi:

- `_on_run_backtest`, `_start_backtest_run`, `_on_cancel_backtest`, `_start_sync_for_config`
- Toàn bộ `*_for_action` — cửa quyết định một callback đến muộn còn thuộc action hiện tại không
- Qt `@Slot` + `@safe_ui_action`: giữ nguyên chữ ký có decorator trên presenter, thân hàm mới delegate

Hệ quả trực tiếp: coordinator chạy **ngoài luồng Qt**, nơi **không được** đụng FSM hay tracker.

## Yêu cầu §4 — không đổi một assertion nào

Đạt. Ba method giữ **nguyên chữ ký** vì test gọi thẳng:

| Method | Số chỗ test gọi |
| :--- | ---: |
| `_run_backtest` | **67** |
| `_run_sync` | 9 |
| `_run_chart_preview` | 3 |

Cùng lý do: `_all_trades`, `_strategy_params`, `_market_metadata_cache`, `_active_preview_id`
vẫn là thuộc tính của presenter — test gán thẳng vào chúng.

## Bài học lặp lại **ba lần** — đủ để thành luật

> **Thứ gì test có thể thay trên presenter thì phải đọc/gọi MUỘN, qua presenter — không bind
> lúc khởi tạo.**

| Lần | Chỗ sai | Test bắt được |
| :-: | :--- | :--- |
| 1 | Nhận `list[Trade]` một lần thay vì `get_all_trades()` | (tránh được nhờ đọc test trước) |
| 2 | `get_market_metadata=self._market_metadata_cache.get` | 2 assertion `UNVERIFIED_MISSING != VERIFIED` |
| 3 | `set_strategy_lines_visible` bind vào `IndicatorCoordinator` | test thay `presenter._on_ema_toggled` bằng Mock |

## Trùng lặp thật đã gỡ (không phải đếm dòng)

- **11 bản sao** `self.view.chart_cards[0] if self.view.chart_cards else None` → một
  `_first_chart_card()`. Là **method**, không cache: host dựng lại mỗi lần đổi chart mode, giữ
  tham chiếu là ôm một C++ object đã `deleteLater()` — chính hình dạng `BUG-013`.
- **Đuôi "rồi chạy lại"** lặp **byte-for-byte** ở cả hai save handler → `_start_run_after_config_save`.
- **Hai danh sách tham số** dựng `RunStaticBacktestCommand`/`RunHistoricalTickBacktestCommand`
  bảo trì song song → một dict `shared`. Thêm field cho một cái mà quên cái kia là lỗi **không
  ai bắt được**; giờ có test khẳng định hai command mang cùng bộ field chung.
- **Ba handler** region/info/marker chỉ khác label + method + list → một `_draw_via_host`.
- **12 nhánh** `if "x" in props` chép broker property → một bảng (key, attribute, coercion).

## Lỗi thật bị cổng bắt, không phải bằng mắt

1. **`drawn_count` là keyword-only.** Gọi positional → `TypeError` **bên trong Qt event loop**,
   5 test đỏ nhưng chỉ báo *"Exceptions caught in Qt event loop"*. Đáng nhớ: sai chữ ký sau một
   Qt slot **không** hiện ra như một failure bình thường.
2. **Dựng coordinator quá sớm** trong `__init__` — trước chỗ gán `_view_model` 60 dòng. Mọi test
   chạm presenter chết vì `AttributeError`.
3. **Ba lần đoán sai đường dẫn import** (`SyncMarketDataCommand`, `BacktestRangeCoverage`,
   `map_klines`). Collection đỏ ngay — cách phát hiện rẻ nhất.
4. **`ruff check` trên riêng thư mục coordinator xanh trong khi cổng đỏ**: file test mới nằm
   ngoài phạm vi đó. Cổng quét `src tests tools`, và **cổng mới là thứ quyết định**.

## Fake phải thành kiểu thật mới có nghĩa

Ba lần: `ScriptInput`, `TimeFrame`, `BacktestRunConfig`. Cả hai run command là **pydantic
model** validate field thật, nên `SimpleNamespace` biến mọi test thành validation error thay vì
chạy đúng nhánh nó viết ra để kiểm.

## Test không rỗng — đã chứng minh bằng tiêm lỗi

**16 lỗi tiêm**, mỗi cái đỏ đúng chỗ phải đỏ, rồi xanh lại khi khôi phục. Vài cái đáng kể:

- Bỏ reset runner khi dựng lại host → hình dạng `BUG-013`
- Realtime dùng `timeframe` thay `tick_resolution` → đúng bẫy `BOT-076`
- Bỏ hàng rào `preview_id` → query cũ đè lên kết quả mới
- Export toàn bộ thay vì phần đang lọc
- Bỏ nhánh cancel → FSM kẹt `SYNCING` vĩnh viễn

Một assertion tự viết ra đã **rỗng nghĩa** và được sửa: kiểm `UNVERIFIED_MISSING` trên view
model mới tinh sẽ xanh dù hàm không làm gì — đó vốn là giá trị mặc định.

## Nghiệm thu

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → **`RESULT: PASS`** sau **mỗi** commit
trong 6 commit. Lần cuối: **2.345 passed, 4 skipped**; Lint/Format/Mypy/Tests/Sanity/Run-log
đều xanh; grep file log sạch `FAILED|Traceback|ResourceWarning`.

## Còn lại

Presenter vẫn **2.135 dòng / 119 method** — trên ngưỡng 400. Phần còn lại **phần lớn là FSM,
action-ownership, signal binding và `__init__`**, tức đúng thứ `003B` giao cho presenter giữ.
Muốn giảm tiếp phải chẻ chính những thứ đó, và đó là quyết định kiến trúc khác, không phải
"chỉ di chuyển" — ứng viên cho `003F`.
