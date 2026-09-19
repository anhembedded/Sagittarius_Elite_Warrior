# BUG-110 — Cảnh báo `[chart-range]` (nến bị ép dẹp) tái xuất hiện, sau khi `BUG-034` đã sửa

**Reported date:** 2026-09-09
**Severity:** ⚪ **Đóng — không tái hiện được từ môi trường hiện có** (trước: 🟡 P3)
**Status:** ⚪ **Đóng 2026-09-19 (user quyết định).** 3 lượt điều tra, root cause **chưa** xác nhận
được — xem §8 để biết đóng hồ sơ này nghĩa là gì và không nghĩa là gì.

---

## 1. Hiện tượng (Symptom)

User chạy app thật (Windows, GUI thật, Binance thật — đúng môi trường mà `BUG-034` không có suốt
5 lượt điều tra), mở màn **Giao dịch** (Trading) với symbol `ETHUSDT`. Log gốc do user cung cấp:

```text
2026-09-09 08:40:22,619 - App.ChartCard - INFO - [cached-frame] ChartCard(ETHUSDT): cached interaction DISABLED — pan/zoom go straight to pyqtgraph
2026-09-09 08:40:22,620 - App.ChartCard - INFO - [chart-env] ChartCard(ETHUSDT): render backend=cpu (opengl requested=False) | antialias=layered | LOD=True | cached interaction=False | DPR=2 | Qt platform=wayland | screen=1440x900
2026-09-09 08:40:23,069 - App - INFO - Executing query: GetHistoricalKlinesQuery
2026-09-09 08:40:23,086 - App.QueryHandler - INFO - BACKTEST_TRACE action=query_execute_start symbol=['ETHUSDT'] timeframe='1m' limit=500 start=None end=None order_by_desc=True
2026-09-09 08:40:23,296 - App.QueryHandler - INFO - BACKTEST_TRACE action=query_execute_complete_multi symbols=1 rows={'ETHUSDT': 500}
2026-09-09 08:40:23,506 - App.ChartCard - INFO - [chart-data] ChartCard(ETHUSDT): loaded 500 candles spanning [1788806100.0, 1788836040.0] | price [2475.3100, 2507.9900] | initial view x-range [1788826742.4, 1788836040.0] | y-range [2473.5426, 2509.7574] | autorange=[False, True] | chart type=candlestick
2026-09-09 08:40:35,313 - App.ChartCard - WARNING - [chart-range] ChartCard(ETHUSDT): price band [2475.3100, 2507.9900] fills only 18.77% of y-range [2401.5721, 2575.6500] — candles are unreadable. Y bounds each item on the main plot claims: FastCandlestickItem=[2475.3100, 2507.9900] PlotDataItem=None
```

- **08:40:23,506** — nạp xong lịch sử: `price [2475.31, 2507.99]` khớp gần đúng
  `y-range [2473.54, 2509.76]` — trục Y khoẻ mạnh, đúng như mong đợi.
- **08:40:35,313** — 12 giây sau, **không có lệnh nạp dữ liệu mới nào được log ở giữa** — cảnh báo
  `[chart-range]` bắn: `y-range` đã đổi thành `[2401.57, 2575.65]`, rộng hơn hẳn dải giá thật
  (32.68 đơn vị) trong khi trục Y cao 174.08 đơn vị → nến chỉ còn chiếm 18.77%.

## 2. Đối chiếu với `BUG-034` (đã sửa 2026-09-08, ngay hôm trước)

Đây là **đúng cơ chế cảnh báo** `BUG-034`'s §10.3 đã cấy vào code
(`ChartCard._report_squashed_price_band()`, nối vào `vb.sigRangeChanged`) — cảnh báo này tồn tại
chính xác để bắt lại triệu chứng này nếu nó quay lại (§11.5 của `BUG-034` nói rõ điều đó). Nhưng
nội dung cảnh báo lần này **khác hẳn** lần `BUG-034` báo:

| | `BUG-034` (đã sửa) | `BUG-110` (log này) |
| :--- | :--- | :--- |
| % nến chiếm trục | ~0.88% (gần như biến mất) | 18.77% (thấy được, nhưng lẹm) |
| Item nào bị nêu tên là thủ phạm | `rsi_14=[10.0000, 90.0000]` — item thang dao động thật | **Không có** — chỉ `FastCandlestickItem` (đúng giá) và `PlotDataItem=None` (không đóng góp gì) |
| Cơ chế đã xác nhận | Một overlay không theo thang giá tham gia auto-range Y | **Chưa xác định** |

**Đã kiểm tra `git blame`/đọc code**: bản sửa `BUG-034` (`ignoreBounds=True` khi thêm curve overlay,
`indicator_manager.py:114`) đúng là đang có trong code hiện tại. Rà toàn bộ nơi gọi
`main_plot.addItem(...)` trong `src/presentation/ui/components/chart_card/`:

| File:dòng | Item | `ignoreBounds`? |
| :--- | :--- | :---: |
| `chart_card.py:171` | `self.candlestick` (nến) | Không — **đúng**, đây là item định nghĩa trục giá |
| `crosshair_controller.py:86-89` | crosshair lines/labels | Có |
| `price_line.py:30` | current-price line | Có |
| `indicator_manager.py:114` | overlay indicator curve | Có (bản sửa `BUG-034`) |

→ **Mọi item khác ngoài nến đều đã có `ignoreBounds=True`.** Cơ chế "một item khác kéo trục"
(root cause của `BUG-034`) đã bị bịt kín ở mọi call site hiện có. Log của `BUG-110` cũng xác nhận
điều đó — không có item nào khác với Y bounds thật ngoài `FastCandlestickItem`. **Đây gần như
chắc chắn là một cơ chế KHÁC**, không phải `BUG-034` tái phát từ chỗ cũ.

## 3. Nghi vấn chưa xác nhận — cần điều tra, không đoán fix

`_set_initial_view_range()` (`chart_card.py:377-404`) có 2 nhánh:

- Dữ liệu ít (`<= _DEFAULT_INITIAL_VISIBLE_CANDLES`): gọi `main_plot.autoRange()` thẳng.
- Dữ liệu nhiều hơn (trường hợp 500 nến ở đây): gọi `enableAutoRange(y=True)` rồi
  `setXRange(first_t, last_t, padding=0.02)` — **không** gọi gì cho Y ngoài bật lại auto-range.

Đúng như `BUG-034` §10.1 đã chứng minh: pyqtgraph **không tính lại auto-range lúc thêm/bật** — chỉ
đánh dấu bẩn, tính lại ở lần **paint** kế tiếp. Log `08:40:23`'s `y-range [2473.54, 2509.76]` có
thể là dải **trước khi paint thật chốt** (transient), và `08:40:35`'s `y-range [2401.57, 2575.65]`
mới là dải **đã chốt thật** — 12 giây là khoảng chờ hợp lý cho lần paint đầu tiên trên một cửa sổ
thật (không phải offscreen).

**Nếu đúng vậy**, câu hỏi thật là: dải `[2401.57, 2575.65]` từ đâu ra, khi chỉ có
`FastCandlestickItem=[2475.31, 2507.99]` đóng góp? Padding mỗi bên ≈ 70.7 đơn vị ≈ 216% chiều cao
dải giá — quá lớn so với padding mặc định pyqtgraph (~2-10%). Nghi vấn cụ thể, **chưa xác nhận**:

1. `PlotDataItem=None` — item nào? Nếu là một overlay indicator đã dựng (`add_overlay`,
   `ignoreBounds=True`) nhưng CHƯA có dữ liệu (`update_indicator_data` chưa gọi tới) — nó đúng là
   vô hại (đã loại ở §2). Nhưng nếu là một item KHÁC chưa được `ignoreBounds` — dù hiện tại
   `dataBounds()` trả `None` (rỗng) — mà **timing thật** giữa lúc log bắn và lúc item đó nhận dữ
   liệu có xen vào, cảnh báo có thể bắt đúng lúc item đó tạm rỗng, còn lúc kéo trục thật lại có dữ
   liệu (rồi rỗng lại) — timing này chỉ tái hiện được trên GUI thật, không tái hiện được headless
   (đúng bài học `BUG-034` §10.1/§6).
2. Padding mặc định của `enableAutoRange(y=True)` khi không đi kèm `setYRange`/`autoRange()` rõ
   ràng — có thể pyqtgraph dùng padding tính theo `%` của **toàn bộ lịch sử X-range** đã nạp
   (`first_t..last_t` của 500 nến) chứ không phải theo cửa sổ X hiện đang hiển thị
   (`setXRange(first_t, last_t)` chỉ giới hạn X, không giới hạn item nào được xét cho Y) — nếu
   đúng, `enableAutoRange(y=True)` có thể đang tính Y theo dải giá của **toàn bộ 500 nến**, không
   phải dải giá của cửa sổ đang hiển thị. Đọc `price [2475.31, 2507.99]` trong log — đây LÀ
   `min/max` của toàn bộ 500 nến (`min(lows)`/`max(highs)` ở `chart_card.py:367-368`), nên giả
   thuyết này **cũng chưa loại được bằng log hiện có** — cần log riêng dải giá của đúng cửa sổ
   X đang hiển thị (`first_t..last_t` sau `_set_initial_view_range`) để so sánh.

## 4. Suggested next steps

Không đoán fix khi chưa xác nhận — theo đúng tinh thần `fix-bug-rule.md` §1 và tiền lệ `BUG-034`.

1. Viết test unit ép `vb.updateAutoRange()` chạy thật sau `render_historical_data()` với **>500
   nến thật** (nhánh `setXRange` của `_set_initial_view_range`, khác nhánh `autoRange()` mà
   `BUG-034`'s test `test_auto_range_does_not_settle_until_the_view_is_asked_to_update` đã dùng —
   cần xác nhận nhánh nào tạo ra triệu chứng, có thể chỉ nhánh `setXRange` mới bị) — so `y-range`
   trước/sau update, đối chiếu với dải giá của **đúng cửa sổ X** `first_t..last_t`, không phải
   toàn bộ lịch sử.
2. Nếu tái hiện được ở bước 1: đã có bằng chứng — viết fix + regression test đúng quy trình.
3. Nếu KHÔNG tái hiện được: cần môi trường GUI thật (như `BUG-034` 4 lượt đầu) — chạy `--debug`,
   thêm log tạm ở `_set_initial_view_range()` in ra `viewRange()` ngay sau mỗi nhánh + ngay tại
   thời điểm `[chart-range]` bắn, để phân biệt "giá trị X-range dùng để tính Y auto-range" (toàn bộ
   lịch sử hay cửa sổ hiển thị).
4. `[chart-range]`'s log (`_main_plot_y_bounds()`) hiện chỉ liệt kê item **đang có trên `vb.addedItems`
   tại đúng lúc bắn** — nếu nghi vấn #1 ở §3 đúng (một item rỗng lúc log, có dữ liệu lúc kéo trục),
   cân nhắc thêm timestamp/số lượng điểm dữ liệu mỗi item vào dòng log đó để bắt được timing, không
   chỉ tên.

## 5. Việc đã làm để loại trừ (không cần lặp lại)

- Đã đọc `pyqtgraph`/source thật của mọi call site `main_plot.addItem(...)` trong
  `chart_card.py`/`crosshair_controller.py`/`price_line.py`/`indicator_manager.py` — **không phải**
  cơ chế `BUG-034` (mọi overlay đã `ignoreBounds=True`).
- Đã xác nhận log `[chart-range]` là cơ chế chẩn đoán **cố ý giữ lại** sau khi `BUG-034` đóng
  (đúng như §11.5 của nó dự đoán), không phải regression của epic nào đang làm — không có commit
  nào trong `EPIC-023A/B/C/D` (2026-09-08) chạm tới `chart_card.py`/`indicator_manager.py`.

---

## 6. Lượt điều tra 2 (2026-09-09) — 3 giả thuyết mới loại trừ bằng đối chiếu source
`pyqtgraph` thật + repro headless, **chưa root-cause được**, đã tăng cường chẩn đoán

**Trạng thái: vẫn Open.** Không có máy Windows/GUI thật hay Binance thật trong môi trường phiên
này — cùng giới hạn đã chặn 4/5 lượt điều tra `BUG-034`. Không đoán fix khi chưa có bằng chứng
(`fix-bug-rule.md` §1).

### 6.1. Loại trừ bằng toán học: padding của pyqtgraph không thể tạo ra dải rộng như log

Đọc `ViewBox.suggestPadding()`/`updateAutoRange()` (source thật, không suy đoán từ trí nhớ):

```python
def suggestPadding(self, axis):
    l = self.width() if axis==0 else self.height()
    def_pad = self.state['defaultPadding']       # = 0.02, không đổi trong app này
    max_pad = max(0.1, def_pad)                    # = 0.1 — CHẶN TRÊN, luôn luôn
    ...
```

Padding tối đa có thể là **10% mỗi bên** (`max_pad=0.1`), bất kể `self.height()` (kích thước pixel
widget) nhỏ tới đâu — đã thử trực tiếp `vb.height()` ngay sau khi dựng `ChartCard` chưa `show()`:
trả về ~305px (giá trị placeholder hợp lý của Qt, không phải 0), `suggestPadding(1) ≈ 0.057` — hoàn
toàn bình thường. Với padding tối đa 10% mỗi bên, `y-range` chỉ có thể rộng hơn `childRange` (dải
**trước** padding) tối đa 20%. Từ số liệu log: `174.08 = childRange_height * (1 + 2*padding)` →
`childRange_height ≥ 174.08 / 1.2 ≈ 145.07` — **gấp 4.4 lần** dải giá thật (32.68). Nghĩa là:
**`childRange` (giá trị trước khi cộng padding) đã sai từ gốc — không phải do padding.**

### 6.2. Loại trừ: cơ chế cache `_cached_visible_bounds` bị stale do live candle

`FastCandlestickItem.dataBounds(1, orthoRange=...)` cache theo `(lo, hi)` (chỉ số cửa sổ hiển thị),
rồi **luôn** merge thêm `self.live_candle` (nến đang hình thành) vào kết quả, **không cache phần
đó**. Giả thuyết: 1 tick live có high/low bất thường (glitch sàn) từng kéo dải rộng, rồi dải đó bị
"đóng băng" sau khi nến đó `close` (do `update_live_candle()` — chạy mỗi tick — **không** gọi
`informViewBoundsChanged()`, chỉ `append_closed_candle()` mới gọi). Đã đọc kỹ: khi nến close,
`generate_picture()` chạy TRƯỚC khi `self.live_candle` bị reset — nhưng `dataBounds()` thật (từ
`updateAutoRange()`) chỉ được pyqtgraph gọi **sau đó**, ở lần paint kế tiếp, lúc `live_candle` đã
`None`. Vậy nến vừa đóng (giá trị THẬT, không phải giá trị glitch tạm) mới là thứ được dùng — nếu
nến đó có wick thật sự rộng, `dataBounds(1)` (fallback KHÔNG-orthoRange, dùng trong log) cũng phải
phản ánh đúng wick đó — nhưng log cho `price_bounds` = [2475.31, 2507.99], khớp *đúng* dải 500 nến
ban đầu, không rộng hơn. **Mâu thuẫn** — nếu có 1 nến đóng với wick cực rộng thật, `price_bounds`
phải rộng theo, nhưng nó không rộng. Loại trừ giả thuyết "1 nến đóng có wick bất thường thật".

### 6.3. Đã thử tái hiện bằng 4 bộ dữ liệu tổng hợp khác nhau — không tái hiện được

Cùng bài học `BUG-034` §6/§8.5 đã ghi: dữ liệu tổng hợp (random walk tự do, random walk có biên,
uniform ngẫu nhiên trong dải cố định, flat/gần-flat) đều **không** tái hiện được `childRange` bị
kéo rộng gấp 4.4 lần dải giá thật khi ép `vb.updateAutoRange()` chạy thật (kỹ thuật đã học từ
`BUG-034` §10.1). Không giữ lại các test này (`fix-bug-rule.md` §2 — chỉ chứng minh/loại trừ đúng
1 giả thuyết cho đúng 1 lần chạy, không có giá trị chẩn đoán lâu dài một khi đã ghi lại kết luận ở
đây).

### 6.4. Đã làm để lượt sau tự chẩn đoán được (giữ lại vĩnh viễn)

`_report_squashed_price_band()` (`chart_card.py`) giờ log thêm 3 trường vào **chính dòng
`[chart-range]`** đã có (không thêm dòng mới, đúng `logging-rule.md` §4):

- `windowed price band (x=[min_x, max_x]): [lo, hi]` — kết quả **thật** của
  `dataBounds(1, orthoRange=(min_x, max_x))`, đúng cách gọi pyqtgraph's `updateAutoRange()` thật
  dùng (khác với `price_bounds` ở đầu dòng — luôn là fallback KHÔNG-orthoRange, chỉ đúng khi không
  bug). Lần tới cảnh báo bắn, so 2 giá trị này lập tức biết `childRange` sai ở bước windowed hay
  không.
- `live candle forming: True/False` — loại trừ/xác nhận ngay giả thuyết §6.2 mà không cần đọc lại
  timeline log.

Không cần bước tái hiện riêng để bắt đầu chẩn đoán lần sau — chỉ cần `grep '\[chart-range\]'` khi
triệu chứng tái xuất là có đủ 2 dữ kiện còn thiếu ở lượt này.

### 6.5. Suggested next steps (thay thế §4 cũ)

1. Chờ log `[chart-range]` tái xuất hiện thật (đã tăng cường ở §6.4) — so `windowed price band` với
   `price_bounds` ở đầu dòng: nếu **windowed RỘNG HƠN** full-history, bug nằm trong
   `candlestick_item.py`'s bisect/cache (`_visible_history_slice`/`dataBounds`'s nhánh
   `orthoRange is not None`); nếu **bằng nhau**, bug không nằm ở `FastCandlestickItem` mà ở chỗ
   khác trong `ViewBox.updateAutoRange()` chưa xác định (khả năng: `targetRect[0]` không phải
   X-range đang hiển thị thật lúc đó — cần thêm log `vb.viewRange()` ngay TRƯỚC và NGAY SAU
   `_set_initial_view_range()` để đối chiếu).
2. Nếu `live candle forming: True` lúc cảnh báo bắn — giả thuyết §6.2 (dù đã thấy mâu thuẫn ở lần
   đọc code này) cần xem lại với đúng số liệu thật, không suy đoán.
3. Vẫn cần môi trường Windows/GUI thật hoặc Binance thật để tái hiện sống — headless không tái hiện
   được sau 4 bộ dữ liệu tổng hợp khác nhau (§6.3), khớp đúng kết luận `BUG-034` §6/§8.5.

## 7. Lượt điều tra 3 (2026-09-19) — môi trường mới (Xvfb thật, không phải offscreen), 2 giả
thuyết còn lại của §3/§6 bị loại trừ sống, **vẫn chưa root-cause**

**Trạng thái: vẫn Open.** Không đoán fix khi chưa có bằng chứng (`fix-bug-rule.md` §1).

### 7.1. Phát hiện quy trình: `Xvfb` có sẵn trong phiên này — không còn là "headless hoàn toàn"

`BUG-034` (4/5 lượt) và `BUG-110` (2 lượt trước) đều bị chặn bởi cùng một câu: "không có máy
Windows/GUI thật... môi trường phiên này cũng không có". Câu đó **không còn đúng nguyên vẹn**:
`Xvfb`/`xvfb-run` có sẵn trong container này, và `QT_QPA_PLATFORM=xcb` (khác hẳn `offscreen` —
`scripts/quick_surface_desktop_probe.py`/`python_backtest_pan_desktop_e2e.py` đã dùng đúng cách
này cho `BUG-115`/`BUG-009`) mở ra một **compositor X11 thật** — vòng paint/auto-range thật mà
`offscreen` bỏ qua, đúng thứ round 1 (§3) nghi ngờ là mấu chốt. Giới hạn còn lại, nói thẳng:
đây là **X11** (`xcb`), không phải **Wayland** — log gốc của bug này ghi `Qt platform=wayland`,
và không có compositor Wayland (`weston`/`Xwayland`) trong container để thử đúng nền tảng đó.
Bất cứ cơ chế nào đặc thù riêng cho mô hình frame-callback của Wayland (khác X11) vẫn nằm ngoài
tầm với của round này.

### 7.2. Giả thuyết §3 mục 2 / §6.5 mục 1 (Y auto-range tính theo TOÀN BỘ lịch sử, không phải
cửa sổ X đang hiển thị) — **loại trừ sống, đã tự sửa một lần nhầm ở giữa chừng**

Phương pháp: dựng `ChartCard` thật dưới `Xvfb`+`xcb` (không phải offscreen), nạp 500 nến qua
đúng `render_historical_data()` (đúng nhánh `setXRange` của `_set_initial_view_range`, >150
nến), 350 nến "cũ" dao động cực rộng (1000..5000) rồi 150 nến "cửa sổ" dải hẹp (~2485-2495,
khớp đúng số liệu log gốc), bơm event loop thật 3 giây (30 lần `QTest.qWait(100)`).

**Lần chạy đầu tiên "tái hiện" — nhưng sai vì lỗi ở chính dữ liệu tổng hợp, không phải app**:
`y-range` settle ở `[742, 5258]`, gấp 451x dải cửa sổ. Trace trực tiếp `dataBounds(ax=1,
orthoRange=...)` (monkeypatch, không suy đoán) cho thấy: `orthoRange` truyền vào **đúng** là
cửa sổ X hẹp thật (`[1788820642.4, 1788829940.0]`, khớp `setXRange`'s `first_t/last_t`) —
không phải toàn bộ lịch sử như giả thuyết ban đầu nghi — nhưng bisect-với-padding
(`visible_slice_indices`, `candle_width * DEFAULT_VISIBLE_PADDING_WIDTHS`) trả về `lo=344`,
tức **6 nến TRƯỚC** ranh giới cửa sổ (index 350) cũng bị kéo vào slice — và 6 nến đó, do cách
dựng dữ liệu tổng hợp (bước nhảy giá đột ngột đúng tại ranh giới), lại nằm trong vùng dao động
1000..5000. Đây là **lỗi của chính script chẩn đoán**, không phải bug thật — sửa lại bằng cách
chèn **50 nến đệm** dải hẹp giữa vùng dao động rộng và cửa sổ được test (thừa gấp ~8 lần mức
padding cần), chạy lại: `y-range` settle đúng `[2484.49, 2495.51]`, khớp sát dải giá cửa sổ
thật. **Kết luận: dưới compositor thật, `enableAutoRange(y=True)` + `setXRange()` tính Y đúng
theo cửa sổ X đang hiển thị, không lấy toàn bộ lịch sử** — giả thuyết này bị loại trừ sống,
không chỉ bằng toán học (§6.1) như trước.

### 7.3. Giả thuyết §6.2 (nến live glitch bị "đóng băng" vào Y-range) — loại trừ sống, đúng cách
gọi production

Phương pháp: 500 nến dải hẹp (không có gì rộng trong toàn bộ lịch sử), rồi gọi
`ChartCard.update_last_candle()` (method cấp `ChartCard`, không gọi thẳng
`candlestick.update_live_candle()` — lần thử đầu dùng nhầm cách gọi thấp hơn, khiến timestamp
của nến live nằm NGOÀI cửa sổ X hiện tại và bị `dataBounds()`'s `orthoRange` guard loại bỏ tầm
thường, không chứng minh được gì — `viewport.notify_new_data()` phải chạy cùng để view theo
kịp nến mới, đúng luồng thật) với high/low glitch cực đoan (`9000.0`/`100.0`). Kết quả: `y-range`
**đúng theo dự kiến** mở rộng để chứa glitch trong lúc nến đang live (`[-351, 9451]`) — không
phải bug, đó là hành vi TradingView-style auto-scale-theo-cửa-sổ đang làm đúng việc của nó. Sau
đó gọi `ChartCard.append_closed_candle()` với giá đóng BÌNH THƯỜNG (không glitch, đúng như dữ
liệu Binance thật gửi khi nến đóng): `y-range` **phục hồi ngay lập tức** về `[2481.24, 2497.76]`
và giữ nguyên qua 500ms bơm event loop thật tiếp theo — không bị "đóng băng" ở giá glitch. Khớp
với phân tích code ở §6.2 (đã loại trừ bằng đọc code), giờ có thêm bằng chứng sống.

### 7.4. Việc đã làm để loại trừ (không cần lặp lại)

- Cả 2 giả thuyết còn "sống" (chưa loại trừ hoàn toàn) tính đến hết lượt điều tra 2 — §3 mục 2
  (windowed vs full-history) và §6.2 (live-candle sticking) — giờ đã loại trừ bằng phản chứng
  **sống**, dưới compositor X11 thật (`Xvfb`+`xcb`), không chỉ headless synthetic (§6.3) hay
  toán học thuần (§6.1) như trước.
- Script chẩn đoán không giữ lại trong repo (`fix-bug-rule.md` §2 — chỉ chứng minh/loại trừ 1
  giả thuyết cho 1 lần chạy, không có giá trị chẩn đoán lâu dài một khi đã ghi kết luận ở đây,
  đúng tiền lệ §6.3). Phương pháp đủ chi tiết ở §7.2/§7.3 để dựng lại nếu cần.

### 7.5. Suggested next steps

1. **Không còn giả thuyết cụ thể nào chưa loại trừ** từ 3 lượt điều tra (§2, §6.1, §6.2, §6.3,
   §7.2, §7.3 đã loại hết những gì round 1-2 nêu ra). Lượt tới cần **bằng chứng mới**, không
   phải kiểm lại giả thuyết cũ.
2. Chờ log `[chart-range]` tái xuất hiện thật với 2 trường đã tăng cường ở §6.4
   (`windowed price band`, `live candle forming`) — đây vẫn là con đường nhiều thông tin nhất,
   và giờ **hai điểm dữ liệu đó đã tự loại trừ 2 trong 3 giả thuyết cụ thể mà round 1-2 nêu ra**
   nếu log tới cho thấy chúng khớp hành vi đúng — nghĩa là log tới, nếu vẫn squash, gần như chắc
   chắn chỉ đến việc log ĐÓ mới có ý nghĩa, không phải một trong hai điều đã loại ở đây.
3. **Manh mối mới, chưa thử**: log gốc ghi `Qt platform=wayland`, còn mọi lượt tái hiện (kể cả
   round 3 này) đều chỉ chạy được trên `xcb`/`offscreen`. Nếu có máy Linux có Wayland compositor
   thật (hoặc Windows — nền tảng gốc `BUG-034` cuối cùng tái hiện được), thử lại đúng §7.2/§7.3's
   kịch bản trên nền tảng đó trước khi nghĩ tới giả thuyết hoàn toàn mới.

## 8. Đóng hồ sơ 2026-09-19 — user quyết định dừng điều tra khi không tái hiện được

**Đóng vì không tái hiện được, không phải vì đã sửa.** Không có dòng code sản xuất nào đổi cho
bug này qua cả 3 lượt điều tra. Cùng tiền lệ `BUG-068`/`BUG-121` đã dùng trong repo này: đóng là
**tạm dừng**, không phải **kết luận** rằng bug không tồn tại.

### 8.1. Vì sao đóng hợp lý ở điểm này

Ba lượt điều tra, ba cách tiếp cận khác nhau, không lượt nào tái hiện được triệu chứng gốc:
- **Round 1** (§1-§5): đọc code + git blame loại trừ đúng cơ chế `BUG-034` (mọi overlay đã có
  `ignoreBounds=True`); nêu 2 giả thuyết cụ thể, chưa kiểm.
- **Round 2** (§6): loại trừ bằng toán học rằng padding của pyqtgraph không thể tạo dải rộng như
  log ghi (childRange bản thân đã sai, không phải do padding); loại trừ giả thuyết "1 nến đóng có
  wick bất thường thật" bằng đọc code; thử 4 bộ dữ liệu tổng hợp headless, không tái hiện; tăng
  cường log vĩnh viễn (`windowed price band`, `live candle forming`) để lượt log thật tiếp theo
  tự đủ bằng chứng.
- **Round 3** (§7): phát hiện `Xvfb`+`xcb` có sẵn trong container — compositor **thật**, không
  phải `offscreen` — và dùng nó để **loại trừ sống** (không chỉ bằng đọc code/toán học) cả 2 giả
  thuyết cụ thể còn lại của round 1-2.

Sau 3 lượt, **không còn giả thuyết cụ thể nào từ báo cáo gốc chưa bị loại trừ**. Giả thuyết cuối
cùng chưa thử — hành vi đặc thù riêng của Wayland (nền tảng log gốc ghi lại) khác X11 — không thể
thử tiếp trong container này (không có compositor Wayland). Tiếp tục điều tra từ đây cần **bằng
chứng mới** (log thật tái xuất hiện, hoặc một máy có Wayland/Windows thật), không phải kiểm lại
giả thuyết cũ bằng phương pháp khác.

### 8.2. Mức độ nguy hiểm thật, để cân nhắc đúng khi/nếu quay lại

🟡 P3 từ đầu: nến vẫn nhìn thấy được (18.77% trục, không phải ~0.88% gần-biến-mất như `BUG-034`),
không có báo cáo mất dữ liệu hay crash kèm theo — chỉ là trải nghiệm đọc chart kém hơn mong đợi
trong một khoảng thời gian ngắn (log không cho biết triệu chứng có tự hết hay không).

### 8.3. Việc đã làm, không cần lặp lại nếu mở lại

Log chẩn đoán tăng cường ở round 2 (§6.4: `windowed price band`, `live candle forming`) **vẫn còn
trong code** — không bị rút lại khi đóng hồ sơ này. Nếu triệu chứng tái xuất hiện, log tới sẽ có
đủ 2 trường đó ngay lập tức, không cần chờ thêm một lượt điều tra chỉ để thêm log.

### 8.4. Nếu quay lại

Mở **hồ sơ mới**, tham chiếu ngược file này và `BUG-034`. Bắt đầu từ:
1. Log `[chart-range]` thật tái xuất hiện — đọc `windowed price band` vs `price_bounds` đầu dòng
   theo đúng §6.5 mục 1 đã hướng dẫn, KHÔNG lặp lại §2/§6.1/§6.2/§6.3/§7.2/§7.3 đã loại trừ.
2. Nếu có máy Wayland thật hoặc Windows thật: thử lại đúng kịch bản §7.2 (windowed-vs-full-history)
   và §7.3 (live-candle glitch) trên nền tảng đó trước — đây là giả thuyết duy nhất còn chưa bị
   loại trừ trực tiếp.
