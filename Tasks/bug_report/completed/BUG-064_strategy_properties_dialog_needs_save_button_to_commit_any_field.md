# BUG-064 — Dialog "Cài đặt Chiến lược" chỉ commit giá trị khi bấm nút Lưu, không phản hồi Enter/mất focus

| Trường | Giá trị |
| :--- | :--- |
| **Trạng thái** | ✅ **Đóng 2026-08-27 — root cause tìm ra và đo được, tái hiện bằng test thật** |
| **Mức độ** | 🟡 P2 — không mất dữ liệu vĩnh viễn (giá trị chỉ chưa từng được lưu), nhưng gây hiểu nhầm "chỉnh sửa bị revert" |
| **Phát hiện** | 2026-08-27, user báo trực tiếp: "thay đổi kích thước lệnh thành 10, nhấn Enter, nơi vẫn hiện số 100" |

## Symptom

User mô tả và gửi ảnh chụp dialog "Cài đặt Chiến lược" (`StrategyPropertiesDialog`,
BOT-104), tab "Đặc tính": gõ giá trị mới vào ô "Giá trị kích thước"
(`propOrderSizeValue`), nhấn Enter — ô vẫn hiện lại giá trị cũ (`100`) khi mở lại
dialog. Ban đầu bị nhầm với 2 giả thuyết khác (tham số chiến lược không ảnh hưởng
kết quả backtest; dialog hiện sai tên chiến lược) — cả hai đều **bị loại bằng test
thật** trước khi tìm đúng root cause:

- Test tái hiện chính xác round-trip `VolumeSpikeFlowStrategy` (đổi
  `trailing_stop_pct`/`fade_mode`, bấm Lưu, dựng lại strategy) → **pass ngay**, chứng
  minh cơ chế lưu tham số chiến lược hoạt động đúng.
- Test tái hiện chính xác thao tác Enter trên `propOrderSizeValue` → **pass ngay ở
  lần chạy đầu (trước khi sửa)**, tức là bug **có thật**, không phải cảm giác.

## Root cause

`src/presentation/ui/screens/backtest/backtest_modals/strategy_properties_dialog.py`
— mọi `QLineEdit` trong cả 2 tab ("Các đầu vào" lẫn "Đặc tính") được tạo ra **không
kèm bất kỳ kết nối signal nào** (`returnPressed`/`editingFinished`). Cơ chế lưu duy
nhất là `save_and_rerun()`, chỉ được gọi khi bấm nút "Lưu & Chạy lại". Gõ giá trị
mới rồi nhấn Enter không kích hoạt gì cả — giá trị chỉ tồn tại trên mặt widget, chưa
từng được ghi vào `BackTestViewModel`. Lần mở dialog kế tiếp, `_sync_properties()`
đọc lại đúng giá trị cũ từ ViewModel (chưa đổi) → trông như bị "revert".

**Phát hiện thứ hai trong lúc sửa (user chỉ ra, không phải tôi tự thấy):** phần
`save_and_rerun()`/`_sync_properties()` đọc/ghi 12 widget bằng tay
(`self._prop_order_size_value.text()`, `.currentData()`, `.value()`,
`.isChecked()`...) — đúng loại "hot fix nhân bản" mà `bug-fix-rule.md`/§12.5 cấm.
Cùng một tập "12 broker property" bị khai 2 lần độc lập: 1 lần ở
`StrategyConfigCoordinator._BROKER_PROPERTIES` (áp giá trị vào ViewModel), 1 lần rải
rác trong `StrategyPropertiesDialog` (đọc/ghi widget) — thêm 1 property mới mà quên
1 trong 3 chỗ là bug y hệt BUG-064 lặp lại.

## Fix

1. **`_wire_line_edits_to_save_on_focus_lost()`** (dialog) — một vòng lặp chung
   dùng `findChildren(QLineEdit)`, nối `editingFinished` (bắt cả Enter **và** mất
   focus, đúng yêu cầu "lost focus thì update") tới `save_and_rerun()`. Áp dụng
   1 lần cho tab Đặc tính (widget tĩnh, xây 1 lần ở `__init__`) và mỗi lần
   `_sync_inputs()` rebuild tab Các đầu vào (widget động theo từng chiến lược) — field
   mới thêm vào sau này tự động được nối, không cần sửa thêm dòng nào.
2. **Guard chống gọi lặp** (`self._saving`) — rebuild tab Đầu vào sau khi lưu có thể
   khiến 1 widget đang giữ focus bắn thêm `editingFinished` trong lúc bị huỷ
   (deferred `deleteLater()`), gọi lại `save_and_rerun()` lần 2 nếu không chặn.
3. **`src/presentation/ui/screens/backtest/logic/broker_properties_schema.py`
   (file mới)** — `BROKER_PROPERTY_FIELDS`: bảng khai báo DUY NHẤT "khoá payload ↔
   thuộc tính ViewModel ↔ hàm ép kiểu", dùng chung bởi cả Coordinator lẫn Dialog.
   `StrategyConfigCoordinator._BROKER_PROPERTIES` (khai trùng) đã xoá, đọc thẳng từ
   schema chung.
4. **`_build_property_bindings()`** (dialog) — bảng "khoá ↔ widget ↔ đọc/ghi", dùng
   5 hàm dựng theo loại widget (`_line_edit_binding`, `_spin_box_binding`,
   `_check_box_binding`, `_combo_box_data_binding`, `_combo_box_text_binding`).
   `save_and_rerun()` và `_sync_properties()` giờ chỉ lặp qua bảng này — không còn
   `.text()`/`.currentData()`/`.value()`/`.isChecked()` viết tay cho từng field.
   Thêm 1 broker property mới từ giờ chỉ cần **1 dòng** ở `BROKER_PROPERTY_FIELDS` +
   **1 dòng** ở `_build_property_bindings()` (thay vì sửa 3 nơi độc lập như trước).
   Tác dụng phụ tích cực: xoá luôn bảng index combo hard-code riêng
   (`{"fixed_cash": 1, "fixed_contracts": 2}`) từng phải khớp tay với thứ tự
   `addItem()` — `_combo_box_data_binding` dùng `findData()`, không giả định thứ tự.

**Phạm vi cố ý không đụng:** tham số chiến lược ("Các đầu vào" tab) không cần sửa gì
— cơ chế `ScriptInput`/`input_*()` đã tự động hoàn toàn từ trước (chứng minh bằng
test `VolumeSpikeFlowStrategy`). Dev Board và Data Management **không dính bug
này** — cả hai đã dùng `textEdited` (commit theo từng ký tự gõ), một cơ chế khác,
đúng đắn theo cách khác: hành động đi kèm ở 2 màn đó rẻ (chỉ cập nhật UI/filter),
trong khi ở dialog Backtest mỗi lần commit gắn với **chạy lại cả backtest** — dùng
`textEdited` ở đây sẽ kích backtest chạy lại theo từng ký tự gõ, sai hoàn toàn.

## Regression thứ hai — do chính fix của BUG-064 gây ra, user phát hiện ngay lập tức

Ngay sau khi fix ở trên lên nhánh, user báo tiếp: "lost focus test box, sao lại
đóng luôn cái dialog vậy?" — mất focus 1 ô bất kỳ làm **đóng luôn cả dialog**, kể
cả khi chỉ đang tab qua ô khác để tiếp tục chỉnh sửa.

**Root cause:** `save_and_rerun()` (đường duy nhất commit giá trị) khi thành công
sẽ đi qua `_finish_save()` (coordinator) → emit `botParamsSaved`. Tín hiệu này được
nối sẵn từ trước (`__init__`): `view_model.botParamsSaved.connect(self.accept)` —
đúng ý định ban đầu (bấm nút "Lưu & Chạy lại" thì đóng dialog), nhưng nối này
**không phân biệt được** "bấm nút Save" với "một ô vừa mất focus" — cả 2 đều đi
qua chung `save_and_rerun()` sau khi tôi nối `editingFinished` vào đó.

**Fix:** thêm `_commit_without_closing()` — wrapper tạm **ngắt** kết nối
`botParamsSaved → accept` trong đúng thời gian gọi `save_and_rerun()`, rồi nối lại
ngay sau đó (an toàn vì `emit()` chạy đồng bộ cùng call stack, cùng thread Qt).
Đổi `_wire_line_edits_to_save_on_focus_lost()` để nối `editingFinished` vào
`_commit_without_closing()` thay vì thẳng vào `save_and_rerun()`. Nút "Lưu & Chạy
lại" vẫn gọi `save_and_rerun()` trực tiếp — hành vi đóng dialog khi bấm nút giữ
nguyên, không đổi.

**Sai lầm thứ hai của tôi, ngay trong chính lần sửa này:** tôi tự quyết giữ lại
phần "mất focus vẫn chạy lại backtest", tự lý giải là "đúng tinh thần TradingView",
và ghi vào chính hồ sơ này rằng user "không báo việc chạy lại là vấn đề". Đó là
suy diễn, không phải sự thật — xem mục kế tiếp.

Regression test: `test_tabbing_away_from_a_field_without_pressing_enter_also_commits_it`
và `test_editing_a_strategy_input_field_and_losing_focus_also_commits_it` được bổ
sung `assert dialog.isVisible()` — **xác nhận đỏ đúng lý do** khi tạm gỡ fix này
bằng `git stash` (thông báo lỗi: `"losing focus on an input field must not close
the dialog"`), xanh lại sau khi khôi phục. Thêm test riêng
`test_clicking_save_still_closes_the_dialog` để đảm bảo không sửa quá tay — bấm
nút Save vẫn phải đóng dialog như cũ.

## Regression thứ BA — cùng gốc với thứ hai, tôi vá triệu chứng thay vì vá cơ chế

User báo tiếp, gay gắt và đúng: **"chưa save sao lại nhảy state?"**

Fix ở mục trên chỉ chặn đúng **một** hệ quả (đóng dialog) mà không đụng tới nguyên
nhân: đường mất-focus vẫn đi qua nguyên vẹn pipeline **"save"**. Cụ thể,
`strategyPropertiesSaveRequested` → `BackTestPresenter._on_strategy_properties_save_requested`
→ `_start_run_after_config_save()` → `self.fsm.dispatch(BacktestUiEvent.RUN_REQUESTED)`
+ `_start_backtest_run(...)`. Nên mỗi lần tab qua một ô, màn hình **rời trạng thái
hiện tại và khởi động luôn một lần chạy backtest**, dù user chưa hề bấm Lưu.

Việc tôi làm ở mục trên (`_commit_without_closing`, tạm ngắt kết nối
`botParamsSaved → accept`) là đúng loại "hot fix" mà `bug-fix-rule.md` §1 và
ONBOARDING §12.5.1 cấm: che một triệu chứng của việc dùng sai pipeline, thay vì
tách pipeline ra.

**Fix thật — tách hẳn hai đường, từ ViewModel xuống Coordinator:**

| | Mất focus / Enter | Nút "Lưu & Chạy lại" |
| :--- | :--- | :--- |
| Signal | `strategyPropertiesCommitRequested` (mới) | `strategyPropertiesSaveRequested` |
| Slot ViewModel | `requestStrategyPropertiesCommit` (mới) | `requestStrategyPropertiesSave` |
| Presenter | `_on_strategy_properties_commit_requested` (mới) | `_on_strategy_properties_save_requested` |
| Coordinator | `commit_strategy_properties()` (mới) | `apply_strategy_properties()` |
| Ghi giá trị | ✅ | ✅ |
| Emit `botParamsSaved` (→ đóng dialog) | ❌ | ✅ |
| `RUN_REQUESTED` / chạy lại backtest | ❌ | ✅ |
| `_notify_config_changed()` (dirty-tracking BOT-095B) | ✅ | ✅ |

Phần validate + lưu giá trị dùng chung `_persist_strategy_properties()` — không
nhân đôi. `_commit_without_closing()` và cờ `self._saving` đã **xoá hẳn**: cả hai
chỉ tồn tại để chống đỡ hậu quả của việc dùng nhầm pipeline.

**Sửa kèm — rebuild widget giữa lúc đang gõ:** `commit_strategy_properties()` vẫn
phải gọi `refresh_bot_params_schema()` (nếu không, mở lại dialog sẽ hiện giá trị cũ
— đúng triệu chứng gốc của BUG-064). Nhưng việc đó phát `botParamsRowsChanged` →
`_sync_inputs()` → `deleteLater()` **đúng cái widget user đang gõ**. Sửa tận gốc:
`_sync_inputs()` giờ **bỏ qua rebuild khi tập tên field không đổi** (helper
`_field_names()`) — chỉ đổi *giá trị* thì không có gì cần dựng lại, vì widget đang
sống đã giữ đúng giá trị user vừa gõ; đổi *chiến lược* (khác tập field) thì vẫn
rebuild như cũ. Đây là điều kiện có nguyên tắc, không phải thêm một lá cờ nữa.

## Quyết định cuối của user — bỏ hẳn "save and run"

Sau khi tách xong 2 đường ở trên, user chốt: **"bỏ event save and run đi"**.

Nút "Lưu & Chạy lại" giờ chỉ còn **lưu + đóng dialog**, không chạy backtest. Việc
chạy là quyết định của user qua nút Chạy Backtest. Thay đổi cấu hình vẫn đánh dấu
kết quả cũ là stale qua dirty-tracking (`_on_config_input_changed`, BOT-095B) —
đó là đổi nhãn, không phải chuyển trạng thái FSM.

- `BackTestPresenter._on_strategy_properties_save_requested` không còn gọi
  `_start_run_after_config_save()`.
- `StrategyPropertiesDialog.save_and_rerun()` → đổi tên `save_and_close()`.
- Nhãn nút: **"Lưu & Chạy lại" → "Lưu"** — để nhãn cũ là nói dối với người dùng về
  việc nút đó làm gì.

Sau thay đổi này, `apply_strategy_properties()` và `commit_strategy_properties()`
chỉ còn khác nhau đúng một điểm: đường `apply` emit `botParamsSaved` (→ đóng
dialog), đường `commit` thì không.

**Còn tồn đọng, chưa đụng tới (báo để user quyết):** `botParamsSaveRequested` /
`requestBotParamsSave` / `_on_bot_params_save_requested` /
`_start_run_after_config_save()` vẫn còn trong code và **vẫn chạy backtest**. Đó
là đường cũ của nút "Lưu & Re-Backtest" bên QML — QML đã bị xoá ở `EPIC-006`, nên
đường này **không còn emitter thật nào trong `src/`**, chỉ có 5 test gọi trực tiếp
`view_model.requestBotParamsSave(...)`. Tức là code chết về mặt sản phẩm nhưng
đang được test giữ sống. Dọn nó cần sửa/xoá cả 5 test đó, nằm ngoài phạm vi user
yêu cầu ở đây.

Regression test: 2 test focus-loss được bổ sung
`assert modal_presenter.fsm.current_state == state_before` và
`assert dialog.findChild(object, "fldBotParam_fast") is fast_field` (widget đang gõ
phải sống sót qua commit). **A/B xác nhận đỏ đúng lý do**: tạm cho
`_on_strategy_properties_commit_requested` gọi lại `_start_run_after_config_save()`
→ 2 test đỏ với đúng thông báo `"losing focus must not dispatch RUN_REQUESTED"`;
gỡ patch → xanh lại.

## Regression test

`tests/unit/presentation/ui/screens/test_strategy_properties_modal.py` — 6 test mới:

- `test_editing_a_strategy_input_field_and_saving_uses_the_typed_value` — chứng
  minh cơ chế lưu tham số chiến lược (đường có sẵn) hoạt động đúng, loại trừ giả
  thuyết sai đầu tiên.
- `test_editing_volume_spike_flow_strategy_trailing_stop_and_saving_uses_the_typed_value`
  — round-trip đầy đủ với `VolumeSpikeFlowStrategy` (field có `group`, mix
  int/float/bool), loại trừ khả năng lỗi riêng ở chiến lược mới.
- `test_pressing_enter_in_order_size_field_commits_the_typed_value` — tái hiện
  đúng kịch bản user báo; **pass ngay ở lần chạy đầu (trước fix)** với assertion mô
  tả đúng bug (`orderSizeText == "100"` sau Enter), sau đó đảo lại thành assertion
  đúng hành vi mong muốn (`== "10"`) sau khi sửa code — verify cả 2 chiều.
- `test_tabbing_away_from_a_field_without_pressing_enter_also_commits_it` — mất
  focus mà không có Enter cũng phải commit.
- `test_editing_a_strategy_input_field_and_losing_focus_also_commits_it` — cùng cơ
  chế áp dụng cho tab Đầu vào, không chỉ tab Đặc tính.

Cập nhật `modal_presenter` fixture: đăng ký thêm `VolumeSpikeFlowStrategy` vào
`StrategyRegistry` test double.

**Verify đầy đủ trên máy thật** (venv `uv` Python 3.12.3, Engine repo clone riêng):
- `ruff check`/`format --check` `src tests`: sạch.
- `mypy --config-file pyproject.toml --namespace-packages --explicit-package-bases
  src scripts`: sạch, 155 file.
- 16 test liên quan (modal + coordinator) pass, bao gồm
  `test_broker_properties_are_applied_with_their_declared_types` (test cũ, xác nhận
  schema chung mới không đổi hành vi coordinator).
- Full unit + sanity: **2355 passed**, 0 dòng `FAILED|ERROR|Traceback|ResourceWarning`
  trong log đầy đủ. 1 `RuntimeWarning` còn lại đã xác nhận có sẵn từ trước
  (`test_log_panel.py`, không liên quan).
