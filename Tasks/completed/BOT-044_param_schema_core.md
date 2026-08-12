# Nhiệm vụ: Param Schema Core — cơ chế khai báo tham số cho Indicator Script

> Thuộc [Epic BOT-040](../backlog/BOT-040_backtest_screen_full_feature_epic.md), Phase 0.
> **Task 1/4** của nhóm "hệ thống tham số" (đã chia nhỏ theo yêu cầu user):
> `BOT-044` (core, file này) → [`BOT-046`](BOT-046_strategy_param_plumbing.md)
> → [`BOT-047`](BOT-047_dynamic_params_form_ui.md) →
> [`BOT-048`](BOT-048_migrate_default_scripts_to_inputs.md).
> Phụ thuộc `BOT-032` ✅.

## 1. Mục tiêu

Cho `BaseIndicatorScript` một cơ chế **tự khai báo tham số** tương đương
`input()` của Pine Script: 1 lời gọi vừa khai báo (để UI dựng widget), vừa trả
về giá trị (để code dùng ngay).

**Chỉ làm tầng domain + indicator script.** Strategy → `BOT-046`. UI dựng form
→ `BOT-047`. Chuyển 6 script mặc định sang dùng input → `BOT-048`.

## 2. ⚠️ Task này ĐẢO NGƯỢC quyết định ở BOT-032 §9.1 — đã được user chốt lại

`Tasks/completed/BOT-032_custom_indicator_scripts.md` **§9.1** ghi:

> **KHÔNG dùng `params` runtime — 6 script cố định period.** […] user đã chốt:
> *"khong cần chức năng rutime input đâu"*.

Yêu cầu mới (phiên này) làm lại đúng cơ chế đã bỏ. Đây là đảo ngược **có chủ
đích**, ghi lại để người đọc sau không tưởng là mâu thuẫn.

**Số phận 6 script cố định period — user đã chốt**: *"(ema_20, ema_50,
ema_100, ema_200, rsi_14, macd_full) cứ tạo default indicator, nhét tụi nó vào
là được mà. vẫn truyền 20 50…"*

→ **Giữ nguyên cả 6 làm indicator mặc định**, không xoá, không gộp. Chúng chỉ
đổi từ hardcode `self.ema(20)` sang khai báo period **làm input với default
20/50/100/200** — vẫn hiện sẵn trong danh sách như hôm nay, nhưng user chỉnh
được period nếu muốn. Không đụng `default_enabled`/US-07 (EMA 20/50/100/200
vẫn bật sẵn trên Dev Board). Việc chuyển đổi này nằm ở
[`BOT-048`](BOT-048_migrate_default_scripts_to_inputs.md), không phải task
này.

## 3. Thiết kế — vấn đề "2 pha"

UI cần biết schema **trước khi** user chọn giá trị. Pine giải quyết bằng cách
chạy script 1 lượt để thu thập các lời gọi `input()`.

**Hướng chọn (giống Pine nhất)**: khởi tạo script với `params=None` → mọi
`self.input_*()` trả về default **và tự ghi khai báo** vào list nội bộ → đọc
list đó ra schema → tạo **instance mới** với `params={...}` khi user đã chọn.

Tận dụng được `IndicatorScriptRegistry.create(key, params)` — **`params` đã
được chừa sẵn từ BOT-032 đúng cho việc này** (docstring ghi rõ: *"Reserved. […]
so that adding parameterised scripts later (period spin boxes, etc.) doesn't
change this signature"*). BOT-032 đã lường trước ngày này.

## 4. Các bước thực hiện (Action Items)

- [ ] Value object mô tả 1 tham số, đặt ở `domain/scripting/` (nơi đã chứa
  primitive dùng chung cho cả indicator lẫn strategy — đúng ý đồ ghi trong
  `ui_architecture.md`): `name`, `label` (nhãn hiển thị), kiểu, `default`,
  `minval`/`maxval` (optional), `options` (cho dropdown), `group` (nhóm field
  trong modal), `suffix` (đơn vị: `%`, `x`).
- [ ] 4 API khai báo trên `BaseIndicatorScript`, gọi trong `setup()`:
  `input_int()`, `input_float()`, `input_bool()`, `input_string(options=[...])`
  — trả giá trị (từ `params` nếu có, không thì `default`) **và** ghi khai báo.
- [ ] Thuộc tính/`property` đọc schema đã khai báo của 1 instance.
- [ ] `BaseIndicatorScript.__init__` nhận `params: Mapping[str, Any] | None`;
  `IndicatorScriptRegistry.create()` truyền xuống (chỗ nối đã chừa sẵn, chỉ
  cần bỏ dòng bỏ qua `params` hiện tại).
- [ ] Validate ở domain, **không tin UI**: sai kiểu / ngoài `minval`-`maxval` /
  không thuộc `options` → raise lỗi rõ ràng, không im lặng kẹp giá trị.
- [ ] Test: script khai báo input → đọc được schema đúng (kể cả `group`/
  `suffix`/`options`); `params` rỗng → dùng toàn default; `params` có giá trị →
  script chạy bằng giá trị đó; giá trị ngoài min/max → raise.
- [ ] Guard test: **cả 9 script hiện có vẫn chạy y hệt hôm nay** — script không
  khai báo input nào thì schema rỗng, hành vi không đổi 1 chút nào.

## 5. Rủi ro / Lưu ý

- Thay đổi chạm `BaseIndicatorScript` — lớp nền của **9 script đang chạy thật**.
  Ưu tiên **thêm mới (additive)**, không đổi chữ ký cũ; `params` phải là
  optional có default `None`.
- Khai báo input chạy trong `setup()` (1 lần/instance), **không** nằm trong hot
  loop `execute()` — không ảnh hưởng tốc độ backtest.
- Chưa đụng gì tới strategy ở task này — `BaseStrategy` thậm chí còn chưa có
  hook `setup()`, xem [`BOT-046`](BOT-046_strategy_param_plumbing.md).

## 6. Phụ thuộc

- `BOT-032` ✅ — `BaseIndicatorScript`, `IndicatorScriptRegistry.create(params)`
  (đã chừa sẵn), và §9.1 là quyết định bị task này đảo ngược.
