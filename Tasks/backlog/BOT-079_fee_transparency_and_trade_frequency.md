# Nhiệm vụ: Minh bạch phí giao dịch + cảnh báo tần suất

> Thuộc Epic [`BOT-078`](BOT-078_backtest_trustworthiness_epic.md). Nguồn: 📄
> [Rà soát định hướng App](../reports/app_direction_audit.md) §1.
>
> **Rẻ nhất, giá trị cao nhất trong epic — làm trước.** Dữ liệu đã có sẵn từ `BOT-021`,
> chỉ là chưa bao giờ được tổng hợp lên.

## 1. Vấn đề cụ thể

Log [`BUG-002`](../bug_report/BUG-002.md) ghi `807 trades, net profit -80.71%`. Người
đọc kết luận tự nhiên: *"chiến lược này tệ."*

Sự thật, tính từ chính con số đó (`fee_percent = 0.1`, thu cả 2 chiều):

| | Hệ số còn lại | % |
| :--- | :---: | :---: |
| Chỉ riêng phí — `0.999 ^ (2 × 807)` | 0.1989 | **-80.11%** |
| Thực tế | 0.1929 | -80.71% |
| **Edge gross của chiến lược** — `0.1929 / 0.1989` | 0.9697 | **-3.03%** |

→ **Phí chiếm ~96% khoản lỗ.** Chiến lược thực chất **hoà** (≈ -0,004%/lệnh). Kết luận
đúng phải là *"chiến lược không có edge, và giao dịch quá dày để sống nổi với phí"* —
khác hẳn *"chiến lược tệ"*.

App hiện **không cung cấp bất kỳ dữ kiện nào** để người đọc rút ra kết luận đúng đó.

## 2. Tin tốt: dữ liệu đã có, chỉ chưa nối

- `Trade.fees_paid` — **đã có sẵn** từ `BOT-021`, ghi đúng phí vào + phí ra mỗi lệnh.
- [`BacktestMetrics`](../../src/domain/backtesting/backtest_metrics.py) có 13 field
  nhưng **không có field nào về phí**.
- [`performance_metrics_view.py`](../../src/presentation/ui/screens/backtest/logic/performance_metrics_view.py)
  — 4 stat card chính + 8 chỉ số mở rộng, **không có phí**.

Nên đây gần như thuần *tổng hợp + hiển thị*, không phải tính toán mới.

## 3. Các bước thực hiện

### 3.1. Domain — thêm trường, **không đổi công thức cũ**

- [ ] `BacktestMetrics` thêm: `total_fees_paid` (tổng `Trade.fees_paid`) và
      `gross_profit_before_fees` (hoặc tương đương — chốt tên lúc code, miễn là phân
      biệt được rõ *trước phí* / *sau phí*).
- [ ] ⚠️ **Không đổi bất kỳ công thức nào đang có.** `net_profit` vẫn là sau phí như
      hiện tại — mọi test `BOT-021`/`BOT-055` phải xanh **không sửa**. Đây chỉ là thêm
      thông tin, không phải định nghĩa lại.
- [ ] Thêm chỉ số tần suất: số lệnh / đơn vị thời gian (chốt đơn vị lúc code — lệnh/ngày
      là dễ hiểu nhất). Tính từ `equity_curve` đầu-cuối, không cần dữ liệu mới.

### 3.2. Cảnh báo — chỗ dễ làm sai nhất

- [ ] Cảnh báo khi **phí chiếm tỉ lệ lớn bất thường** trong tổng lỗ/lãi. Ngưỡng cụ thể
      **chưa chốt** — đề xuất khởi điểm: phí > 30% giá trị tuyệt đối của `net_profit`.
      Đặt ngưỡng thành hằng số có tên, không rải magic number.
- [ ] Cảnh báo khi **tần suất giao dịch bất thường** so với timeframe (vd trung bình < 15
      bar/lệnh trên khung 1m).
- [ ] ⚠️ Cảnh báo là **thông tin, không phải lỗi** — không được chặn chạy backtest, không
      được nhuộm đỏ toàn màn hình như thể sai. Đây là chỗ dễ làm quá tay.

### 3.3. UI

- [ ] Hiện `total_fees_paid` trong popup "Mở rộng chỉ số chi tiết" (`BOT-055` đã có sẵn
      chỗ, đang có 8 chỉ số).
- [ ] Hiện cảnh báo (nếu có) ở chỗ user **thật sự nhìn**, cạnh kết quả — không giấu trong
      popup phải bấm mới thấy.

### 3.4. Test

- [ ] Test tái hiện đúng ca thật: 807 lệnh, phí 0.1% hai chiều → `total_fees_paid` phải
      giải thích được ~96% khoản lỗ; cảnh báo phải bật.
- [ ] Test không báo động giả: một chiến lược ít lệnh, phí nhỏ → **không** cảnh báo.
- [ ] Test bất biến: mọi metric cũ giữ nguyên giá trị (chạy lại test `BOT-021`/`BOT-055`
      không sửa).

## 4. Rủi ro / Lưu ý

- **Không đổi `fee_percent` mặc định.** `0.1` là hợp lý cho taker Binance. Vấn đề là
  *không ai được biết nó ăn mất bao nhiêu*, không phải nó quá cao.
- **Không tự thêm "phân tích độ nhạy phí"** (chạy lại backtest ở nhiều mức phí) trong
  task này — nghe hay nhưng là tính năng riêng, tốn thời gian chạy, và cần UI riêng. Nếu
  muốn, tách task sau khi cái này ổn.
- Ngưỡng cảnh báo là **phỏng đoán có căn cứ**, không phải chân lý. Ghi rõ trong docstring
  là con số khởi điểm, chờ dùng thật rồi chỉnh.

## 5. Phụ thuộc

- [`BOT-021`](../completed/BOT-021_static_backtest_execution_engine.md) ✅ —
  `Trade.fees_paid`, `BacktestMetrics`.
- [`BOT-055`](../completed/BOT-055_backtest_performance_metrics_panel.md) ✅ — panel +
  popup mở rộng đã có sẵn chỗ.
- Chỉ sửa `Sagittarius_Elite_Warrior/src/` → commit submodule + bump pointer.
