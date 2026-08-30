# EPIC-017B — Dùng `TimeFrame` Enum có sẵn thay literal `"1m"` ở 4 file presentation

**Thuộc Epic:** [`EPIC-017`](../README.md)
**Trạng thái:** ✅ Xong 2026-08-30
**Phụ thuộc:** Không (độc lập với `017A`).

---

## Hiện trạng

`src/domain/value_objects/timeframe.py:4` đã có `class TimeFrame(str, Enum)`
với 16 giá trị (`ONE_SECOND` … `ONE_MONTH`). Nhưng tầng presentation vẫn
hardcode literal `"1m"` >20 chỗ, đồng bộ thủ công bằng comment thay vì
import chung 1 hằng số:

- `backtest_view_model.py:46-51` — `_DEFAULT_TIMEFRAME = "1m"`, comment
  "Must match dashboard_presenter.py's own `_DEFAULT_INTERVAL_STR` (\"1m\")".
- `dev_board_panel.py:78`
- `data_management/data_management_widgets/time_range_card.py:31`
- `data_management_view_model.py` — 6 chỗ default `interval: str = "1m"`.

**Report gốc claim sai:** không phải "chưa có Value Object nào" — nó đã có,
chỉ chưa được dùng ở tầng UI.

## Việc cần làm

1. Thay từng default literal `"1m"` bằng `TimeFrame.ONE_MINUTE` — vì
   `TimeFrame` là `str` subclass, so sánh (`== "1m"`) và serialize JSON
   không đổi hành vi runtime.
2. Xoá các comment kiểu "Must match X's own Y" — sau khi cả 2 phía cùng
   import `TimeFrame.ONE_MINUTE`, đồng bộ là tự động, comment thành thừa.
3. **Không đổi** bất nhất thuật ngữ `"timeframe"` (backtest) vs
   `"interval"` (dashboard, data_management) trong task này — đổi tên field
   là việc rộng hơn nhiều (đụng tên property/signal ở nhiều nơi), nằm
   ngoài scope; chỉ đổi *giá trị mặc định* dùng chung 1 nguồn.
4. Rà toàn bộ danh sách khung thời gian hiển thị trên UI (timeframe picker,
   chart toolbar) — nếu chỗ nào đang tự liệt kê string thay vì duyệt
   `TimeFrame`, cân nhắc đổi luôn (không bắt buộc nếu rủi ro cao hơn lợi ích
   — ghi rõ lý do bỏ qua nếu quyết định không đổi).

## Tiêu chí xong

- `grep -rn '"1m"' src/presentation` không còn ra literal default nào chưa
  qua `TimeFrame.ONE_MINUTE` (trừ nơi thực sự cần string thô, ví dụ payload
  gửi lên Binance API — ghi rõ lý do giữ nguyên nếu có).
- 4 file nêu trên dùng chung `TimeFrame.ONE_MINUTE`, không còn comment
  đồng bộ thủ công.
- Test default value của cả 4 màn hình vẫn xanh, không đổi assertion giá
  trị (chỉ đổi cách viết literal → enum).

## Kết quả (2026-08-30)

Sửa **5 file** (4 nêu trên + `src/presentation/ui/common/app_defaults.py` —
cùng magic string, cùng lý do, phát hiện khi làm task này):

| File | Trước | Sau |
| :--- | :--- | :--- |
| `backtest_view_model.py:52` | `_DEFAULT_TIMEFRAME = "1m"` | `TimeFrame.ONE_MINUTE.value` |
| `dev_board_panel.py:78-79` | `_FALLBACK_TIMEFRAME_SECONDS = 60` / `_LABEL = "1m"` | `TimeFrame.ONE_MINUTE.to_seconds()` / `.value` — 2 constant không còn drift độc lập |
| `time_range_card.py:31-32` | như trên | như trên |
| `data_management_view_model.py` | 2 instance attr + 6 default param `"1m"` | `TimeFrame.ONE_MINUTE.value` (đã import `TimeFrame` sẵn từ trước) |
| `app_defaults.py:40` | `FALLBACK_INTERVAL = "1m"` | `TimeFrame.ONE_MINUTE.value` |

**Bẫy phát hiện khi làm (đáng ghi lại):** `class TimeFrame(str, Enum)` —
`TimeFrame.ONE_MINUTE == "1m"` đúng, nhưng `str(TimeFrame.ONE_MINUTE)` /
f-string của chính instance Enum trả về `"TimeFrame.ONE_MINUTE"`, **không
phải** `"1m"` (verify bằng `python3.12` thật). Vì vậy mọi chỗ thay literal
đều dùng `.value` (một `str` thuần), không dùng thẳng `TimeFrame.ONE_MINUTE`
— nếu không sẽ đổi hành vi runtime ở bất kỳ chỗ nào format/nối chuỗi giá trị
này, đúng loại lỗi mà `app_defaults.py`'s docstring (`EPIC-010H`) đã cảnh báo
("A behaviour change smuggled in beside a refactor is invisible in review").

**Verify:** `ruff check`/`ruff format --diff` sạch trên cả 5 file. Test suite
thật (Python 3.12 venv, PySide6 6.11.1 + engine editable, `QT_QPA_PLATFORM=offscreen`)
— 487 test xanh (`test_app_defaults.py` + toàn bộ `screens/backtest/`,
`screens/data_management/`, presenter/panel test của cả 3 màn liên quan),
không đổi assertion nào.
