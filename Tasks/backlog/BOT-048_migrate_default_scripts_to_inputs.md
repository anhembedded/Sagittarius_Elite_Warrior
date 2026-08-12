# Nhiệm vụ: Chuyển 6 indicator script mặc định sang khai báo period bằng input

> Thuộc [Epic BOT-040](BOT-040_backtest_screen_full_feature_epic.md), Phase 0.
> **Task 4/4** nhóm "hệ thống tham số": [`BOT-044`](../completed/BOT-044_param_schema_core.md)
> → [`BOT-046`](BOT-046_strategy_param_plumbing.md) →
> [`BOT-047`](BOT-047_dynamic_params_form_ui.md) → `BOT-048` (file này).
> Phụ thuộc `BOT-044`, `BOT-047`.

## 1. Mục tiêu

6 script cố định period hiện tại (`ema_20`, `ema_50`, `ema_100`, `ema_200`,
`rsi_14`, `macd_full`) đang hardcode period trong `setup()`. Chuyển sang khai
báo period **làm input với default đúng bằng giá trị hiện tại** — để user
chỉnh được period nếu muốn, nhưng mặc định không có gì thay đổi.

## 2. Quyết định đã chốt (user)

> *"(ema_20, ema_50, ema_100, ema_200, rsi_14, macd_full) cứ tạo default
> indicator, nhét tụi nó vào là được mà. vẫn truyền 20 50…"*

→ **Giữ nguyên cả 6**, không xoá, không gộp thành 1 script `ema` chung. Chúng
vẫn là các indicator mặc định trong danh sách như hôm nay; chỉ khác là period
giờ đến từ input (default 20/50/100/200/14) thay vì hằng số trong code.

Điều này **giữ nguyên** `default_enabled` / US-07 (EMA 20/50/100/200 bật sẵn
trên Dev Board) — không đụng `IndicatorScriptListModel`.

## 3. Các bước thực hiện (Action Items)

- [ ] `ema_20_script.py`/`ema_50`/`ema_100`/`ema_200`: period → `input_int()`
  với default tương ứng, `minval=1`.
- [ ] `rsi_14_script.py`: period → `input_int(default=14, minval=2)`.
- [ ] `macd_full_script.py`: 3 tham số (fast/slow/signal) → input với default
  12/26/9.
- [ ] Xem lại `min_warmup_bars` — hiện là hằng số khớp với period hardcode
  (vd `EmaCrossScript.min_warmup_bars = 26`). Khi period thành input, warm-up
  phải **tính theo giá trị input thực tế**, không còn là hằng số. Đây là chỗ
  dễ bỏ sót nhất: `min_warmup_bars` được `_compute_fetch_limit()` dùng để
  quyết định tải bao nhiêu nến (`BOT-034` §4) — sai chỗ này thì chart thiếu
  dữ liệu mà không báo lỗi.
- [ ] Cân nhắc `ema_cross_script.py`/`ema_ribbon_script.py` (cũng hardcode
  period) — không bắt buộc trong task này, nhưng cùng loại việc, làm luôn cho
  nhất quán nếu gọn.
- [ ] Test hồi quy: mỗi script chạy với params rỗng cho ra **kết quả y hệt**
  trước khi đổi (so sánh chuỗi giá trị plot trên cùng bộ nến) — đây là bảo
  chứng "không có gì thay đổi với user hiện tại".

## 4. Rủi ro / Lưu ý

- `min_warmup_bars` động là rủi ro chính (xem mục 3) — liên quan trực tiếp tới
  `BOT-034` §4 (`_compute_fetch_limit()` lấy `max(min_warmup_bars)` của các
  script đang bật).
- Task này **không** bắt buộc để màn Backtest chạy — nó là dọn dẹp cho nhất
  quán. Nếu gấp, làm sau `BOT-047`.

## 5. Phụ thuộc

- [`BOT-044`](../completed/BOT-044_param_schema_core.md) — cơ chế `input_*()`.
- [`BOT-047`](BOT-047_dynamic_params_form_ui.md) — có UI thì việc chỉnh period
  mới có nghĩa với user.
- `BOT-032` ✅ — 6 script gốc. `BOT-034` ✅ — `_compute_fetch_limit()`.
