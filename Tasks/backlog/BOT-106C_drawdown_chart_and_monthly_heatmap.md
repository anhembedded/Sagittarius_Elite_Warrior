# Nhiệm vụ: Biểu đồ Sụt giảm Vốn (Drawdown Underwater) & Bảng nhiệt Lợi nhuận Hàng tháng (Monthly Heatmap)

**Mã Task:** `BOT-106C`  
**Thuộc Epic:** [`BOT-106`](BOT-106_advanced_financial_analytics_and_reports_epic.md)  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** 🔴 **Backlog**  
**Dependencies:** [`BOT-056`](../completed/BOT-056_backtest_chart_canvas.md), [`BOT-055`](../completed/BOT-055_backtest_performance_metrics_panel.md)

---

## 1. Mục tiêu

Xây dựng 2 component trực quan hóa dữ liệu hiệu suất chuyên sâu cho màn Backtest:
1. **Drawdown Underwater Chart (Biểu đồ Sụt giảm Vốn)**:
   - Thể hiện mức sụt giảm vốn từ đỉnh cũ (theo %) kéo dài theo trục thời gian dưới dạng diện tích màu đỏ (Underwater Area Chart).
   - Giúp người dùng nhìn rõ ngay các giai đoạn "khủng hoảng" của chiến lược.
2. **Monthly / Annual Returns Heatmap (Bảng nhiệt Lợi nhuận Tháng & Năm)**:
   - Lưới ma trận 12 cột (Tháng 1 $\rightarrow$ Tháng 12) $\times$ $N$ dòng (Năm 2022, 2023, 2024...).
   - Ô có màu xanh đậm (lãi cao), xanh nhạt (lãi vừa), đỏ nhạt (lỗ nhẹ), đỏ đậm (lỗ nặng). Cột cuối cùng tổng kết `YTD Return (%)`.

---

## 2. Triển khai

1. **Domain / Application**:
   - `monthly_returns_calculator.py`: Nhóm `equity_curve` theo tháng/năm, tính toán ROI từng tháng.
   - `drawdown_series_calculator.py`: Tính toán chuỗi % sụt giảm `drawdown_curve: list[tuple[float, float]]`.
2. **Presentation**:
   - Component QML `MonthlyReturnsHeatmap.qml` & Subplot `DrawdownUnderwaterCard.qml`.
