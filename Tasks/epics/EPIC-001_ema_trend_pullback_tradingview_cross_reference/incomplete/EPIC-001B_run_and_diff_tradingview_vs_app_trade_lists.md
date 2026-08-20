# EPIC-001B — Chạy song song TradingView vs app, đối chiếu trade-by-trade

**Thuộc:** [EPIC-001](../README.md)
**Phụ thuộc:** [EPIC-001A](EPIC-001A_align_broker_simulator_config_for_comparison.md)
**Trạng thái:** 🔴 Chưa làm.

## Mục tiêu

Có bằng chứng thật (không phải suy luận) rằng `EmaTrendPullbackStrategy`
trên app cho đúng kết quả như Pine Script gốc chạy trên TradingView — hoặc
tìm ra chỗ lệch thật.

## Các bước

1. Trên TradingView: mở chart symbol/khung thời gian đã chọn, áp chiến lược
   "EMA Trend Confirm + Pullback + TP%" gốc, set input y hệt bộ giá trị đã
   chọn để test, đảm bảo đủ lịch sử nạp trước điểm bắt đầu so sánh (xem
   §"Warm-up" trong `README.md` của epic). Mở List of Trades trong Strategy
   Tester, ghi lại toàn bộ: entry time/price, exit time/price, side, lý do
   thoát (TP hay Touch EMA), PnL.
2. Trên app: set config theo đúng kết quả `EPIC-001A`, chạy Static Backtest
   cùng symbol/range/input, mở Trade Logs Table, export hoặc chép lại danh
   sách y hệt các trường trên.
3. Diff 2 danh sách theo thứ tự thời gian — với dung sai hợp lý (làm tròn
   giá/thời gian nếu 2 nguồn dữ liệu không khớp tuyệt đối đến từng mili giây
   /satoshi), không yêu cầu khớp bit-for-bit.
4. Với mỗi chỗ lệch: xác nhận đã thật sự kiểm tra hết checklist ở
   `README.md` của epic trước khi kết luận là bug (một cấu hình quên đồng bộ
   không phải là bug thật). Nếu vẫn lệch sau khi đã loại hết nguyên nhân cấu
   hình — mở `Tasks/bug_report/incomplete/BUG-XXX_....md` mới, tuân theo
   `.agents/rules/bug-fix-rule.md` (root cause trước, regression test fail
   đúng lý do trước khi sửa).
5. Ghi kết quả cuối (khớp hoàn toàn / khớp với N lệch đã giải thích được /
   N bug thật đã mở) vào chính file này khi đóng task, dời sang
   `../completed/`.

## Ngoài phạm vi

Không tự sửa code chiến lược khi chưa xác nhận chắc chắn đó là bug thật
(loại trừ hết khả năng lệch cấu hình trước) — tránh "sửa" một hành vi vốn dĩ
đã đúng chỉ vì 2 bên chưa cùng config.
