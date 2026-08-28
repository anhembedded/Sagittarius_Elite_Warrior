# EPIC-014 — Widget chọn Symbol và Timeframe dùng chung

**Trạng thái:** đang làm
**Bắt đầu:** 2026-08-28
**Yêu cầu gốc:** *"tạo cho tôi cái widget như này đi, đổi nó thành widget dùng
chung cho backtest và dev"* + *"ý là tui muốn bạn tạo card, và tạo thêm nhiều
timeframe"*

---

## 1. Vấn đề

### 1.1 Symbol: ba bản khác nhau của cùng một màn hình

| Nơi | Cái đang có | Thiếu |
| :--- | :--- | :--- |
| Data Management | `components/symbol_picker_overlay.py` (mỏng, trên `PickerOverlay`) | favourites, recents, lọc theo quote |
| Backtest | `backtest_modals/symbol_picker_dialog.py` — **bản sao riêng** | như trên |
| Dev Board | **không có picker nào** — `QComboBox` editable nhét cứng `["BTCUSDT", "ETHUSDT"]` | tất cả |

`EPIC-007F` đã ghi ý định gộp ba cái này lại và **không làm** — comment trong
`symbol_picker_overlay.py` còn nguyên: *"Backtest's own
`BacktestSymbolPickerDialog`, which `EPIC-007F` migrates. Until it does, two
dialogs still render this shape"*. Bản sao thứ ba (Dev Board) thì tệ hơn: sàn
niêm yết ~1.400 cặp, người dùng chỉ chạm được 2 cặp bằng một cú click, mọi cặp
khác phải **gõ tay đúng từng ký tự**, không có gì kiểm tra — gõ sai thành một
symbol mà stream không bao giờ tick.

### 1.2 Timeframe: UI là chỗ duy nhất trong stack không với tới được

`TimeFrame` khai báo **16** khung. Sàn trả về cả 16. DB lưu cả 16.
`BackTestViewModel.timeframeOptions` trả về `DEFAULT_TIMEFRAMES` — một tuple
**5 phần tử** nằm trong `chart_card/chart_toolbar.py`, tồn tại để **canh một
hàng pill trên header của chart**. Một hằng số canh layout đang quyết định
người dùng được chọn khung nào.

Hệ quả đo được, không phải suy đoán:
`BackTestPresenter` cũng kiểm tra `if default_interval in DEFAULT_TIMEFRAMES`
— nên một người đặt `DEFAULT_INTERVAL = "4h"` trong config bị **bỏ qua im
lặng**, vì cái tuple canh toolbar cũng đang định nghĩa "config hợp lệ là gì".

---

## 2. Đã làm

### 2.1 `components/symbol_picker/` — widget dùng chung

Logic thuần tách khỏi Qt, để test được mà không cần `QApplication`:

| File | Việc |
| :--- | :--- |
| `quote_asset.py` | tách `BASE`/`QUOTE` bằng **so khớp hậu tố dài nhất** — `ETHFDUSD` → `ETH`/`FDUSD`, không phải `ETHF`/`USD` |
| `filtering.py` | `Scope` (Tất cả / Yêu thích / Gần đây), lọc quote, tìm kiếm — AND cả ba |
| `preferences.py` | `SymbolPreferences`: yêu thích + gần đây, `IStateContributor` scope `symbol_prefs` |
| `symbol_card.py` | `SymbolCard` — `BASE` đậm + `quote` mờ, dòng trạng thái, ngôi sao |
| `overlay.py` | `SymbolPickerOverlay` — ô tìm kiếm + đếm kết quả, tab scope, tab quote, mục yêu thích, điều hướng bàn phím |

**Một store duy nhất cho mọi màn hình, không phải mỗi màn hình một cái.** Sao
một cặp trên Backtest nghĩa là *"cặp này quan trọng với tôi"*, không phải
*"quan trọng với tôi ở tab này"* — hai bản sao sẽ trôi ra khỏi nhau.

`favourite_toggled` tách khỏi `clicked`: đánh sao **không phải** là chọn. Nếu
gộp, người dùng đang sắp xếp danh sách yêu thích sẽ bị đóng dialog sau mỗi lần
bấm sao.

### 2.2 `components/timeframe_picker/` — card + đủ 16 khung

`catalogue.py` **suy ra từ chính `TimeFrame`**, không liệt kê lại: thêm một
member vào enum là nó xuất hiện trong picker, không cần sửa chỗ thứ hai. Đây
là phiên bản duy nhất của việc này mà không thể trôi ra lại.

- Nhóm theo đơn vị: GIÂY / PHÚT / GIỜ / NGÀY TRỞ LÊN — người dùng quyết định
  đơn vị trước, con số sau.
- Sắp theo `to_seconds()`, không theo thứ tự khai báo.
- Mỗi card: mã (`4h`) + nghĩa (`4 giờ`). `12h`, `1d`, `3d` đều ba ký tự và
  khác nhau ở đúng ký tự mắt đọc cuối cùng — viết nghĩa ra là cái làm lưới đọc
  được.
- `1s` được cảnh báo (một ngày ≈ 86.400 nến), **không bị chặn** — đó chính là
  khung `VolumeSpikeFlowStrategy` cần.

### 2.3 Đấu dây

| Màn hình | Trước | Sau |
| :--- | :--- | :--- |
| Backtest symbol | `BacktestSymbolPickerDialog` (xoá) | `SymbolPickerOverlay` |
| Backtest timeframe | `TimeframePickerDialog` (xoá), 5 khung | `TimeframePickerOverlay`, 16 khung |
| Dev Board symbol | `QComboBox` 2 mục nhét cứng | `SymbolPickerOverlay` + `symbolOptions` lấy từ sàn (BOT-102) |

Hai dialog cũ **bị xoá hẳn**, không giữ lại làm forwarder — forwarder chính là
cách hai bản sao sống sót qua lần thử đầu của `EPIC-007F`.

`SymbolPreferences` đăng ký singleton trong container ở `app_bootstrapper`, nối
vào `UiStateCoordinator` (`EPIC-010`) để yêu thích/gần đây sống qua lần khởi
động sau. Mỗi màn hình tự dựng một store riêng khi container không có —
presenter được dựng trong test với container trống, và một màn hình không có
store vẫn phải mở được picker.

### 2.4 Sửa kèm theo: `DEFAULT_INTERVAL = "4h"` không còn bị bỏ qua

`BackTestPresenter` giờ kiểm tra `describe_timeframe(...) is not None` — hỏi
domain, không hỏi cái tuple canh toolbar.

---

## 3. Chưa làm / cố ý để lại

- **Data Management vẫn dùng `components/symbol_picker_overlay.py` (bản mỏng).**
  Yêu cầu của user nói rõ phạm vi là *"backtest và dev"*. Chuyển màn hình thứ
  ba là việc tách riêng, không gộp vào đây để giữ diff đọc được.
- `ChartToolbar.DEFAULT_TIMEFRAMES` **giữ nguyên 5 pill** — đó là hàng pill
  trên header chart, 16 pill sẽ tràn. Nó không còn kiêm nhiệm việc định nghĩa
  danh sách chọn nữa, đó mới là chỗ sai.
