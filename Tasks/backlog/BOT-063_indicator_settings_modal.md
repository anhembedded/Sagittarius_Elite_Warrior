# Nhiệm vụ: Modal "Thông số Chỉ báo" cho Dev Board — Lưu / Khôi phục Mặc định

> Phụ thuộc `BOT-048` ✅ (6 script mặc định giờ đã khai báo period qua
> `input_int()`), tái dùng đúng pattern đã xây ở
> [`BOT-047`](../completed/BOT-047_dynamic_params_form_ui.md) (modal "Cấu
> hình Thông số Bot" cho Backtest screen) — chỉ khác đối tượng là
> **indicator script** trên Dev Board, không phải **strategy** trên màn
> Backtest.

## 1. Mục tiêu

Dev Board hiện chỉ có checkbox bật/tắt cho mỗi indicator script
(`IndicatorScriptListModel`/`DevBoardPanel.qml`'s "CUSTOM SCRIPTS" list) —
không có cách nào chỉnh tham số (period của EMA/RSI, fast/slow/signal của
MACD...) từ UI. Sau `BOT-044`/`BOT-048`, tầng domain đã sẵn sàng đầy đủ
(`BaseIndicatorScript.input_*()`, `.inputs`,
`IndicatorScriptRegistry.create(key, params)`) — chỉ thiếu tầng presentation.

Task này ghi lại việc còn thiếu: **chưa bắt đầu**, không có action item nào
đã làm.

## 2. Vì sao chưa làm ngay lúc BOT-048

Lúc làm `BOT-048`, user chốt: chỉ chuyển 6 script sang `input_*()` (backend),
**chưa xây UI** — để tách rõ 2 việc, tránh làm to task vốn chỉ nhằm dọn dẹp
kỹ thuật. Ghi task này lại làm nhắc việc, không quên.

## 3. Đã có sẵn để tái dùng (không viết lại)

- `bot_params_form.py` (`presentation/ui/screens/backtest/`) — logic build
  schema từ `.inputs` + parse giá trị QML gửi lên. Có thể tổng quát hoá
  thành hàm dùng chung cho cả `BaseStrategy` lẫn `BaseIndicatorScript` (2
  class đều có `.inputs` cùng shape `ScriptInput`), hoặc copy sang
  `presentation/ui/screens/dashboard/` nếu tách theo màn hình gọn hơn — cân
  nhắc lúc code, không quyết trước.
- `BotParamsDialog.qml`/`BotParamField.qml` (`presentation/ui/components/`)
  — component QML dựng form theo schema (int/float/bool/string, nhóm field,
  "Khôi phục Mặc định" ép thẳng vào `Loader.item`, "Lưu" chỉ đóng dialog khi
  Presenter xác nhận qua signal riêng — không tự đóng khi save fail).
- Icon `save.svg`/`rotate-ccw.svg` (khôi phục lại ở `BOT-062`/dọn merge) —
  sẵn cho nút Lưu/Khôi phục Mặc định của modal này, chưa nơi nào dùng.

## 4. Việc cần làm khi bắt đầu

- [ ] Nút mở modal trên `DevBoardPanel.qml` (mỗi dòng script trong
  "CUSTOM SCRIPTS", hoặc 1 icon riêng cạnh checkbox) — chỉ hiện/enable khi
  script đó có `.inputs` khác rỗng (script không khai báo gì thì không có
  gì để chỉnh).
- [ ] `indicator_script_runner.py`: `rebuild()` hiện gọi
  `self._registry.create(key)` — **không truyền params**. Cần đường lưu giá
  trị đã "Lưu" (per-script, per-key) và truyền vào `create(key, params)`.
- [ ] Quyết định nơi lưu giá trị đã chỉnh: chỉ tồn tại trong phiên làm việc
  (mất khi đóng app, đơn giản nhất) hay lưu persist qua `IConfig`/
  `user_config.json` (bền hơn nhưng cần thêm schema versioning nếu sau này
  đổi input). **Không tự quyết — hỏi user khi bắt đầu task.**
- [ ] `dashboard_presenter.py._compute_fetch_limit()` đọc `min_warmup_bars`
  như **class attribute**, không instantiate script — đúng cho tới giờ vì
  chưa ai truyền `params` thật. Khi modal này cho override period thật,
  `min_warmup_bars` phải tính lại theo giá trị **đã lưu** của script đang
  bật, không phải hằng số mặc định nữa (xem comment để lại ở mỗi script tại
  `BOT-048`, ví dụ `ema_20_script.py`).
- [ ] Test: build schema đúng cho ít nhất 1 script khai 1 input (vd
  `Ema20Script`) và 1 script khai nhiều input (`MacdFullScript`); Lưu xong
  → `_compute_fetch_limit()` phản ánh đúng period mới; "Khôi phục Mặc định"
  trả đúng giá trị hardcode gốc.

## 5. Phụ thuộc

- [`BOT-044`](../completed/BOT-044_param_schema_core.md) — cơ chế `input_*()`
  gốc, dùng chung cho cả script lẫn strategy.
- [`BOT-047`](../completed/BOT-047_dynamic_params_form_ui.md) — pattern UI để
  tái dùng nguyên (form động, Lưu/Khôi phục Mặc định).
- [`BOT-048`](../completed/BOT-048_migrate_default_scripts_to_inputs.md) — 6
  script mặc định giờ có input thật để modal này hiển thị.
