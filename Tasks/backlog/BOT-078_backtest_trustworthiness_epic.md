# Epic: Backtest Trustworthiness — kết quả backtest có đáng tin không?

> Sinh ra từ 📄 [Rà soát định hướng App](../reports/app_direction_audit.md), phát hiện
> **#1** và **#2** — hai lỗ hổng khiến con số backtest **có thể đánh lừa người đọc**
> ngay cả khi engine chạy hoàn toàn đúng.
>
> **Khác hẳn [Epic `BOT-073`](BOT-073_realtime_tick_backtest_epic.md)**: `BOT-073` lo
> *engine mô phỏng có giống thật không*. Epic này lo *con số engine trả ra có bị hiểu
> sai không*. Engine đúng 100% vẫn có thể sinh ra kết luận sai.

## 1. Vấn đề — bằng chứng, không phải cảm tính

### 1.1. Con số `-80.71%` gần như hoàn toàn là phí

Log [`BUG-002`](../bug_report/BUG-002.md): `807 trades, net profit -80.71%`. Với
`fee_percent = 0.1` thu **cả 2 chiều**:

| | Hệ số còn lại | % |
| :--- | :---: | :---: |
| Chỉ riêng phí (`0.999 ^ 1614`) | 0.1989 | **-80.11%** |
| Thực tế log ghi | 0.1929 | -80.71% |
| **Edge gross của chiến lược** (phép chia) | 0.9697 | **-3.03%** |

→ **Phí chiếm ~96% khoản lỗ.** Chiến lược về cơ bản **hoà** (-0,004%/lệnh), không phải
"chiến lược tồi". 807 lệnh / 7 ngày ≈ **1 lệnh mỗi 12 phút**.

App hiện **không có chỗ nào** nói cho user biết điều đó — dù `Trade.fees_paid` đã có sẵn
dữ liệu, chỉ là chưa bao giờ được tổng hợp lên `BacktestMetrics`.

### 1.2. Không có bất kỳ cơ chế chống overfitting nào

```
grep -ri "walk.forward|out.of.sample|overfit|monte.carlo|in-sample" Tasks/ src/  → 0
```

Trong khi `BOT-044`/`046`/`047`/`048` đã hoàn thành **nguyên bộ máy tinh chỉnh tham số**.
Tinh chỉnh trên đúng một khoảng lịch sử, không train/test split → cỗ máy overfit không
phanh.

## 2. Mục tiêu

Không phải "làm backtest chính xác hơn" — mà **"làm cho người đọc không thể hiểu sai kết
quả"**. Ba hướng:

1. **Minh bạch chi phí** — phí phải hiện ra như một dòng riêng, không lẫn vào PnL.
2. **Kiểm định ngoài mẫu** — một con số đẹp phải chứng minh được nó không chỉ đẹp trên
   dữ liệu đã dùng để tinh chỉnh.
3. **Công bố giới hạn** — nói thẳng những gì backtest này *không* mô phỏng.

## 3. Bảng task con

| Task | Tên | Phụ thuộc | Ghi chú |
| :--- | :--- | :---: | :--- |
| [**BOT-079**](BOT-079_fee_transparency_and_trade_frequency.md) | **Minh bạch phí + cảnh báo tần suất giao dịch** | — | **Rẻ nhất, giá trị cao nhất.** Dữ liệu đã có sẵn (`Trade.fees_paid`), chỉ cần tổng hợp + hiển thị. Làm trước. |
| [**BOT-080**](BOT-080_out_of_sample_walk_forward.md) | **Kiểm định out-of-sample / walk-forward** | `BOT-047` ✅ | Lớn nhất epic. Còn câu hỏi mở cần user chốt — xem task. |
| [**BOT-081**](BOT-081_backtest_limitation_disclosure.md) | **Công bố giới hạn trên UI kết quả** | `BOT-079` | Gom mọi giới hạn đã biết (phí, slippage, tick fidelity, overfit) vào một chỗ user thật sự nhìn thấy. |

## 4. Thứ tự khuyến nghị & quan hệ với `BOT-073`

**`BOT-079` → `BOT-081` → `BOT-080`** (theo tỉ lệ giá trị/chi phí), nhưng `BOT-080` là
cái quan trọng nhất về lâu dài.

⚠️ **Quan hệ với [`BOT-073`](BOT-073_realtime_tick_backtest_epic.md) (Realtime backtest)
— cần cân nhắc thứ tự nghiêm túc:**

`BOT-073` làm kết quả *chân thực hơn về cơ chế*. Nhưng nếu tham số đã overfit thì kết quả
chân thực đó **vẫn vô nghĩa** — chỉ là một con số sai chính xác hơn.

→ Đề xuất: **`BOT-079` (rẻ) làm trước `BOT-073`**; `BOT-080` nên xong **trước khi** ai đó
dùng bộ máy `BOT-047` để tinh chỉnh tham số một cách nghiêm túc.

## 5. Rủi ro / Lưu ý

- **Cám dỗ lớn nhất**: coi đây là "việc phụ, làm sau" vì nó không thêm tính năng nào nhìn
  thấy được. Nhưng nó quyết định **mọi kết luận** rút ra từ app — kể cả kết luận "chiến
  lược này tốt, đem tiền thật vào".
- Epic này **không** đụng engine tính toán (`PaperExchange`/`BacktestMetrics` chỉ *thêm*
  trường, không đổi công thức đã có). Bất biến của `BOT-021` giữ nguyên.
- Không tự ý đổi `fee_percent` mặc định — con số `0.1` là hợp lý cho taker Binance; vấn
  đề là **không ai được biết nó ăn mất bao nhiêu**, không phải nó quá cao.

## 6. Phụ thuộc

- [`BOT-021`](../completed/BOT-021_static_backtest_execution_engine.md) ✅ — `Trade.fees_paid`,
  `BacktestMetrics` đã có sẵn.
- [`BOT-055`](../completed/BOT-055_backtest_performance_metrics_panel.md) ✅ — panel hiển
  thị metric, nơi thông tin mới sẽ xuất hiện.
- [`BOT-047`](../completed/BOT-047_dynamic_params_form_ui.md) ✅ — bộ máy tinh chỉnh tham
  số mà `BOT-080` phải bảo vệ.
- 📄 [Rà soát định hướng App](../reports/app_direction_audit.md) — nguồn phân tích.
