# Nhiệm vụ: Modal "Thông số Chỉ báo" cho Dev Board — Lưu / Khôi phục Mặc định

**Trạng thái:** 🟢 **Hoàn thành (2026-09-23)** — xem §6 để biết đường thật đi qua đâu; tiền đề ở §3 (QML) đã lỗi thời, tái dùng `StrategyParamsDialog` (QtWidgets) thay vì `BotParamsDialog.qml`.

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

---

## 6. Ghi Chú Triển Khai Thực Tế (2026-09-23)

**Toàn bộ §3 (QML) đã lỗi thời — không dùng lại.** `DevBoardPanel.qml`,
`bot_params_form.py` (`presentation/ui/screens/backtest/`),
`BotParamsDialog.qml`/`BotParamField.qml` đều đã bị xoá từ `EPIC-025`
(rebuild QtWidgets). Xác nhận qua khảo sát thật trước khi code, không suy
đoán từ tên file. Đường thật đi qua:

- **Không xây modal mới** — tái dùng nguyên `StrategyParamsDialog`
  (`support/ui_kit/param_form/strategy_params_dialog.py`), lớp QtWidgets
  đã thay `BotParamsDialog.qml` cho **strategy** (`EPIC-022D`/`023C`). Lớp
  này vốn đã tổng quát (nhận bất kỳ đối tượng nào khớp cấu trúc
  `BotParamsSink` Protocol — không hề gắn cứng với "strategy"), chỉ cần
  thêm tham số `title` tuỳ chọn (mặc định giữ nguyên "Strategy Parameters"
  cho 2 nơi gọi cũ) để Dev Board hiển thị "Indicator Parameters" thay vì
  dùng chung chữ "Strategy". Đã thêm nút **"Restore Defaults"** vào chính
  dialog này (`reset_to_default()` đã có sẵn trên `BotParamFieldWidget`,
  chỉ còn thiếu nút gọi nó) — lợi luôn cho 2 nơi gọi strategy cũ.
- **`_field`/`_coerce` tách khỏi `StrategyCatalogService` thành
  `support/indicators/scripting/param_form.py`** (`build_param_groups`/
  `validate_params`), dùng chung cho cả `StrategyCatalogService` (đã đổi
  sang gọi hàm chung, không đổi hành vi) và `IndicatorScriptCatalog` mới
  (script tương đương của `StrategyCatalogService`, sống trong
  `support/indicators/` vì chỉ có 1 registry, không cần port/interface).
  Đặt trong `scripting/` (không phải thẳng `support/indicators/`) vì
  `tests/unit/architecture/boundaries/rules.py`'s `_COMPUTATION_SUB_
  PACKAGES` chỉ cho phép `modules/strategy` (ngoài `ui/`) đọc thẳng các
  sub-package **có tên** (`indicators`/`indicator_scripts`/`scripting`/
  `indicator_script_registry`), không phải gốc package.
  `ParamValidation` không dùng chung với `modules/strategy/contracts/` mà
  tự có bản sao riêng trong `support/indicators` — đúng tiền lệ
  `modules/trading/contracts/strategy_param_validation.py` đã chọn
  (`DECISION_2026-09-17...md`): kiểu dữ liệu thuần giá trị, rẻ để nhân
  bản, đắt để ràng buộc 2 cây độc lập vào nhau.
- **`min_warmup_bars` chuyển sang per-instance thật** (đúng như comment để
  lại từ `BOT-048` ở `ema_20_script.py` "Needs to become per-instance once
  BOT-063 wires a real params UI"): 6 script (`ema_20/50/100/200`,
  `rsi_14`, `macd_full`) tự gán `self.min_warmup_bars = <giá trị input
  thật>` trong `setup()`, class attribute chỉ còn là fallback. Không cần
  sửa base class — instance attribute tự che class attribute, Python có
  sẵn cơ chế này.
- **Lưu trữ: persist qua `IConfig`** (`ConfigKeys.DASHBOARD_INDICATOR_
  SCRIPT_PARAMS`, JSON `{key: {param: value}}`), quyết theo Hiến pháp P5
  (Apply Before You Invent — mirror shape đã có sẵn ở
  `ConfigKeys.TRADING_LIVE_STRATEGY_PARAMS`/`LiveStrategyConfigStore` thay
  vì phát minh phiên bản chỉ-trong-phiên đơn giản hơn nhưng chưa qua kiểm
  chứng). `IndicatorScriptParamsStore` mirror đúng shape đó nhưng keyed
  theo script (nhiều script có thể bật + chỉnh cùng lúc, khác 1 strategy
  duy nhất). Đọc lại "no retroactive effect" — giá trị chỉnh chỉ có hiệu
  lực ở lần Load History/Start Live kế tiếp, đúng quy ước bật/tắt script
  đã có sẵn.
- **`IndicatorScriptRunner.rebuild()`/`add_script()`** nhận thêm
  `get_params` callback tuỳ chọn (mặc định trả `None`, không đổi hành vi
  của Backtest — nơi duy nhất khác cũng dùng class này nhưng chưa có UI
  params riêng). `IndicatorCoordinator.compute_fetch_limit()` tương tự
  thêm `get_script_params`, và giờ **instantiate** script qua
  `registry.create(key, params)` thay vì đọc `min_warmup_bars` off class.
- **`IndicatorScriptParamsSink`** (`support/indicators/ui/`) — sink mới,
  khác hẳn `StrategyCardViewModel` (1 sink cố định, đổi target theo
  combo): dựng mới mỗi lần mở dialog, 1 cái/script key, gọi thẳng
  catalog+store thay vì đi vòng qua Presenter signal — không có UI khác
  nào cần phản ứng sống với việc đổi params 1 script (khác thẻ strategy có
  label tóm tắt hiển thị nơi khác).
- **Phát hiện `BUG-134` giữa chừng** (đã tách riêng, xem hồ sơ bug): nút
  "Strategy Parameters…" có sẵn trên Dev Board crash `TypeError` mỗi lần
  bấm — `_open_strategy_params_dialog()` truyền `self` (một `QObject` từ
  `EPIC-025` PR 1.4c-3, không phải `QWidget` nữa) làm Qt parent, đúng hình
  dạng `_dialog_parent()`'s docstring (trên cùng class) đã cảnh báo. Sửa
  bằng đúng `_dialog_parent()` sẵn có.
- **Nút mở modal**: 1 icon `sliders` cạnh checkbox mỗi dòng script, chỉ
  hiện khi `IndicatorScriptListModel`'s `HasParamsRole` (mới, tính qua
  throwaway instance `cls().inputs`) là true. `ema_cross`/`ema_ribbon`/DEV
  showcase không khai `input_*()` nào nên không có nút.
- **Test**: `test_param_form.py` (hàm build chung), `test_indicator_script_
  catalog.py`, `test_indicator_script_params_store.py`,
  `test_script_params_sink.py`, `test_strategy_params_dialog.py` (title +
  Restore Defaults — dialog này trước đó chưa có test trực tiếp nào),
  `test_dev_board_indicator_params.py` (nút chỉ hiện đúng script có input,
  click không crash), `test_bug_134_strategy_params_dialog_parent.py`
  (regression riêng cho bug tìm thấy). Toàn bộ `.exec()` bị patch trong
  test — dialog thật là modal, treo vô hạn dưới `QT_QPA_PLATFORM=offscreen`.
