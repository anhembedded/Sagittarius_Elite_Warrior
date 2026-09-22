# Nhiệm vụ: Phân tích MAE / MFE (Maximum Adverse / Favorable Excursion)

**Mã Task:** `BOT-106B`  
**Thuộc Epic:** [`BOT-106`](BOT-106_advanced_financial_analytics_and_reports_epic.md)  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** ✅ Done (2026-09-22)  
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
   - `PaperExchange`: Cập nhật `mae` và `mfe` của `OpenPosition` (`modules/backtesting/domain/open_position.py` từ `EPIC-025` PR 3.1c-2) trên từng nến/tick giá đi qua trong khi vị thế đang mở.
2. **Presentation**:
   - Hiển thị MAE / MFE trong dòng chi tiết mở rộng của Trade Logs (`BackTestTradeLogs.qml` dòng §2.2).

## Implementation notes (2026-09-22)

- **Domain, done**: `Trade.mae_percent`/`Trade.mfe_percent` (`contracts/trade.py`) và `OpenPosition.mae_percent`/`.mfe_percent` (`domain/open_position.py`), cả hai mặc định `0.0` — cùng lý do `leverage` (`BOT-049`): mọi `Trade(...)` cũ trong test suite vẫn dựng được không sửa. `PaperExchange._update_excursion_tracking(high, low)` (`domain/paper_exchange.py`) widen (`min`/`max`, không ghi đè) MAE/MFE của **mọi** vị thế đang mở mỗi lần `check_intrabar_stops()` chạy — trước cả bước kiểm tra thanh lý, nên nến cuối cùng khiến vị thế bị thanh lý vẫn được tính vào MAE. `pnl_percent` dùng cùng công thức phần trăm-trên-margin với `Trade.pnl_percent` (qua `FillPricing.mark_to_market`), nên hai trường so sánh trực tiếp được với nhau.
- **6 test mới** trong `tests/unit/modules/backtesting/domain/test_paper_exchange.py` (mặc định 0 khi chưa từng thấy nến nào; widen qua nhiều nến chứ không ghi đè bằng nến cuối — mutation-verify: đổi `min`/`max` thành gán trực tiếp, test tương ứng đỏ đúng lý do; đối xứng LONG/SHORT; MAE vẫn ghi nhận đúng ở nến thanh lý; hai vị thế pyramid theo dõi độc lập nhau). Toàn bộ 66 test trong file xanh; `ruff`/`mypy` sạch.
- **Presentation: ngoài phạm vi.** `BackTestTradeLogs.qml` không còn tồn tại — QML đã bị gỡ khỏi codebase này trước `EPIC-025` (đã xác nhận ở phiên trước). Domain-only là điểm dừng đúng, cùng khuôn với `BOT-106C`.
- **Giới hạn thật, phát hiện khi làm task này — [`BUG-133`](../bug_report/incomplete/BUG-133_tick_backtest_never_checks_intrabar_stops.md) (Open):** `RunHistoricalTickBacktestCommandHandler` (`BOT-076`, Historical Tick Backtest) **không bao giờ gọi** `check_intrabar_stops()` — không riêng MAE/MFE, mà cả SL/TP (`BOT-041`) và thanh lý (`BOT-049`) cũng vô hiệu ở chế độ này từ trước khi task này tồn tại. MAE/MFE do đó **chỉ hoạt động ở chế độ Static Backtest** cho tới khi `BUG-133` đóng — không phải một giới hạn riêng của task này, mà một khoảng trống có sẵn task này thừa hưởng. Không mở rộng phạm vi để tự sửa `BUG-133` ở đây (`ONBOARDING.md` §7): đã ghi hồ sơ riêng.
