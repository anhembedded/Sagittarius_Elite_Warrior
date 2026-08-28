# EPIC-014 — Widget chọn Symbol và Timeframe dùng chung

**Trạng thái:** ✅ hoàn thành
**Bắt đầu:** 2026-08-28
**Yêu cầu gốc:** *"tạo cho tôi cái widget như này đi, đổi nó thành widget dùng
chung cho backtest và dev"* + *"ý là tui muốn bạn tạo card, và tạo thêm nhiều
timeframe"* + *"các màn hình, cái nào cùng tính năng thì app dùng luôn cái mới"*

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

1. `BackTestPresenter` cũng kiểm tra `if default_interval in DEFAULT_TIMEFRAMES`
   — nên một người đặt `DEFAULT_INTERVAL = "4h"` trong config bị **bỏ qua im
   lặng**, vì cái tuple canh toolbar cũng đang định nghĩa "config hợp lệ là gì".
2. `ChartToolbar` — hàng 5 pill nằm trên **mọi** chart card, ở cả Backtest lẫn
   Dev Board — là bộ chọn timeframe thật, và cũng chỉ có 5. `set_active("4h")`
   không khớp nút nào, nên **cả 5 pill đều không sáng** và người dùng không có
   đường quay lại khung đang xem. Trạng thái này chạm được ở **mọi lần khởi
   động**: `EPIC-010D` khôi phục interval đã nhớ, và `DEFAULT_INTERVAL` đặt
   được bất kỳ khung nào trong 16.
3. Settings: `Default Interval` là ô text tự do. Gõ sai → im lặng, theo đúng
   đường (1).

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
| Data Management symbol | `QComboBox` sửa được **+** nút kính lúp (2 widget cho 1 lựa chọn) | một nút mở `SymbolPickerOverlay` |
| Data Management timeframe | `QComboBox` đóng (đã đủ 16) | nút mở `TimeframePickerOverlay` |
| `ChartToolbar` (Backtest + Dev Board) | 5 pill, hết | 5 pill **+ nút `…`** mở đủ 16; khung ngoài pill hiện ngay trên nút `…` |
| Settings `Default Interval` | ô text tự do | nút mở `TimeframePickerOverlay` |

Ba file cũ **bị xoá hẳn** (`backtest_modals/symbol_picker_dialog.py`,
`backtest_modals/timeframe_picker_dialog.py`, `components/symbol_picker_overlay.py`),
không giữ lại làm forwarder — forwarder chính là cách các bản sao sống sót qua
lần thử đầu của `EPIC-007F`.

`ChartToolbar` tự sở hữu dialog của nó thay vì bắn `sig_more_requested` ra
ngoài: nó chỉ mở đúng cái nó vốn đã chọn và bắn lại đúng
`sig_timeframe_changed`, nên **không consumer nào phải sửa** — và không màn
hình nào mọc thêm một bản sao của đoạn đấu dây đó, đúng thứ đã làm các picker
nhân lên ngay từ đầu.

`SymbolPreferences` đăng ký singleton trong container ở `app_bootstrapper`, nối
vào `UiStateCoordinator` (`EPIC-010`) để yêu thích/gần đây sống qua lần khởi
động sau. Mỗi màn hình tự dựng một store riêng khi container không có —
presenter được dựng trong test với container trống, và một màn hình không có
store vẫn phải mở được picker.

### 2.4 Sửa kèm theo: `DEFAULT_INTERVAL = "4h"` không còn bị bỏ qua

`BackTestPresenter` giờ kiểm tra `describe_timeframe(...) is not None` — hỏi
domain, không hỏi cái tuple canh toolbar.

---

### 2.5 Sửa ngay sau đó: nút `…` "không thấy đâu"

User báo *"thiếu cái nút … rồi"* kèm ảnh mock. Nút **có** được tạo và **có**
`isVisible() == True` — dựng thật một `ChartCard` offscreen rồi đo, nó nằm ở
**13×19 px**.

Nguyên nhân: `_button_style()` ghi `padding: 2px 0` — không có padding ngang —
nên **mọi** nút trong hàng co lại đúng bề rộng chữ của chính nó: `1d` 16px,
`…` 13px. Một dấu ba chấm màu xám mờ rộng 13px không đọc ra là nút, nó đọc ra
là dấu phân cách. Sửa ở đúng nguyên nhân (`padding: 2px 8px` cho cả hàng) chứ
không đặc cách riêng một nút, kèm sàn `_BUTTON_MIN_WIDTH` cho các nhãn hẹp
nhất. Sau khi sửa: pill 34–43px, `…` 34px, `12h` 42px (trần 52, không bị cắt).

Kèm theo một lỗi thứ hai tìm ra lúc soi lại: `_btn_more` là `setCheckable(True)`,
mà `clicked` đã toggle nó **trước khi** slot chạy — nên mở picker rồi thoát ra
để lại nút `…` sáng cùng lúc với pill đang chọn, hai chỗ cùng trông như được
chọn. `_open_picker` giờ khẳng định lại `set_active(self._active)` ngay đầu.

Test đo **bề rộng sau khi layout**, không phải `setMinimumWidth` — đã A/B: bỏ
padding ra là test đỏ với `assert 13 >= 34`, đúng con số user nhìn thấy.

## 3. Chưa làm / cố ý để lại

- **Settings → `Default Symbols` vẫn là ô text.** Nó là một **danh sách** ngăn
  bằng dấu phẩy, không phải một lựa chọn đơn — khác tính năng với picker, và
  gắn picker vào đó còn kéo theo việc màn Settings phải gọi sàn lấy danh sách
  mã, thứ nó chưa từng làm. Ghi lại ở đây thay vì làm nửa vời.
- `ChartToolbar.DEFAULT_TIMEFRAMES` **giữ nguyên 5 pill** — đó là hàng pill
  trên header chart, 16 pill sẽ tràn. Ràng buộc đó là thật và giữ nguyên; chỗ
  sai là nó từng kiêm luôn việc *định nghĩa người dùng được chọn gì*, và nút
  `…` mới là cái gỡ chỗ đó.
