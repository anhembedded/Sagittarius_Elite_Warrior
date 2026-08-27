# EPIC-012C — `BacktestScreenState`: gom 24 accessor về 1 tham số

**Trạng thái:** ⬜ Chưa làm
**Repo:** Elite
**Phụ thuộc:** `A`

## Số đo (2026-08-27)

6 Coordinator nhận **74 tham số** constructor. **24** trong đó là accessor
đọc/ghi state của Presenter, và chúng lặp lại nhau:

| Accessor | Xuất hiện ở |
| :--- | :--- |
| `get_symbol` | `execution`, `chart_render`, `strategy_config`, `data_sync` |
| `get_current_raw_klines` | `indicator`, `strategy_config` |
| `get_active_strategy_lines` | `chart_render`, `indicator` |
| `get_chart_klines_fetch_limit` | `execution`, `chart_render` |
| `get_chart_script_keys` / `set_chart_script_keys` | `execution` / `indicator` |
| còn lại (1 nơi mỗi cái) | `set_current_raw_klines`, `get_chart_mode`, `get_strategy_params`, `set_strategy_params`, `get_all_trades`, `get_first_chart_card`, `get_market_metadata`, `get_current_config`, `is_busy`, `next_preview_id`, `get_active_preview_id`, `effective_data_interval` |

Gom về **một** object `BacktestScreenState`, mỗi Coordinator nhận đúng 1 tham số
`state` → **74 → 56**.

## Ràng buộc bắt buộc — đọc muộn, không bao giờ capture

`EPIC-003E` đã dính **4 lần** đúng một lỗi: capture một thuộc tính/bound method
của Presenter **lúc dựng Coordinator**, trong khi test thay nó **sau đó**. Vì
vậy `BacktestScreenState` **không được** là một `dataclass` chụp giá trị lúc
dựng. Nó phải là một **kiểu có property đọc thẳng vào Presenter/ViewModel tại
thời điểm gọi** — hoặc giữ callable bên trong nhưng chỉ gọi khi được hỏi.

`get_first_chart_card` là ca đặc biệt và **phải giữ nguyên là hàm**: `BUG-013`
cho thấy chart card cached trở thành C++ object đã `deleteLater()` sau khi host
dựng lại. Cache nó vào một dataclass là dựng lại đúng bug đó.

## Ranh giới: cái gì KHÔNG vào `BacktestScreenState`

Chỉ **state**. Ba thứ dưới đây trông giống nhưng là **lệnh gửi tới View**, phải
đi qua `IBacktestView` (`EPIC-012B`) chứ không đi qua state:
`set_chart_display_timezone`, `set_strategy_lines_visible`,
`set_script_overlay_lines_visible`.

Tương tự, `emit_*` là **kênh phát tín hiệu**, không phải state — giữ nguyên.

## Nghiệm thu

- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`.
- Đếm lại tham số ctor: tổng phải là **56**.
- **Bơm lỗi bắt buộc:** đổi một property của `BacktestScreenState` thành chụp
  giá trị một lần lúc `__init__`. Ít nhất một test phải đỏ. Không test nào đỏ
  nghĩa là lớp lỗi early-binding của `EPIC-003E` vẫn chưa được phủ.
