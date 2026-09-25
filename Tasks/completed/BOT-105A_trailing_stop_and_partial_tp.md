# Nhiệm vụ: Trailing Stop, Break-Even Stop & Chốt lời từng phần (Partial TP)

**Mã Task:** `BOT-105A`  
**Thuộc Epic:** [`BOT-105`](BOT-105_advanced_order_execution_and_risk_epic.md)  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** ✅ **Hoàn thành một phần (2026-09-25) — Break-Even Stop (23/09) và Trailing Stop (25/09); Partial TP hoãn, xem §3/§4.**  
**Dependencies:** [`BOT-041`](../completed/BOT-041_stop_loss_take_profit_and_risk_sizing.md), `BOT-021`

---

## 1. Mục tiêu

Bổ sung 3 cơ chế quản trị lệnh động cốt lõi vào `PaperExchange`:
1. **Break-Even Stop**: Khi giá tăng đạt ngưỡng kích hoạt (VD: $+1R$ hoặc $+2\%$ lợi nhuận), hệ thống tự động dời `stop_loss_price` về mức giá vào lệnh (`entry_price` hoặc `entry_price + fee`) để bảo toàn vốn 100%.
2. **Trailing Stop**: 
   - Tham số: `trailing_activation_price` (ngưỡng bắt đầu bám) và `trailing_offset` (khoảng cách bám theo giá đỉnh).
   - Khi giá tạo đỉnh mới $H_{new}$, mức cắt lỗ mới = $H_{new} - \text{trailing\_offset}$. Nếu giá hồi về chạm mức này $\rightarrow$ Khớp lệnh thoát vị thế.
3. **Chốt lời từng phần (Partial Take Profit / Scaling Out)**:
   - Cho phép cấu hình danh sách mốc chốt lời: `[(price_1, 50%), (price_2, 50%)]`.
   - Khi giá chạm `price_1`, `PaperExchange` ghi nhận 1 phần lợi nhuận, giảm số lượng vị thế `quantity`, sinh ra 1 partial `Trade` log, và giữ 50% khối lượng còn lại tiếp tục gồng lãi.

---

## 2. Kiểm thử & Tiêu chí Nghiệm thu

- **Financial Invariants**:
  - Khi đóng 1 phần vị thế, tổng `quantity` đã đóng + còn lại luôn bằng `initial_quantity`.
  - Tổng số tiền thực nhận sau các lần partial exit khớp chính xác với số dư tài khoản.
  - Trailing stop không bao giờ dời lùi xuống theo hướng bất lợi (chỉ được dời lên theo chiều tăng lãi).
- **Unit Tests**:
  - Kiểm thử Break-even stop kích hoạt đúng thời điểm.
  - Kiểm thử Trailing stop bảo vệ lợi nhuận khi thị trường đảo chiều từ đỉnh.
  - Kiểm thử Scaling out với 2 mốc TP1 và TP2.

---

## 3. Implementation Notes (2026-09-23)

**Chỉ Break-Even Stop được xây trong lần này** — re-scope có chủ ý, không phải
bỏ sót:

- 3 cơ chế trong §1 là 3 đơn vị công việc **độc lập, kích thước tương đương
  nhau** (mỗi cái đụng `PaperExchange`/`OpenPosition`/`BrokerSimulationConfig`
  theo cách riêng): Break-Even là một phép dời `stop_loss_price` một lần duy
  nhất dựa trên `mfe_percent` đã có sẵn; Trailing Stop cần một state máy đầy
  đủ hơn (dời lại **mỗi khi** giá tạo đỉnh mới, không phải một lần) và một
  tham số `trailing_offset` hoàn toàn mới; Partial TP cần thay đổi cấu trúc
  sâu hơn — `Trade`/`OpenPosition.quantity` hiện là số lượng cố định của một
  vị thế trọn vẹn, đóng một phần đòi hỏi tách `quantity` ra khỏi việc "đóng vị
  thế" (hiện `_close_one_position()` luôn đóng toàn bộ) và một schema mới cho
  danh sách mốc `[(price, %)]`. Dồn cả 3 vào một PR đúng như kiểu đã lặp lại 2
  lần trước đó trong task board này (`PROP-001`/`PROP-002`, xem
  `Tasks/completed/`) sẽ lại tạo ra một PR quá tải; tách riêng để mỗi cơ chế
  có bộ test tài chính (invariant) riêng, kiểm chứng độc lập.
- **Đã kiểm tra runtime thật** (không đoán, script tạm trong phiên làm việc):
  Break-Even một lần duy nhất (không tái kích hoạt), phối hợp đúng với
  `stop_loss_pct` tĩnh sẵn có (luôn dời lên hòa vốn, không bao giờ lùi), đúng
  hướng cho cả LONG/SHORT, và khớp lệnh ngay trong cùng 1 bar khi giá chạm
  ngưỡng kích hoạt rồi hồi về hòa vốn trong cùng bar đó.
- **Còn lại lúc đó (chưa xây)**: Trailing Stop và Partial Take Profit. Trailing
  Stop nay đã xây xong — xem §4 (2026-09-25). Partial TP (đóng từng phần
  `quantity`, sinh nhiều `Trade` cho 1 vị thế) vẫn hoãn, backlog riêng khi cần
  — không có hạ tầng nào cho nó tồn tại trong `PaperExchange` hiện tại,
  xác minh bằng cách đọc `paper_exchange.py`/`open_position.py` trực tiếp,
  không suy đoán.

**Files**: `contracts/broker_simulation_config.py`
(`break_even_trigger_pct`), `domain/open_position.py`
(`break_even_armed`), `domain/paper_exchange.py`
(`_apply_break_even_stops()`, gọi trong `check_intrabar_stops()` ngay sau
`_update_excursion_tracking()`).

**Tests**: `test_paper_exchange.py` (+9 — tắt mặc định, dưới ngưỡng không
kích hoạt, LONG/SHORT, cùng bar, phối hợp với SL tĩnh, chỉ dời một lần,
validation của config). Mutation-verified: gỡ tạm lời gọi
`_apply_break_even_stops()` trong `check_intrabar_stops()` làm 5/9 test đỏ
đúng lý do, khôi phục lại sau.

**Verification**: `ruff check`/`ruff format --check` sạch trên mọi file đã
sửa; mypy (`--config-file pyproject.toml --namespace-packages
--explicit-package-bases`) không phát sinh lỗi mới trên file nào đã sửa.
`tests/unit/modules/backtesting/domain/` + `application/` + `contracts/`:
217 passed.

## 4. Implementation Notes — Trailing Stop (2026-09-25)

**Đơn vị công việc riêng, như §3 đã dự tính** — bám sát mẫu `_apply_break_even_
stops()` đã có, chỉ khác ở chỗ nó lặp lại **mỗi bar** thay vì một lần duy nhất:

- **Đơn vị %**: `trailing_activation_pct` dùng cùng quy ước với
  `break_even_trigger_pct` (% lợi nhuận-trên-margin qua `mfe_percent` đã có) để
  quyết định *khi nào* kích hoạt bám đỉnh — tái dùng cơ chế sẵn có thay vì phát
  minh đơn vị mới. Nhưng `trailing_offset_pct` là % của GIÁ (cùng quy ước với
  `stop_loss_pct`/`take_profit_pct`), không phải % margin — vì nó được so trực
  tiếp với đỉnh/đáy giá thực (`OpenPosition.trailing_peak_price`, theo dõi
  riêng, độc lập với `mfe_percent`) để tránh phải đảo ngược công thức đòn bẩy.
  Đây là một chọn lựa có chủ ý khác với cách task gốc đặt tên
  (`trailing_activation_price`/`trailing_offset` như thể cả hai đều là giá
  tuyệt đối) — giữ nhất quán với mọi field khác của `BrokerSimulationConfig`
  (toàn bộ đều %, không field nào là giá tuyệt đối).
- Hai field `trailing_activation_pct`/`trailing_offset_pct` bắt buộc đi cùng
  nhau (validate ở `__post_init__`) — một mình một field không phải cấu hình
  hợp lý.
- **Không có hạ tầng UI mới** — đúng tiền lệ `break_even_trigger_pct` chính nó
  đã đặt ra (không dây UI nào cả) và tiền lệ `tick_resolution` của `BOT-105B`
  ("field cấu hình là seam, picker UI là biến thể hoãn lại"), `architecture-
  rule.md` §7.2.1.
- **Đã kiểm tra runtime thật** (test suite thật, không đoán): bám đỉnh mới
  cho LONG (`max()`) và đáy mới cho SHORT (`min()`), không bao giờ lùi khi
  không có đỉnh/đáy mới, khớp lệnh ngay trong cùng 1 bar khi giá bám rồi hồi
  về chạm stop mới, phối hợp đúng với `stop_loss_pct` tĩnh sẵn có (chỉ siết
  chặt, không bao giờ nới lỏng) — kể cả khi phối hợp với break-even cùng lúc
  (cả hai chỉ tiến, không bao giờ lùi, nhờ so sánh "chỉ thay nếu chặt hơn"
  trước khi ghi `stop_loss_price`).
- **Không cần thay đổi `OrderMatchingPolicy`/khớp lệnh** — `evaluate_
  intrabar_stops()` đã đọc `stop_loss_price` một cách tổng quát qua
  `IStoppablePosition`; trailing stop chỉ là một cơ chế khác *ghi* vào field
  đó trước khi khớp lệnh chạy, giống hệt break-even.

**Files**: `contracts/broker_simulation_config.py`
(`trailing_activation_pct`, `trailing_offset_pct`), `domain/open_position.py`
(`trailing_armed`, `trailing_peak_price`), `domain/paper_exchange.py`
(`_apply_trailing_stops()`, gọi trong `check_intrabar_stops()` ngay sau
`_apply_break_even_stops()`).

**Tests**: `test_paper_exchange.py` (+9 — validation cấu hình (bắt buộc đi
cùng nhau, biên số âm/ngoài khoảng), tắt mặc định, dưới ngưỡng kích hoạt
không bám, bám đỉnh + không lùi qua nhiều bar + khớp lệnh khi hồi về,
LONG/SHORT, cùng bar, phối hợp chỉ-siết-chặt với SL tĩnh có sẵn).
Mutation-verified: gỡ tạm lời gọi `_apply_trailing_stops()` trong
`check_intrabar_stops()` làm 4/9 test đỏ đúng lý do, khôi phục lại sau.

**Verification**: `ruff check`/`ruff format --check` sạch trên mọi file đã
sửa. mypy (gate thật — cwd tại thư mục cha, `MYPYPATH` trỏ `Sagittarius_
Engine` checkout kề bên): zero lỗi trên 3 file đã sửa; tổng lỗi toàn `src`+
`scripts` giữ nguyên 706 như trước nhánh này (đối chiếu bằng cách chạy trước/
sau thay đổi) — không lỗi mới, không thoái lui.
`tests/unit/modules/backtesting/domain/test_paper_exchange.py`: 85 passed.
`tests/unit/modules/backtesting/domain` + `application` + `contracts`: 246
passed. `tests/unit/architecture`: 440 passed.
`tests/unit/modules/backtesting` (toàn bộ): 954 passed, không thoái lui.
`python3 scripts/check_skill_prompt_references.py`: OK.

**Follow-up từ review độc lập của `PR #266`** (2 should-fix, không blocking):
1. **`paper_exchange.py` vượt ngưỡng 400 dòng** (`architecture-rule.md` §5.4,
   `C7`/`D7`) — tách `_update_excursion_tracking()`/`_apply_break_even_
   stops()`/`_apply_trailing_stops()` thành `StopManagementPolicy` mới
   (`domain/policies/stop_management_policy.py`), cùng một lifecycle (đúng
   thứ tự gọi mỗi bar, cái sau đọc cái trước vừa ghi). File còn lại **460
   dòng** (từ 562) — vẫn trên ngưỡng, vì phần còn lại (`_open()`/`_close()`/
   `_close_one_position()`) là vòng đời khớp lệnh cốt lõi, đã có test đầy
   đủ, không liên quan tới thay đổi của PR này; tách tiếp rủi ro hơn giá trị
   trong phạm vi 1 PR trailing-stop. Đã thêm vào `BOT-144` (task theo dõi nợ
   400-dòng có sẵn) làm file thứ 4, thay vì tự ý làm refactor lớn ngoài
   phạm vi. `StopManagementPolicy` có bộ test riêng
   (`tests/unit/modules/backtesting/domain/policies/test_stop_management_
   policy.py`, +6, dùng `OpenPosition`/`FillPricing` thật, không qua
   `PaperExchange`).
2. **Thiếu test phối hợp break-even + trailing cùng lúc** — docstring/PR
   body khẳng định 2 cơ chế phối hợp đúng nhưng chỉ có test với `stop_loss_
   pct` tĩnh. Thêm `test_trailing_stop_coordinates_with_a_break_even_move_
   already_in_place` (+1): break-even dời stop về entry trước, trailing sau
   đó dời tiếp xa hơn, không bao giờ lùi.

Xác minh lại sau fix: `ruff check`/`format --check` sạch; mypy 0 lỗi mới,
tổng vẫn 706 không đổi; `test_paper_exchange.py` 86 passed;
`test_stop_management_policy.py` 6 passed (mới); `domain`+`application`+
`contracts`: 253 passed; `tests/unit/architecture`: 440 passed;
`tests/unit/modules/backtesting` (toàn bộ): 961 passed, không thoái lui.
