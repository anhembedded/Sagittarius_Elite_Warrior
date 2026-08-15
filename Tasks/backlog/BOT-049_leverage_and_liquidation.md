# Nhiệm vụ: Đòn bẩy (Leverage) & Thanh lý (Liquidation)

> Thuộc [Epic BOT-040](BOT-040_backtest_screen_full_feature_epic.md), Phase 0.
> **Task 2/3** nhóm "PaperExchange nâng cao":
> [`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md) → `BOT-049`
> (file này) → [`BOT-050`](BOT-050_short_selling_support.md).
> Phụ thuộc `BOT-041`.

## 1. Mục tiêu

Thêm đòn bẩy kiểu futures (mockup: dropdown "5x Futures") vào exchange giả
lập — **kèm thanh lý**. Không có liquidation thì "leverage" chỉ là số nhân
trang trí, không phản ánh đúng rủi ro thật của futures, và kết quả backtest
sẽ lạc quan sai lệch một cách nguy hiểm.

## 2. Các bước thực hiện (Action Items)

- [ ] Chọn **isolated margin** (mỗi lệnh 1 khoản margin độc lập) thay vì cross
  margin — đơn giản hơn, đủ cho mô phỏng, và là mặc định phổ biến khi backtest.
  **Xác nhận với user** nếu họ muốn cross.
- [ ] Công thức margin: `margin = notional / leverage`. Sizing của `BOT-041`
  (theo risk %) phải phối hợp đúng với leverage — 2 cơ chế cùng quyết định
  quantity, cần chốt cái nào ưu tiên khi mâu thuẫn (vd risk% cho ra size lớn
  hơn margin cho phép).
- [ ] **Liquidation price** — công thức phải **đối chiếu ít nhất 1 nguồn tham
  khảo thật** (vd tài liệu Binance Futures về isolated liquidation price),
  **không tự suy diễn**. Ghi nguồn vào docstring.
- [ ] Kiểm tra chạm liquidation mỗi bar bằng `high`/`low` (cùng cơ chế SL/TP
  của `BOT-041`); liquidation **ưu tiên trước** SL/TP nếu cùng nến (sàn thật
  thanh lý trước khi lệnh SL của user khớp).
- [ ] Lệnh bị thanh lý ghi `exit_reason = LIQUIDATION` (enum đã khai báo sẵn ở
  [`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md)) và tính là **mất
  toàn bộ margin**, không phải PnL âm thông thường — ảnh hưởng
  `BacktestMetrics` (`gross_loss`, `largest_losing_trade`).
- [ ] `Trade` thêm `leverage` + `liquidated: bool` (hoặc suy ra từ
  `exit_reason`, tránh dữ liệu trùng lặp — chọn 1).
- [ ] Test tính tay: liquidation price đúng với ví dụ từ nguồn tham khảo; lệnh
  bị thanh lý làm balance về đúng mức kỳ vọng; metrics phản ánh đúng.

## 3. Rủi ro / Lưu ý

- **Rủi ro sai số cao nhất trong cả Epic.** Liquidation price tính sai → toàn
  bộ kết quả backtest có đòn bẩy đều vô nghĩa, mà lại **trông có vẻ hợp lý** —
  loại lỗi nguy hiểm nhất. Bắt buộc đối chiếu nguồn ngoài.
- Chưa tính phí funding (futures thật có funding rate mỗi 8h) — **cố ý bỏ
  qua** ở task này, ghi rõ là hạn chế đã biết. Nếu cần, tách task riêng.

## 4. Phụ thuộc

- [`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md) — cơ chế kiểm
  tra chạm giá mỗi bar + sizing.
- [`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md) — `exit_reason`.
