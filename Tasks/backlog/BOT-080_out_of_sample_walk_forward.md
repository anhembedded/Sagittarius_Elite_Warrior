# Nhiệm vụ: Kiểm định out-of-sample / walk-forward — chống overfitting

> Thuộc Epic [`BOT-078`](BOT-078_backtest_trustworthiness_epic.md). Nguồn: 📄
> [Rà soát định hướng App](../reports/app_direction_audit.md) §2.
>
> **Task lớn nhất epic, và quan trọng nhất về lâu dài.** Còn **câu hỏi mở cần user chốt**
> trước khi viết action item chi tiết — xem §4.

## 1. Vấn đề

```
grep -ri "walk.forward|out.of.sample|overfit|monte.carlo|in-sample" Tasks/ src/  → 0 kết quả
```

**Không một dòng nào** trong toàn bộ codebase lẫn backlog nhắc tới chống overfitting.

Trong khi đó [`BOT-044`](../completed/BOT-044_param_schema_core.md) →
[`BOT-046`](../completed/BOT-046_strategy_param_plumbing.md) →
[`BOT-047`](../completed/BOT-047_dynamic_params_form_ui.md) →
[`BOT-048`](../completed/BOT-048_migrate_default_scripts_to_inputs.md) đã hoàn thành
**nguyên bộ máy tinh chỉnh tham số**: form động theo schema, "Lưu & Re-Backtest",
"Khôi phục Mặc định".

→ App hiện cho phép: chỉnh tham số → chạy lại → thấy số đẹp hơn → chỉnh tiếp — **trên đúng
một khoảng dữ liệu**, không có bất kỳ rào chắn nào. Đây là định nghĩa của overfitting, và
nó đang được hỗ trợ bằng một UI tiện lợi.

## 2. Vì sao đây là lỗ hổng lớn nhất của sản phẩm

Một chiến lược overfit sẽ cho **equity curve đẹp, drawdown thấp, profit factor cao** trên
dữ liệu đã dùng để tinh chỉnh — rồi thua ngay khi gặp dữ liệu mới. App hiện **không có
cách nào** phân biệt:

- chiến lược thật sự có edge, và
- chiến lược chỉ đang thuộc lòng một đoạn lịch sử.

Cả hai trông **giống hệt nhau** trên màn hình Backtest hiện tại.

⚠️ **So sánh mức độ ưu tiên với [`BOT-073`](BOT-073_realtime_tick_backtest_epic.md)**:
`BOT-073` (Realtime backtest) làm kết quả *chân thực hơn về cơ chế*. Nhưng nếu tham số đã
overfit thì kết quả chân thực đó **vẫn vô nghĩa** — chỉ là một con số sai một cách chính
xác hơn. Task này nên xong **trước khi** ai dùng `BOT-047` để tinh chỉnh nghiêm túc.

## 3. Hướng tiếp cận đề xuất (chưa phải action item)

Từ đơn giản tới phức tạp — **không cần làm hết**, làm cái đầu tiên đã có giá trị lớn:

1. **Tách in-sample / out-of-sample đơn giản** — chia khoảng backtest thành 2 phần (vd
   70/30), tinh chỉnh trên phần đầu, **báo cáo riêng** kết quả phần sau. Rẻ nhất, chặn
   được phần lớn ca overfit thô.
2. **Walk-forward** — trượt cửa sổ train/test qua toàn bộ lịch sử, ghép kết quả các đoạn
   test lại. Chuẩn mực trong ngành, nhưng tốn thời gian chạy gấp N lần.
3. **Monte Carlo / xáo thứ tự lệnh** — đánh giá độ bền của equity curve. Để sau cùng, có
   thể không bao giờ cần.

## 4. ❓ Câu hỏi cần user chốt — **không tự quyết**

1. **Chọn mức nào ở §3?** Đề xuất bắt đầu ở mức 1 (in-sample/out-of-sample), nhưng đây là
   đánh đổi giữa độ nghiêm ngặt và thời gian chạy — thuộc quyền user.
2. **Tỉ lệ chia mặc định?** 70/30, 80/20, hay cho user tự nhập?
3. **Bắt buộc hay tuỳ chọn?** Có nên *ép* mọi lần "Lưu & Re-Backtest" đều chạy kiểm định
   ngoài mẫu (an toàn hơn, chậm hơn), hay để nó là một nút riêng (nhanh hơn, dễ bị bỏ
   qua)?
4. **Hiển thị thế nào khi lệch nhau nhiều?** Nếu in-sample lãi 50% mà out-of-sample lỗ
   20% — cảnh báo cỡ nào là đủ mạnh mà không phiền?

**Không bắt đầu code trước khi chốt 4 câu này** — cùng lý do `BOT-042` từng phải dừng
lại hỏi: đây là quyết định sản phẩm, không phải chi tiết cài đặt.

## 5. Rủi ro / Lưu ý

- **Chi phí thời gian chạy**: walk-forward nhân thời gian backtest lên N lần. Kết hợp với
  [`BOT-076`](BOT-076_realtime_backtest_engine.md) (tick-level, đã chậm sẵn) có thể thành
  không dùng được. Cân nhắc giới hạn: walk-forward **chỉ cho Static**, không cho Realtime.
- **Không tự động hoá việc tối ưu tham số** (grid search/genetic). Nghe hợp lý nhưng sẽ
  biến app thành cỗ máy overfit *nhanh hơn* nếu chưa có rào chắn này. Nếu muốn, đó là task
  riêng và **phải sau** task này.
- Dùng chung `PaperExchange`/`BacktestResult` — mỗi đoạn train/test là một
  `BacktestResult` độc lập, không sửa engine.

## 6. Phụ thuộc

- [`BOT-047`](../completed/BOT-047_dynamic_params_form_ui.md) ✅ — bộ máy tinh chỉnh tham
  số mà task này tồn tại để bảo vệ.
- [`BOT-021`](../completed/BOT-021_static_backtest_execution_engine.md) ✅ — chạy nhiều
  lần trên nhiều khoảng.
- [`BOT-079`](BOT-079_fee_transparency_and_trade_frequency.md) — nên xong trước, vì kết
  quả out-of-sample cũng cần đọc đúng (không lẫn phí vào edge).
- 📄 [Rà soát định hướng App](../reports/app_direction_audit.md) §2.
