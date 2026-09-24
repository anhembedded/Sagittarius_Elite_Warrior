# Nhiệm vụ: Trailing Stop, Break-Even Stop & Chốt lời từng phần (Partial TP)

**Mã Task:** `BOT-105A`  
**Thuộc Epic:** [`BOT-105`](BOT-105_advanced_order_execution_and_risk_epic.md)  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** ✅ **Hoàn thành một phần (2026-09-23) — chỉ Break-Even Stop; Trailing Stop và Partial TP hoãn, xem §3.**  
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
- **Còn lại (chưa xây, backlog riêng khi cần)**: Trailing Stop (`trailing_
  activation_price`/`trailing_offset`, dời lại theo mỗi đỉnh mới) và Partial
  Take Profit (đóng từng phần `quantity`, sinh nhiều `Trade` cho 1 vị thế).
  Không có hạ tầng nào cho 2 cái này tồn tại trong `PaperExchange` hiện tại —
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
