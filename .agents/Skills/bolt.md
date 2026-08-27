# Bolt ⚡ — journal

Chỉ ghi những gì sẽ đổi cách quyết định lần sau. Không ghi nhật ký công việc.

## 2026-08-26 — Micro-benchmark không trả lời được câu hỏi "có đáng làm không"

**Learning:** Tôi tối ưu `_bar_bounds()` khỏi đường per-tick của Historical Tick
Backtest dựa **chỉ** trên một micro-benchmark của riêng hàm đó: 1064ns → 69ns,
15.5×. Con số đó đúng, và nó **không** trả lời được câu hỏi thật sự quan trọng.

Micro-benchmark trả lời *"code mới có nhanh hơn code cũ không"*. Câu quyết định
một tối ưu có đáng làm hay không là *"hàm đó có chiếm phần đáng kể của vòng chạy
không"* — và hai câu đó khác nhau. Một hàm nhanh gấp 15 lần nhưng chiếm 0.1%
tổng thời gian thì tối ưu nó là lãng phí công review.

Chỉ khi profile **cả handler** bằng `cProfile` mới có câu trả lời:

| | `_bar_bounds` | % tổng vòng chạy |
| :--- | ---: | ---: |
| Trước | 120.000 lần gọi | **17.37%** |
| Sau | 400 lần gọi | **0.32%** |

Lần này may — nó đáng làm thật. Nhưng tôi **không biết điều đó lúc quyết định**.

**Action:** Profile toàn bộ đường chạy **trước**, chọn mục tiêu từ profile, rồi
mới micro-benchmark để xác nhận bản sửa. Không làm ngược. `scripts/bolt001_tick_backtest_profile.py`
là bộ khung sẵn cho tick backtest — sửa tham số là dùng lại được cho đường khác.

## 2026-08-26 — Chi phí per-tick nằm ở `datetime`, không ở số học

**Learning:** Trong hot loop của tick backtest, thủ phạm không phải phép chia
lấy dư mà là hai thứ của `datetime`: `.timestamp()` (đổi múi giờ) và mỗi lần
dựng `datetime`/`timedelta`. Profile cho thấy `fromtimestamp` và `timestamp`
mỗi cái ~4% tổng, chỉ riêng chúng.

Nhìn rộng ra: hot loop ở đây đắt vì **cấp phát object**, không vì tính toán.
Top profile sau khi sửa là `to_candle()` (~39%) — dựng một `MarketData` mới cho
**mỗi** tick.

**Action:** Trong bất kỳ vòng lặp per-tick/per-bar nào, tìm chỗ *dựng object*
trước khi tìm chỗ *tính toán*. Ứng viên còn nguyên: `to_candle()` cấp phát
120.000 `MarketData` cho 120.000 tick, trong khi chỉ có ~400 bar thật.

## 2026-08-26 — Test có thể trông như đang bảo vệ mà không bảo vệ gì

**Learning:** Test đầu tôi viết cho `BOLT-001` kiểm `_bar_bounds()` **trực
tiếp** — tức code **không đổi**. Nó pass, đọc rất thuyết phục, và fault
injection (`<` → `<=` trên đúng dòng tôi sửa) **không làm nó đỏ**.

Test gap có sẵn cũng không bắt được, vì tick nối lại của nó cách biên bar khá
xa nên cả hai cách viết rẽ cùng nhánh.

**Action:** Sau khi viết test cho một tối ưu, **luôn** phá đúng dòng vừa sửa và
xác nhận đúng test đó đỏ. Nếu không đỏ, test đang kiểm thứ khác. Với thay đổi ở
biên, dựng ca test rơi **đúng vào biên** — chỗ khác không phân biệt được.
