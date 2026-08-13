# Nhiệm vụ: Minh bạch phí giao dịch + cảnh báo tần suất

> Thuộc Epic [`BOT-078`](../backlog/BOT-078_backtest_trustworthiness_epic.md). Nguồn: 📄
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

- [x] `BacktestMetrics` thêm: `total_fees_paid` (tổng `Trade.fees_paid`) và
      `gross_profit_before_fees` (hoặc tương đương — chốt tên lúc code, miễn là phân
      biệt được rõ *trước phí* / *sau phí*).
- [x] ⚠️ **Không đổi bất kỳ công thức nào đang có.** `net_profit` vẫn là sau phí như
      hiện tại — mọi test `BOT-021`/`BOT-055` phải xanh **không sửa**. Đây chỉ là thêm
      thông tin, không phải định nghĩa lại.
- [x] Thêm chỉ số tần suất: số lệnh / đơn vị thời gian (chốt đơn vị lúc code — lệnh/ngày
      là dễ hiểu nhất). Tính từ `equity_curve` đầu-cuối, không cần dữ liệu mới.

### 3.2. Cảnh báo — chỗ dễ làm sai nhất

- [x] Cảnh báo khi **phí chiếm tỉ lệ lớn bất thường** trong tổng lỗ/lãi. Ngưỡng cụ thể
      **chưa chốt** — đề xuất khởi điểm: phí > 30% giá trị tuyệt đối của `net_profit`.
      Đặt ngưỡng thành hằng số có tên, không rải magic number.
- [x] Cảnh báo khi **tần suất giao dịch bất thường** so với timeframe (vd trung bình < 15
      bar/lệnh trên khung 1m).
- [x] ⚠️ Cảnh báo là **thông tin, không phải lỗi** — không được chặn chạy backtest, không
      được nhuộm đỏ toàn màn hình như thể sai. Đây là chỗ dễ làm quá tay.

### 3.3. UI

- [x] Hiện `total_fees_paid` trong popup "Mở rộng chỉ số chi tiết" (`BOT-055` đã có sẵn
      chỗ, đang có 8 chỉ số).
- [x] Hiện cảnh báo (nếu có) ở chỗ user **thật sự nhìn**, cạnh kết quả — không giấu trong
      popup phải bấm mới thấy.

### 3.4. Test

- [x] Test tái hiện đúng ca thật: 807 lệnh, phí 0.1% hai chiều → `total_fees_paid` phải
      giải thích được ~96% khoản lỗ; cảnh báo phải bật.
- [x] Test không báo động giả: một chiến lược ít lệnh, phí nhỏ → **không** cảnh báo.
- [x] Test bất biến: mọi metric cũ giữ nguyên giá trị (chạy lại test `BOT-021`/`BOT-055`
      không sửa).

## 6. Kết quả triển khai thực tế

- **Domain** (`backtest_metrics.py`): 4 field mới trên `BacktestMetrics`
  (`total_fees_paid`, `avg_bars_per_trade`, `has_high_fee_ratio`,
  `has_high_trade_frequency`), tất cả có default để không phá construction test cũ nào.
  Ngưỡng đặt tên hằng số `FEE_DOMINANCE_WARNING_RATIO = 0.3` và
  `MIN_BARS_PER_TRADE_WARNING_THRESHOLD = 15.0`, docstring ghi rõ "con số khởi điểm,
  chưa validate". `avg_bars_per_trade` dùng đơn vị **bar**, không phải lệnh/ngày (lý do:
  `BacktestMetrics` không biết khung thời gian của nến, bar-count thì độc lập
  timeframe).
- **Cảnh báo**: gộp thẳng vào badge của card "Net PnL" — card duy nhất trong 4 card
  chính luôn hiển thị, không cần popup. Khi có cờ cảnh báo, badge đổi màu
  `BEAR_COLOR` (đúng tiền lệ đã có ở card Profit Factor với badge "Rủi ro") và nối
  thêm ghi chú ngắn (`⚠ Phí cao` / `⚠ Tần suất cao`) — không phải banner riêng, không
  nhuộm đỏ toàn màn hình, đúng yêu cầu §3.2. Card "Total Fees Paid" trong popup mở
  rộng cũng đổi màu `BEAR_COLOR` khi `has_high_fee_ratio` — 2 chỗ cùng nhất quán một
  tín hiệu.
- **Không đổi 1 dòng QML nào** — toàn bộ nằm ở Python (`performance_metrics_view.py`),
  tái dùng đúng cơ chế `MetricCard.qml` badge có sẵn. Chủ đích: `BackTestTopPanel.qml`
  đang là file WIP redesign (`BOT-083`), tránh thêm markup mới vào đó trước khi user
  xác nhận bản redesign đã chốt.
- **Test**: 8 test mới trong `test_backtest_metrics.py` (bao gồm tái hiện ca `BUG-002`
  qua `PaperExchange` thật, không assert số tay), 3 test mới trong
  `test_performance_metrics_view.py`, cập nhật 1 assertion cũ
  (`test_extended_cards_cover_every_remaining_metrics_field`) và 1 assertion cũ trong
  `test_backtest_presenter.py` (`extendedStatCards` 8 → 9). Full suite
  `tests/unit`+`tests/sanity`: 786 passed, chỉ còn đúng 3 fail đã biết từ `BOT-083`
  (không liên quan, không tăng thêm). `ruff check`/`ruff format --check` sạch.

## 4. Rủi ro / Lưu ý

- **Không đổi `fee_percent` mặc định.** `0.1` là hợp lý cho taker Binance. Vấn đề là
  *không ai được biết nó ăn mất bao nhiêu*, không phải nó quá cao.
- **Không tự thêm "phân tích độ nhạy phí"** (chạy lại backtest ở nhiều mức phí) trong
  task này — nghe hay nhưng là tính năng riêng, tốn thời gian chạy, và cần UI riêng. Nếu
  muốn, tách task sau khi cái này ổn.
- Ngưỡng cảnh báo là **phỏng đoán có căn cứ**, không phải chân lý. Ghi rõ trong docstring
  là con số khởi điểm, chờ dùng thật rồi chỉnh.

## 5. Phụ thuộc

- [`BOT-021`](BOT-021_static_backtest_execution_engine.md) ✅ —
  `Trade.fees_paid`, `BacktestMetrics`.
- [`BOT-055`](BOT-055_backtest_performance_metrics_panel.md) ✅ — panel +
  popup mở rộng đã có sẵn chỗ.
- Chỉ sửa `Sagittarius_Elite_Warrior/src/` → commit submodule + bump pointer.
