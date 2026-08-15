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

## 4. ✅ Câu hỏi đã chốt (14/08)

1. **Mức**: Mức 1 — tách in-sample/out-of-sample đơn giản. Walk-forward/Monte Carlo để sau.
2. **Tỉ lệ**: **70/30 cố định** (không cho user tự nhập — tránh chỉnh tỷ lệ tới khi ra số
   đẹp, tự đánh bại mục đích chống overfit của chính task này).
3. **Bắt buộc**: **Có** — mọi lần chạy backtest đều tính cả in-sample lẫn out-of-sample,
   không có nút/checkbox riêng để bỏ qua.
4. **Hiển thị lệch nhau nhiều**: dòng cảnh báo riêng, cùng cơ chế `resultWarningText` vừa
   làm ở `BOT-079` (không phải badge đỏ to, không nhuộm đỏ toàn màn hình).
5. **Kết quả nào là "chính"** (câu hỏi phát sinh khi bắt tay code, không nằm trong 4 câu
   gốc): stat cards/chart/trade log hiện có **vẫn gắn với kết quả full-range, không đổi**.
   In-sample/out-of-sample là thông tin **thêm vào**, không thay thế.

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
- [`BOT-079`](../completed/BOT-079_fee_transparency_and_trade_frequency.md) — nên xong trước, vì kết
  quả out-of-sample cũng cần đọc đúng (không lẫn phí vào edge).
- 📄 [Rà soát định hướng App](../reports/app_direction_audit.md) §2.

## 7. Kết quả triển khai thực tế

- **Domain** (`domain/backtesting/`, 2 file mới):
  - `out_of_sample_split.py`: `split_klines_for_out_of_sample(klines, ratio=0.7)` — chia
    theo **số lượng nến** (không theo thời gian), thuần Python.
  - `out_of_sample_validation.py`: `OutOfSampleValidation` (`in_sample`/`out_of_sample`:
    2 `BacktestResult` độc lập, `in_sample_ratio`) + property `has_high_divergence` —
    hằng số `OUT_OF_SAMPLE_DIVERGENCE_WARNING_POINTS = 30.0` (điểm % — chưa validate,
    cùng caveat `BOT-079`). **Chỉ bật khi in-sample tốt hơn out-of-sample** — chiều ngược
    lại (out-of-sample tốt hơn) không phải dấu hiệu overfit.
- **`BacktestResult`** thêm field `out_of_sample: OutOfSampleValidation | None = None` —
  optional, mọi construction cũ (test, `.compute()`) không cần sửa.
- **`RunStaticBacktestCommandHandler`**: tách vòng lặp mô phỏng thành `_simulate(klines,
  command)` dùng chung cho cả full-range lẫn 2 nửa split — **mọi lần chạy đều tự động
  tính in-sample/out-of-sample** (đúng quyết định "bắt buộc"), trả `None` cho
  `out_of_sample` khi khoảng quá ngắn để chia (thay vì crash hay hiện 0-trade gây hiểu
  nhầm "không có edge"). Full-range vẫn tính y hệt cũ — `trades`/`equity_curve`/`metrics`
  ở gốc `BacktestResult` không đổi.
- **UI**: gộp vào 2 cơ chế có sẵn từ `BOT-079`, không thêm UI mới:
  - Cảnh báo overfit nối vào `build_result_warning_text()` — dòng riêng cạnh "Mở rộng chỉ
    số chi tiết", nội dung có số thật (`"In-sample +50.00% nhưng Out-of-sample -20.00%"`),
    không chỉ nói "có lệch".
  - 2 card mới ("In-Sample Net Profit"/"Out-of-Sample Net Profit") vào popup mở rộng, chỉ
    xuất hiện khi `out_of_sample` không `None`; card out-of-sample đổi màu `BEAR_COLOR`
    khi `has_high_divergence`.
- **Test**: 18 test mới xuyên domain→application→presentation (split/validation/handler/
  view logic) + 1 test presenter end-to-end xác nhận Presenter thật sự nối dây, không chỉ
  hàm tính đúng trong cô lập. 815 test toàn `tests/unit/`+`tests/sanity/` pass, `ruff`
  sạch.
- **Chưa làm** (đúng phạm vi "Mức 1", không tự mở rộng): Walk-forward, Monte Carlo, giới
  hạn warm-up indicator cho khoảng out-of-sample ngắn (mỗi nửa dùng strategy/indicator
  mới hoàn toàn từ đầu — một EMA-200 sẽ chưa "nóng" hết trong 1 khoảng out-of-sample
  ngắn; chấp nhận được ở Mức 1, ghi lại để `BOT-080` mức 2 xử lý nếu cần).
