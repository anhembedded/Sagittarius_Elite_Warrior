# EPIC-007E — Elite: tầng `components/` dùng chung, cắt import chéo màn hình

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Elite_Warrior` · **Trạng thái:** 🔵 Chưa làm
**Phụ thuộc:** `007B`, `007C`, `007D`

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

## Bằng chứng phải nộp

- `grep` chứng minh 0 import chéo widget giữa các `screens/*`.
- Guard mới chạy thật: thêm tạm 1 import chéo → test đỏ. Dán output.
- `pwsh -NoProfile -File scripts/ci-local.ps1` — `RESULT: PASS`.

## Rủi ro

`ChartCard` đổi lớp cha là chỗ dễ vỡ nhất: `chart_toolbar.py:10` docstring còn nhắc
`BaseCard.add_to_header` — engine's `Card` dùng `header_actions` (một `QHBoxLayout`), API khác.
Rà hết mọi call-site `add_to_header`/`add_to_footer` trước khi đổi.
