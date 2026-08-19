# Nhiệm vụ: Phân tích MAE / MFE (Maximum Adverse / Favorable Excursion)

**Mã Task:** `BOT-106B`  
**Thuộc Epic:** [`BOT-106`](BOT-106_advanced_financial_analytics_and_reports_epic.md)  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** 🔴 **Backlog**  
**Dependencies:** [`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md), [`BOT-057`](../completed/BOT-057_backtest_trade_logs_table.md)

---

## 1. Khái niệm & Giá trị MAE / MFE

- **MAE (Maximum Adverse Excursion)**: Mức lỗ tạm thời sâu nhất (% hoặc $) mà vị thế từng phải chịu đựng trong suốt thời gian mở lệnh trước khi đóng.
  - *Ý nghĩa*: Cho biết vị thế có bị "gồng lỗ" quá mức hay không. Giúp xác định mức đặt Stop Loss tối ưu (chặt chẽ nhưng không bị quét oan).
- **MFE (Maximum Favorable Excursion)**: Mức lãi tiềm năng cao nhất (% hoặc $) mà vị thế từng đạt được trước khi đóng.
  - *Ý nghĩa*: Cho biết chiến lược có để "lãi trôi đi mất" hay không. Giúp xác định điểm đặt Take Profit hoặc Trailing Stop tối ưu.

---

## 2. Triển khai

1. **Domain**:
   - `Trade`: Thêm 2 trường `mae_percent: float` và `mfe_percent: float`.
   - `PaperExchange`: Cập nhật `mae` và `mfe` của `_OpenPosition` trên từng nến/tick giá đi qua trong khi vị thế đang mở.
2. **Presentation**:
   - Hiển thị MAE / MFE trong dòng chi tiết mở rộng của Trade Logs (`BackTestTradeLogs.qml` dòng §2.2).
