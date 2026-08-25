# EPIC-007E — Elite: tầng `components/` dùng chung, cắt import chéo màn hình

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Elite_Warrior` · **Trạng thái:** ✅ Xong — 2026-08-25
**Phụ thuộc:** `007B`, `007C`, `007D` — đã xong

---

## Phạm vi

Tầng giữa còn thiếu: thứ dùng ở ≥2 màn **nhưng mang tên nghiệp vụ**, nên không được lên Engine.

| Lớp | File | Kế thừa | Thay cho |
| :--- | :--- | :--- | :--- |
| `ChartCard` | `components/chart_card/chart_card.py` | `Card` (engine) | đang kế thừa `BaseCard` của Elite |
| `TimeRangeCard` | `components/time_range_card.py` | `Card` | `data_management_widgets.TimeRangeCardWidget` |
| `SymbolPickerOverlay` | `components/symbol_picker_overlay.py` | `PickerOverlay` | `data_management_widgets.SymbolPickerDialog` |
| `TradeSideBadge` | `components/trade_side_badge.py` | `Badge` | `_side_badge` trong `_TradeLogRowWidget` |

## Yêu cầu

1. **Xoá `components/base_card.py`.** `BaseCard` là bản trùng lặp của engine's `Card` (cùng
   cấu trúc header/body/footer) và docstring của nó nói "style qua QSS `#base_card`" — **file
   QSS đó đã bị xoá từ `EPIC-005B`**, nên `BaseCard` hiện không được style bởi bất cứ thứ gì.
   Consumer duy nhất là `ChartCard`; chuyển nó sang engine's `Card` rồi xoá file.
2. **Cắt đứt 3 import chéo màn hình.** Sau task này, không file nào trong
   `screens/<A>/` được import từ `screens/<B>/`:
   - `backtest_top_panel.py:29` → `AppProgressBarWidget` (lấy từ DataMgmt)
   - `backtest_trade_logs_panel.py:31` → `LogPanelWidget` (lấy từ DataMgmt)
   - `dev_board_panel.py:33` → `LogPanelWidget` (lấy từ DataMgmt)

   Cả 3 chuyển sang dùng `LogPanel` / `StyledProgressBar` của Engine (`007B`, `007C`).
3. **Guard mới ở Elite**: test fail nếu có import giữa hai gói `screens/*` khác nhau. Ngoại lệ
   phải liệt kê tường minh — hiện có 3 import chéo **phi-UI** cũng vi phạm
   (`backtest_presenter` → `dashboard.indicator_script_runner`, `dashboard.kline_mapping`;
   `backtest_view_model` → `dashboard.indicator_script_list_model`). Chúng **ngoài phạm vi
   epic này** (không phải widget) → cho vào danh sách miễn trừ có ghi lý do + link tới một task
   riêng, đừng im lặng nới guard.
4. Mỗi lớp một file. `chart_card/` giữ nguyên cấu trúc thư mục con hiện có.

## Bằng chứng

### 0 import chéo widget

```text
$ grep -rn "presentation.ui.screens\." src/presentation/ui/screens/*/*.py | grep "screens\."
backtest_presenter.py:98    -> screens.dashboard.indicator_script_runner
backtest_presenter.py:102   -> screens.dashboard.kline_mapping
backtest_view_model.py:29   -> screens.dashboard.indicator_script_list_model
```

Đúng 3 dòng còn lại — cả 3 đều nằm trong `_ALLOWED` của guard, có lý do và link
`Tasks/backlog/BOT-120_backtest_depends_on_dashboard_for_non_ui_logic.md` (task mới, mở trong
chính commit này). 0 import **widget**.

### Guard chạy thật, chứng minh bằng cách phá nó

`tests/unit/presentation/ui/test_no_cross_screen_imports.py`, 3 test. Thêm tạm một import chéo
mới (`data_management_view.py` import `AppLogPanel` từ `backtest` thay vì từ `components/`):

```text
FAILED test_no_widget_import_crosses_a_screen_boundary
E   một gói screens đang import từ gói screens khác.
E     data_management_view.py:12  data_management -> backtest  [AppLogPanel]
```

Khôi phục → `3 passed`.

### Gate (Python 3.12, `pwsh` không có trên môi trường này — chạy đúng lệnh `ci-local.ps1` gọi)

```text
ruff check src tests           RC=0   All checks passed!
ruff format --check src tests  RC=0   461 files
pytest tests/unit/ tests/sanity/  RC=0   1726 passed
```

Trước `007E`: 1704 passed. +22 test mới (guard import chéo ×3, guard card layer ×1, badge
format ×2, `SymbolPickerOverlay` — phần còn lại nằm trong test có sẵn được cập nhật).

### Ảnh trước/sau — `ChartCard` đổi lớp cha là thay đổi thị giác thật

| Màn | Pixel đổi | Delta TB |
| :--- | ---: | ---: |
| `settings` | 0% | 0 |
| `data_management` | 11,5% | 38,0 |
| `backtest` | 17,4% | 48,5 |
| `dashboard` | 23,1% | 83,1 |

Cao hơn hẳn `007D` (delta TB ~9) — đúng bản chất: `007D` đổi sắc độ, đây đổi **cấu trúc** (card
giờ có viền/nền thật, trước đó `BaseCard` không được style bởi gì cả).

## Bẫy phát hiện giữa chừng, không có trong đề bài

**Guard cũ xanh-giả khi mất referent.** `test_card_layer_structure.py` dò theo **chuỗi tên**
`"BaseCard"`. Xoá `BaseCard` mà không sửa guard thì `_defines_card_class` trả `False` cho mọi
file, hai test cũ pass vì tập kết quả rỗng — **không báo lỗi, chỉ lặng lẽ ngừng bảo vệ**. Đã
sửa: `_CARD_BASES` là tập hợp gồm cả `Card`/`BaseCard`, và thêm
`test_the_guard_still_finds_something` — assert tập `_card_classes` khác rỗng, để một guard
mất chủ thể phải kêu lên chứ không được im lặng.

**`apply_role()` của Engine ghi QSS không có selector, đổ xuống mọi widget con — `BUG-008`.**
`ChartCard` đặt `ChartToolbar` (5 nút không tự style, dựa vào theme toàn cục) vào header. Đổi
sang engine's `Card` thì QSS bare-property-list của `SURFACE` cascade xuống tận nút, làm mất
hết chrome — nhìn thấy được trên ảnh chụp, không có test nào bắt. Đây là lần đầu `Card` có
consumer thật (`007B` mới cho nó 0 consumer), nên lỗi này chưa từng lộ ra trước đó.

Mở `BUG-008` bên Engine. Sửa tạm bên Elite: `ChartToolbar` tự style bằng token thay vì dựa vào
theme toàn cục — không phải workaround, mà là việc nó lẽ ra phải làm từ đầu (một toolbar chỉ
đúng khi không ai phía trên có style là đang dựa vào may rủi).

## Ba trong bốn lớp task liệt kê — chỉ 2 đủ điều kiện thật

Task đưa ra 4 lớp. Đo lại theo đúng tiêu chí 3 tầng của epic (`README.md` §3.3):

| Lớp | Task nói | Đo thật | Quyết định |
| :--- | :--- | :--- | :--- |
| `ChartCard` | 1 consumer, đổi cha | 1 consumer thật, header API có **3** consumer (class + Protocol + adapter) + 1 lần inject runtime | Làm — giữ `add_to_header` làm shim, xem `chart_card.py` |
| `SymbolPickerOverlay` | ≥2 màn | **2 consumer thật** (DataMgmt + `BacktestSymbolPickerDialog`, cái sau chờ `007F`) | Làm |
| `TimeRangeCard` | kế thừa `Card` | **1 consumer**, và bản thân nó không có header/viền — không phải card, là 3 field trong 1 card có sẵn | **Không làm** — cho nó kế thừa `Card` là thêm chrome nó chưa từng có |
| `TradeSideBadge` | kế thừa `Badge` | **1 chỗ render** (`_side_badge`), không phải ≥2 | **Không làm** — chưa đủ điều kiện lên `components/` |

Cả hai bị hoãn đều còn 1 consumer — đúng ranh giới "hình dạng là phỏng đoán, chưa có consumer
thật để đối chiếu" mà `README.md` §5 (kill criterion đã sửa ở `007A`) chặn lại. Ghi làm ứng
viên, không đoán hình dạng.

## Rủi ro (bản gốc) — đã xảy ra đúng như cảnh báo

`chart_toolbar.py`'s docstring quả thật còn nhắc `BaseCard.add_to_header`, và rà hết call-site
lộ ra **3 consumer, không phải 1**: `ChartCard`, Protocol `IBacktestChartHost`, adapter
`PythonBacktestChartHost`, cộng một lần inject thứ hai runtime từ `backtest_view.py`. Giữ
`add_to_header` làm method (không xoá) chính là cách xử lý — xem docstring của nó trong
`chart_card.py` để biết đủ 4 nơi gọi.
