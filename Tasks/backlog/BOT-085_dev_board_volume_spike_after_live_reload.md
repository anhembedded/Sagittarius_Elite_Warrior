# Nhiệm vụ: Bug — Volume bar bất thường + nến bất thường sau khi Start Live reload chart

> Nguồn: 📄 [`BUG-003`](../bug_report/BUG-003.md) (ảnh chụp + event log Dev Board).
> **Chưa root-cause xong** — đây là giả thuyết có căn cứ từ đọc code, chưa tái hiện được
> bằng tay/test. Ghi rõ để không ai tưởng nhầm là đã điều tra xong.

## 1. Triệu chứng (từ ảnh chụp thật)

Dev Board, symbol ETHUSDT, khung 1m. Ngay sau chuỗi sự kiện Start Live (auto-sync), biểu
đồ hiện:

- 1 nến đỏ có bấc dài bất thường, giá rơi từ ~1884 xuống ~1881 trong khung nhìn hẹp.
- Đúng tại vị trí X đó, subplot Volume có **1 cột cao đột biến (~295.9)**, trong khi các
  cột xung quanh chỉ ~10–50 — gấp 6–10 lần nền xung quanh, không có cột nào khác cao
  tương đương trong toàn bộ khung nhìn.
- Ô crosshair hiện `Time: 2026-08-14 06:15:12 | Value: 295.9036` — khớp đúng dải giá trị
  trục Volume (0–300 trong ảnh), không phải trục giá (~1880–1885) → xác nhận `295.9036`
  là số đọc từ **subplot Volume**, không phải lỗi crosshair đọc nhầm subplot (đã đọc
  `crosshair_controller.py::_on_mouse_moved` — logic per-plot đúng, mỗi plot tự cập nhật
  label theo `y_val` của chính plot đó khi chuột nằm trong `sceneBoundingRect()` của nó).

Event log (mốc thời gian khớp với triệu chứng):

```
[13:01:09] Loading historical data from local database...
[13:01:09] Refreshed 2000 historical klines for ETHUSDT.
[13:01:54] Starting Live Stream (Auto-Sync)...
[13:01:54] Prepared 1 charts.
[13:01:54] Syncing missing data from Binance...
[13:02:00] Reloading historical data onto charts...
[13:02:00] Refreshed 2000 historical klines for ETHUSDT.
[13:02:00] Opening Websocket stream...
[13:02:00] Live stream for ['ETHUSDT'] is running.
[13:03:00] [Live] ETHUSDT candle closed at 1882.45
[13:04:00] [Live] ETHUSDT candle closed at 1881.59
```

→ Bất thường xuất hiện ngay quanh mốc **"Reloading historical data onto charts"
(13:02:00)** — đúng lúc chart chuyển từ dữ liệu lịch sử (`render_historical_data`/
`render_historical_volume`) sang nhận tick sống (`update_last_candle`/`update_last_volume`)
cho cùng 1 nến đang hình thành.

## 2. Giả thuyết (chưa xác nhận) — dựa trên đọc code thật

Đọc `chart_card.py` + `volume_renderer.py` + `dashboard_presenter.py::_on_history_reloaded`
(khớp đúng dòng log "Reloading historical data onto charts... Refreshed N historical
klines"):

- `_on_history_reloaded()` gọi `card.render_historical_data(mapped_data)` rồi
  `card.render_historical_volume(volume_data)` — `VolumeItem.render_historical()`
  **thay thế toàn bộ** `_timestamps`/`_heights`/`_brushes` và reset `_live_index = None`.
- Nếu **trước** lúc reload này, nến đang hình thành đã nhận ít nhất 1 tick sống
  (`update_last_volume()` → `VolumeItem.update_live()`, ghi vào `_live_index`), thì reload
  xoá sạch bar đó (vì DB chỉ có nến đã đóng, chưa có nến đang hình thành) — nến "biến mất"
  tạm thời.
- Tick sống **tiếp theo** sau reload gọi lại `update_last_volume()` → `_live_index is None`
  → nhánh **append bar mới** (`VolumeItem.update_live()` dòng 63-67) thay vì cập nhật tại
  chỗ. Nếu timestamp của tick này **không khớp chính xác** với timestamp nến cuối trong
  `volume_data` vừa reload (lệch biên nến do thời điểm reload rơi đúng ranh giới phút, hoặc
  giá trị "volume tích luỹ" websocket trả về đã cao sẵn do server tính từ đầu nến thật —
  xem ví dụ số Vol tích luỹ tăng dần trong log `BUG-002`: `85.97 → 86.03 → 86.58 →
  114.80 → 115.24` chỉ trong ~20s) → có thể tạo ra 1 bar mới với timestamp gần/trùng bar
  cuối vừa reload, khiến `visible_slice_indices()` (binary search giả định timestamps đã
  sắp xếp/duy nhất) vẽ ra hình dạng bất thường.
- **Chưa xác nhận được** đây có thực sự là nguyên nhân số `295.9` hay không — cần log
  thật có in giá trị `volume`/`timestamp` mỗi lần gọi `update_last_volume()`/
  `render_historical_volume()` quanh mốc 13:02:00 để so khớp.
- Nến giá (bấc dài 1884→1881) **nhiều khả năng là biến động thị trường thật** (khớp với
  log "candle closed at 1882.45" → "1881.59", một khoảng dao động hợp lý cho ETHUSDT 1m),
  không phải bug — chỉ nêu ra vì trùng thời điểm với cột Volume bất thường, không phải bản
  thân là triệu chứng cần sửa.

## 3. Các bước thực hiện

- [ ] **Tái hiện trước khi sửa** (đúng quy trình bug-fix của repo,
      [`.agents/rules/code-rule.md`](../../.agents/rules/code-rule.md)): thêm log tạm ở
      `update_last_volume()`/`render_historical_volume()`/`_on_history_reloaded()` in ra
      `timestamp`/`volume`/`_live_index` mỗi lần gọi, chạy lại đúng kịch bản (Load History
      → Start Live) vài lần để bắt lại đúng ca này.
- [ ] Xác nhận hoặc bác bỏ giả thuyết ở §2 bằng log thật, không suy đoán tiếp.
- [ ] Viết test tái hiện đúng bug (không phải chỉ test hành vi mong muốn) trước khi sửa.
- [ ] Sửa đúng chỗ tìm được — khả năng cao nằm ở việc đồng bộ `_live_index`/timestamp giữa
      `render_historical_volume()` (reset) và `update_last_volume()` (append) khi 2 lời
      gọi này xen kẽ nhau qua ranh giới reload, nhưng **không tự quyết cách sửa trước khi
      xác nhận nguyên nhân thật**.

## 4. Rủi ro / Lưu ý

- Đây là bug ở tầng UI-rendering (`sagittarius_engine`? hay `Sagittarius_Elite_Warrior`?)
  — `chart_card/` nằm trong `Sagittarius_Elite_Warrior/src/presentation/ui/components/`,
  không phải engine — chỉ commit + push submodule, không cần bump gì thêm ở repo cha nếu
  không đụng `sagittarius_engine/`.
- Không tự ý coi nến giá bất thường là cùng 1 bug với cột Volume — có thể là 2 hiện tượng
  độc lập trùng thời điểm ngẫu nhiên; đừng gộp sửa chung nếu điều tra cho thấy khác gốc.
- Cùng lớp rủi ro "nhân bản khi chạy lại/reload" đã ghi ở
  📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) lớp C
  (`BOT-067`) — nhưng `VolumeItem` không đi qua `ResourceScope`, nên cơ chế đó không tự
  bảo vệ được chỗ này; cần xác nhận có phải cùng họ bug hay là chỗ khác cần cơ chế riêng.

## 5. Phụ thuộc

- Không phụ thuộc task nào khác — độc lập, có thể làm bất cứ lúc nào.
- Liên quan (không phụ thuộc): `BOT-034` (auto-start/reload lifecycle),
  `BOT-067` (`ResourceScope`, cùng lớp lỗi "nhân bản khi chạy lại" nhưng khác cơ chế bảo
  vệ), `BOT-072` (bug chart khác cũng liên quan tới viewport/render sau khi dữ liệu đổi).
