# Nhiệm vụ: Trực Quan Hóa Biểu Đồ & Kiểm Thử Đối Soát Backtest (BOT-111)

**Mã Task:** `BOT-111`  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** 🔴 **Backlog (Chờ triển khai)**  
**Thuộc Epic:** [`BOT-109`](BOT-109_golden_strategy_ema_trend_confirm_pullback_epic.md) (Chuẩn Tham Chiếu Vàng)  
**Phụ thuộc:** [`BOT-110`](../completed/BOT-110_ema_trend_confirm_pullback_strategy.md) ✅

---

## 1. Mục Tiêu

Hoàn thiện hiển thị trực quan cho chiến lược *"EMA Trend Confirm + Pullback + TP%"* trên biểu đồ Backtest (`ChartCard` / Native Chart) và bảng lịch sử lệnh (`TradeLogsTable`), bảo đảm trải nghiệm quan sát số liệu chân thực như TradingView.

---

## 2. Các Hạng Mục Công Việc

1. **Hiển thị Đường Chỉ Báo (Indicator Lines)**:
   - Đường EMA dài (200) màu đỏ (`#f6465d`), độ dày 2.
   - Đường EMA vào lệnh (50) màu xanh dương (`#2962ff`), độ dày 1.
2. **Hiển thị Trade Markers**:
   - Long Entry: Tam giác hướng lên màu xanh lá (Green Triangle Up, text="L").
   - Short Entry: Tam giác hướng xuống màu đỏ (Red Triangle Down, text="S").
   - Exit TP: Marker màu vàng chốt lời (text="TP 2.0%").
   - Exit Touch EMA: Marker màu cam/xám thoát lệnh chạm EMA.
3. **Bảng Lịch Sử Lệnh (Trade Logs Table)**:
   - Hiển thị đầy đủ cả tab **Tất cả**, **Mua (LONG)** và **Bán (SHORT)**.
   - Hiển thị PnL và Return % đúng màu xanh/đỏ cho cả lệnh Long và Short.
4. **Kiểm thử Toàn Diện**:
   - Viết Integration / Sanity tests cho luồng chạy Backtest với `EmaTrendPullbackStrategy`.
   - Chạy `.\scripts\ci-local.ps1 -Full` đạt 100% xanh.
