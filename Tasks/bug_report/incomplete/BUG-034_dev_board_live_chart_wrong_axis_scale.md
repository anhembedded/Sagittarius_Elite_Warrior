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

## 4. Chưa làm (theo yêu cầu)

Báo cáo này **chỉ ghi nhận hiện tượng**, chưa xác định root cause, chưa đọc code liên quan
(candle series binding, auto-range logic của chart Dev Board, v.v.), và chưa có Suggested Next
Steps — để dành cho lượt điều tra sau.
