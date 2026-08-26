# BUG-034 — Dev Board Live Chart: giá nến không hiển thị, trục Y bị auto-range sai thang đo

**Reported date:** 2026-08-23
**Severity:** Chưa đánh giá (chưa điều tra)
**Status:** 🔴 Open — chỉ mới ghi nhận hiện tượng, **chưa điều tra root cause** (theo yêu cầu
người báo).

---

## 1. Hiện tượng (Symptom)

Trên màn hình **Dev Board**, sau khi bấm "Start Live" cho symbol `ETHUSDT` (khung `1m`),
luồng dữ liệu live khởi động thành công (xem log bên dưới) nhưng **vùng vẽ nến chính của
biểu đồ trống hoàn toàn** — không thấy thân nến/wick nào, dù dữ liệu giá đang chảy vào đúng.

Ảnh chụp màn hình do người dùng cung cấp cho thấy:

- Panel "Developer Board (Live...)" bên phải hiển thị symbol `ETHUSDT`, giá hiện tại
  `2,425.x` (góc trên bên phải).
- Toolbar chart chọn khung `1m` (đã bấm sáng).
- Dòng đọc OHLC ở crosshair phía trên chart: `08-22 08:15:59  O 2439.8200 H 2440.1600
  L 2439.4500 C 2440.0700 (+0.01%)` — các giá trị này nằm đúng vùng giá ETH thật (~2400),
  có vẻ hợp lý.
- 4 đường EMA (`ema_20`, `ema_50`, `ema_100`, `ema_200`) hiển thị trong legend với giá trị
  cũng nằm đúng vùng ~2420–2437 — hợp lý.
- **Tuy nhiên trục Y của chart chính lại hiện thang đo `-50, 0, 50, 100`** — hoàn toàn không
  khớp với vùng giá ~2400 mà OHLC/EMA đang báo. Không có thân nến nào hiển thị được trong
  vùng plot chính (khoảng giữa 4 đường EMA và biểu đồ volume phía dưới trống trơn, chỉ có nền
  đen).
- Có 1 đường kẻ ngang đứt nét kèm nhãn giá trị `12.6405` xuất hiện giữa chart — con số này
  cũng không khớp với bất kỳ ngữ cảnh giá/thang đo nào đang hiển thị.
- Biểu đồ **volume** ở dưới cùng (thang `0–500`) có vẻ vẫn vẽ bar bình thường, không trống.
- Panel "System Monitor" (log) bên phải cho thấy chuỗi khởi động Live Stream **hoàn tất bình
  thường, không có lỗi/exception nào được log**:

```text
[16:16:03] System Health: HEALTHY (DB: OK, Container: OK, EventBus: OK)
[00:47:44] Starting Live Stream (Auto-Sync)...
[00:47:45] Prepared 1 charts.
[00:47:45] Syncing missing data from Binance...
[00:47:56] Reloading historical data onto charts...
[00:47:56] Refreshed 2000 historical klines for ETHUSDT.
[00:47:56] Opening Websocket stream...
[00:47:56] Live stream for ['ETHUSDT'] is running.
[00:48:00] [Live] ETHUSDT candle closed at 2425.11.
```

(Lưu ý: dòng `[16:16:03]` và các dòng `[00:47:xx]`/`[00:48:00]` không cùng một mốc thời gian
thực — có thể là 2 phiên/2 lần khởi động khác nhau bị gộp trong cùng khung log hiển thị, hoặc
đơn giản là đồng hồ hiển thị theo giờ khác nhau. Ghi lại nguyên văn, không diễn giải thêm.)

## 2. Ảnh chụp màn hình

Người dùng đã cung cấp ảnh chụp trực tiếp trong hội thoại (không có file lưu sẵn trên đĩa để
đính kèm vào report này) — mô tả chi tiết ở mục 1 dựa trên đúng nội dung ảnh đó.

## 3. Kỳ vọng (Expected)

Trục Y của chart chính phải auto-range theo đúng vùng giá thực của nến đang vẽ (ví dụ ~2400
cho ETHUSDT), và thân nến phải hiển thị được trong vùng plot — giống cách chart hoạt động ở
màn hình Backtest.

## 4. Lượt điều tra 1 (2026-08-23) — chưa ra root cause, nhưng đã loại trừ được 4 giả thuyết

**Trạng thái: vẫn Open.** Ghi lại để lượt sau không làm lại từ đầu.

### Đã loại trừ, kèm bằng chứng

| # | Giả thuyết | Kết quả | Bằng chứng |
| :--- | :--- | :--- | :--- |
| 1 | Indicator thang dao động bị vẽ `overlay` lên plot giá, kéo auto-range | ❌ Sai | `macd_full_script.py` và `rsi_14_script.py` đều `overlay = False`; `IndicatorScriptRunner` gán `overlay=script.overlay` đúng ở cả 2 chỗ (dòng 146, 162) rồi rẽ `add_overlay_indicator`/`add_subplot_indicator` theo đúng cờ đó |
| 2 | `DevIndicatorScript` (`overlay=True`, chạy trên Dev Board) vẽ RSI/MACD lên plot giá | ❌ Sai | Nó *khai báo* `rsi(14)`/`macd()`/`level(70)` nhưng chỉ dùng cho điều kiện/marker. Toàn bộ lệnh `plot()` của nó là `EMA 12`, `EMA 26`, `WMA 20`, `close + session_range` — đều thang giá |
| 3 | `add_subplot_indicator` rò dữ liệu subplot sang plot chính | ❌ Sai | `IndicatorManager.add_subplot()` tạo `PlotItem` riêng qua `_plot_layout.add_subplot()` rồi mới `plot()` lên đó |
| 4 | Dữ liệu nến bị map sai thang | ❌ Sai | `kline_mapping.map_klines()` lấy thẳng `open/high/low/close_price`, không chia/nhân gì |

### Probe tái hiện — đường đi bình thường HOÀN TOÀN ĐÚNG

Dựng `ChartCard` thật, lặp lại đúng chuỗi Dev Board (2000 nến ETH ~2425 → volume →
4 EMA overlay → RSI subplot 0–100 → MACD subplot ±45), in dải Y sau từng bước:

```
0. chưa có data                    Y=[0.00, 1.00]
1. sau render_historical_data      Y=[2408.96, 2442.34]
2. sau render_historical_volume    Y=[2408.96, 2442.34]
3. sau 4 EMA overlay               Y=[2408.96, 2442.34]
4. sau subplot rsi_14 (0..100)     Y=[2408.76, 2442.54]
5. sau subplot macd (-45..45)      Y=[2406.28, 2442.87]
```

Y bám đúng ~2425 xuyên suốt; **subplot không hề rò sang plot chính**. Đáng chú ý: dải
mặc định khi chưa có data là `[0, 1]`, **không phải** `-50..100` — nên `-50..100` không
đến từ trạng thái "plot rỗng".

### Ghi chú đọc lại triệu chứng

- Con số `12.6405` có **đúng 4 chữ số thập phân**, khớp format `f"{name}: {y[-1]:.4f}"` của
  legend (`IndicatorManager.update_data`) và cũng khớp nhãn crosshair. **Không nên coi nó là
  giá trị của một indicator** cho tới khi có bằng chứng khác.
- Vì subplot RSI/MACD (nếu bật) nằm **giữa** plot chính và volume, có khả năng dải
  `-50..100` nhìn thấy trong ảnh là trục của *subplot đó*, còn plot chính thì rỗng và bị
  ép mỏng. Chưa xác nhận được — cần ảnh/log của đúng lần tái hiện.

### Đã làm để lượt sau tự chẩn đoán được

Dòng log `[chart-data]` sẵn có trong `ChartCard.render_historical_data()` trước đây chỉ
ghi số nến + **x-range** — không đủ để phân biệt hai khả năng hoàn toàn khác nhau:
"data không tới card này" và "data tới rồi nhưng range bỏ qua nó". Đã bổ sung vào **chính
dòng đó** (không thêm dòng mới, không thêm nhiễu):

- `price [min_low, max_high]` — thang giá mà dữ liệu thật sự mang
- `y-range [min, max]` — dải mà view thật sự lấy
- `autorange=[x, y]` — auto-range còn bật không

```
[chart-data] ChartCard(ETHUSDT): loaded 2000 candles spanning [...]
| price [2408.0137, 2441.9807] | initial view x-range [...]
| y-range [2406.4262, 2443.5681] | autorange=[False, True] | chart type=candlestick
```

## 5. Suggested next steps

1. **Tái hiện với `--debug`** rồi `grep '\[chart-data\]' logs/debug-*.log`. Ba khả năng,
   dòng log phân biệt được ngay:
   - `loaded 0 candles` → data không tới card đang hiển thị (nghi vấn re-key card ở
     `_ensure_chart_cards`).
   - `price [~2400]` nhưng `y-range [-50, 100]` → range bỏ qua data; đào tiếp
     `_set_initial_view_range()` / `_apply_view_bounds()`.
   - `autorange=[..., False]` → auto-range Y đã bị tắt ở đâu đó.
2. Chụp lại ảnh **kèm cả vùng subplot**, để xác nhận `-50..100` là trục của plot chính hay
   của subplot RSI/MACD.
3. Chỉ sau khi có 1 hoặc 2 mới viết regression test — hiện chưa biết đủ để test đúng chỗ.

## 6. Lượt điều tra 2026-08-26 — thêm 1 giả thuyết **được xác nhận thật** (không phải bị loại),
nhưng **không đóng được bug này**

**Trạng thái: vẫn Open.** Dựng lại đúng chuỗi Dev Board (real `ChartCard`, real
`IndicatorScriptRunner`, real `dev_showcase`+`rsi_14`+`macd_full`, 2000 nến tổng hợp) headless
trên Linux (`QT_QPA_PLATFORM=offscreen`, không cần Binance thật) để tự động hoá bước 1–2 ở trên
mà không cần máy Windows/GUI thật. Kết quả:

- **Y-range của main plot bám đúng theo dữ liệu tổng hợp** (không tái hiện được `-50..100`) — dữ
  liệu tổng hợp tự nó là random walk không có mean-reversion nên trôi giá hợp lệ, không phải bug.
  Nghĩa là: hạ tầng auto-range mô tả ở §4 (main plot chỉ nhận đúng item của chính nó) **vẫn đúng**
  với cấu hình được thử — giả thuyết "range bỏ qua data" (bước 1, gạch 2) **chưa được xác nhận**
  bằng repro này.
- Nhưng: phát hiện một defect **thật, khác, đã xác nhận** trong cùng subsystem — `macd_full`
  (3 line: MACD/Signal/Histogram) tạo **3 subplot row riêng** thay vì 1 row chung, khiến main
  plot bị ép chỉ còn ~3/8 chiều cao khi bật MACD, và crosshair bị đăng ký trùng. Đã tách hồ sơ
  riêng: [`BUG-053`](../completed/BUG-053_multi_line_subplot_script_gets_one_row_per_line.md) —
  root-caused, regression-tested (red→green), **đã sửa và đóng**.
- **Vì sao BUG-053 không đóng được BUG-034 này:** repro headless ở trên đã bật đúng tổ hợp script
  Dev Board đã dùng (dev_showcase + rsi_14 + macd_full) và chạy qua đúng `IndicatorScriptRunner`
  thật — nếu việc ép main plot xuống 3/8 chiều cao đã đủ để tạo ra đúng triệu chứng "-50..100 +
  candle rỗng", repro này lẽ ra phải lộ ra dấu hiệu bất thường trong Y-range hoặc x-range. Nó
  không lộ. Nên khả năng cao nhất: BUG-053 là một defect thật, đáng sửa độc lập, nhưng **không
  phải** cơ chế duy nhất (có thể không phải cơ chế nào) tạo ra triệu chứng BUG-034 đã báo.
- **Việc còn thiếu, không đổi so với §5:** vẫn cần ảnh chụp thật + log `--debug` từ một lần tái
  hiện sống (GUI thật hoặc Binance thật) — headless repro chỉ dựng lại được *cấu trúc* wiring, không
  dựng lại được bất cứ thứ gì phụ thuộc timing thật (live tick xen giữa `render_historical_data()`
  và lúc script subplot được tạo, thứ tự Qt event loop, DPR/backend thật). Bước 1–2 ở §5 **vẫn còn
  nguyên giá trị**, chưa bước nào trong đó được thực hiện bằng phiên này.
