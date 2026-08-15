# Nhiệm vụ: Bug — Toàn bộ checklist "Indicators" trên Dev Board không hoạt động (`modelData` sai)

> Nguồn: phát hiện khi điều tra 1 test fail
> (`test_custom_scripts_checklist_renders_every_registered_script`) sau khi sửa
> contract `GetHistoricalKlinesQuery` cho các test race BOT-027 (commit `b9f1f28`).
> Test báo *"no checkbox rendered for script 'rsi_14'"* — điều tra sâu hơn cho thấy
> đây **không phải lỗi riêng `rsi_14`**, mà là **toàn bộ Repeater không render đúng
> bất kỳ script nào** (test chỉ fail-fast ở script đầu tiên nó duyệt).
>
> **✅ ĐÃ SỬA.** Đúng quy trình [`.agents/rules/code-rule.md`](../../.agents/rules/code-rule.md):
> `test_custom_scripts_checklist_renders_every_registered_script` (đã tồn tại, đang
> fail đúng lý do — verify lại trước khi sửa) không cần viết lại, chính nó là bằng
> chứng tái hiện. Sửa `DevBoardPanel.qml`'s Repeater delegate theo đúng pattern của
> `IndicatorPickerMenu.qml` (thêm lại `required property var model`/`int index`, đặt
> `id: scriptRow` để tránh chuỗi `parent.parent` mong manh, đổi mọi `modelData.*` →
> `scriptRow.model.*`). Kết quả: 3/3 test trong file này xanh, 0 warning `modelData`
> còn lại trong log QML (trước đó lặp ở mọi lần Dev Board render), 28/28 test tích hợp
> UI đụng Dev Board xanh, 789 test unit+sanity không đổi.

## 1. Mức độ nghiêm trọng — ĐANG SỐNG TRÊN `main`

Đây không phải bug tiềm ẩn hay edge case — **checklist "Indicators" trên Dev Board
đang hỏng hoàn toàn ngay lúc này**, với người dùng thật đang mở app:

- Không script nào có `objectName` đúng (`chkScript_<key>` không tồn tại trong cây
  visual — verify bằng probe trực tiếp: `rowCount()` của model = 9, nhưng số
  `chkScript_*` tìm được trong cây QML = **0**).
- Nhãn checkbox không hiện tên script.
- Trạng thái checked/unchecked không phản ánh đúng (bao gồm cả 4 script mặc định
  `ema_20/50/100/200` vốn `default_enabled=True`).
- Bấm vào checkbox **không bật/tắt được gì** — `onClicked` ném `TypeError` trước khi
  gọi `setEnabled()`.

Log QML xác nhận bằng warning lặp lại mỗi lần Dev Board render:
```
DevBoardPanel.qml:356:41: TypeError: Cannot read property 'key' of undefined
DevBoardPanel.qml:357:    TypeError: Cannot read property 'title' of undefined
DevBoardPanel.qml:358:    TypeError: Cannot read property 'enabled' of undefined
```

## 2. Root cause (đã verify tận gốc, có bằng chứng before/after)

`DevBoardPanel.qml`'s Repeater delegate (khối "Indicators Card") dùng
`modelData.key`/`modelData.title`/`modelData.enabled` — nhưng **`modelData` không
tồn tại** cho một `QAbstractListModel` khai nhiều role đặt tên (ở đây
`IndicatorScriptListModel` có 3 role: `key`/`title`/`enabled`, xem
[`indicator_script_list_model.py:38-42`](../../src/presentation/ui/screens/dashboard/indicator_script_list_model.py#L38)).
`modelData` chỉ tự động có giá trị khi model là mảng JS thuần hoặc `QAbstractItemModel`
với **đúng 1 role** — quy tắc này của chính Qt/QML, không phải bug của model.

**Bằng chứng đây là regression, không phải lỗi từ đầu**: `git show d49c656 --
DevBoardPanel.qml` cho thấy TRƯỚC commit đó, delegate dùng đúng pattern:

```qml
RowLayout {
    required property var model
    required property int index
    StyledCheck {
        objectName: "chkScript_" + parent.model.key
        text: parent.model.title
        checked: parent.model.enabled
        onToggled: viewModel.scriptModel.setEnabled(parent.index, checked)
    }
}
```

Commit `d49c656` ("Refactor UI components... for improved styling and layout") đổi
`RowLayout` thành `Rectangle` (để thêm hover/MouseArea), và trong lúc viết lại đã
**xoá `required property var model`/`required property int index`** rồi đổi
`parent.model.key` → `modelData.key` — sai cả 2 chế độ QML: không declare `required
property` (chế độ "strict") mà cũng không dùng bare role name (`key`/`title`/`enabled`
trực tiếp, chế độ "implicit") — dùng nhầm `modelData`, thứ chỉ hợp lệ cho model 1-role.

**Bằng chứng pattern đúng vẫn tồn tại y hệt ở nơi khác**:
[`IndicatorPickerMenu.qml:56-68`](../../src/presentation/ui/components/IndicatorPickerMenu.qml#L56)
(component của `BOT-064`, màn Backtest, cũng bind `viewModel.scriptModel` y hệt) vẫn
giữ đúng `required property var model` + `parent.model.key` — **không hỏng**. Đây
chính là bản mẫu để sửa `DevBoardPanel.qml` theo, không cần thiết kế lại từ đầu.

## 3. Các bước thực hiện

- [x] Verify `test_custom_scripts_checklist_renders_every_registered_script` fail
      đúng lý do (*"no checkbox rendered for script 'rsi_14'"*) trước khi đụng code.
- [x] Sửa `DevBoardPanel.qml`'s Repeater delegate theo đúng pattern của
      `IndicatorPickerMenu.qml`: thêm `required property var model`/
      `required property int index` + `id: scriptRow` trên `Rectangle` (delegate
      root — đặt `id` thay vì chuỗi `parent.parent` vì `StyledCheck` nằm sâu hơn 1
      cấp so với `IndicatorPickerMenu.qml`, qua thêm `RowLayout` trung gian), đổi
      toàn bộ `modelData.key/.title/.enabled` → `scriptRow.model.key/.title/.enabled`,
      `MouseArea.onClicked` → `viewModel.scriptModel.setEnabled(scriptRow.index,
      !scriptRow.model.enabled)`.
- [x] `test_custom_scripts_checklist_renders_every_registered_script` +
      `test_enabling_a_script_then_load_history_registers_it_as_active` (cùng file)
      — cả 3 test trong file xanh.
- [x] Verify bằng probe trực tiếp: 0 warning `modelData` còn lại trong log QML (trước
      đó lặp lại mỗi lần render).
- [x] Chạy toàn bộ 5 file test tích hợp UI đụng Dev Board
      (`test_dev_board_custom_scripts.py`, `test_dev_board_indicators.py`,
      `test_dev_board_known_gaps.py`, `test_dev_board_async_race_conditions.py`,
      `test_sanity_ui_e2e.py`) — **28/28 pass**.
- [x] `tests/unit` + `tests/sanity` — 789 pass, không đổi.

## 4. Rủi ro / Lưu ý

- **Đây là bug UI thuần QML** — không đụng Python model, không đụng
  `IndicatorScriptListModel`/`IndicatorScriptRegistry`/`DashboardPresenter`. Phạm vi
  sửa đúng 1 file `.qml`.
- **Không "cho nhất quán" mà đổi luôn `IndicatorPickerMenu.qml` sang pattern khác** —
  nó đang đúng, đừng động vào.
- MouseArea + StyledCheck lồng nhau (Rectangle bọc cả MouseArea lẫn RowLayout chứa
  StyledCheck) là thiết kế **cố ý** của refactor styling (hover effect trên cả hàng,
  không chỉ ô checkbox) — giữ nguyên cấu trúc đó, chỉ sửa đường truy cập role.
  Tương tự lớp lỗi đã gặp ở commit `449413a` (fix onClicked lồng MouseArea
  cho Button) — **không phải cùng 1 bug**, nhưng cùng họ "refactor UI thay cấu trúc
  container, quên rà lại tương tác/binding bên trong".
- Test hiện có (`test_custom_scripts_checklist_renders_every_registered_script`) đã
  **tự phát hiện đúng bug này** — không phải test yếu, chỉ là chưa ai chạy nó sau khi
  merge `d49c656`. Bài học quy trình (không thuộc phạm vi sửa code của task này): CI
  cần chạy `tests/integration/presentation/ui/` trước khi merge PR đổi QML, không chỉ
  `tests/unit`+`tests/sanity`.

## 5. Phụ thuộc

- Không phụ thuộc task nào khác. Sửa **chỉ trong `Sagittarius_Elite_Warrior/src/`**
  (không đụng `sagittarius_engine/`) → chỉ cần commit ở submodule + bump pointer.
- Liên quan gián tiếp `BOT-032`/`BOT-044`/`BOT-048` (script registry/checklist gốc) —
  không cần đọc lại, bug này thuần ở tầng QML binding, không ở tầng domain/registry.
