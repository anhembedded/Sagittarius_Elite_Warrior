# Nhiệm vụ: Bug — `onClicked` chuyển vào `MouseArea` lồng bên trong `Button`, không bấm được từ test

> Phát hiện khi verify [`BOT-082`](../completed/BOT-082_fix_permanently_failing_interactive_shell_test.md)
> (chạy full suite để xác nhận xanh hoàn toàn). Root cause đã điều tra sẵn — **chưa sửa**.
>
> **Regression từ chính commit `d49c656`** *"Refactor UI components in BackTestTradeLogs
> and DevBoardPanel"* của user (redesign UI đang làm dở, không phải bug cũ tồn đọng).

## 1. Triệu chứng

Sau `d49c656`, full suite `tests/unit/` + `tests/sanity/` có thêm 3 test đỏ (trước đó
chỉ có `test_interactive_shell_wait_for_exit_exception`, đã sửa ở `BOT-082`):

```
FAILED test_backtest_presenter.py::test_qml_run_button_click_requests_a_run
    AssertionError: Expected 'submit' to have been called once. Called 0 times.
FAILED test_backtest_presenter.py::test_qml_clicking_a_trade_log_row_toggles_its_detail_section
    AssertionError: assert False is True  (detailTradeLog_1.visible)
FAILED test_dashboard_view.py::test_dashboard_view_header_title
    AssertionError: assert 'Dev Board' == 'Developer Board (Live Testbed)'
```

## 2. Root cause (đã verify) — 2 lỗi khác nhau, không phải 1

### 2.1. `btnRunBacktest` / `rowTradeLog_*` — đúng cạm bẫy đã ghi từ `BOT-057`

[`BackTestTopPanel.qml`](../../src/presentation/ui/screens/backtest/BackTestTopPanel.qml),
nút Run sau refactor:

```qml
Button {
    objectName: "btnRunBacktest"
    ...
    MouseArea {
        ...
        onClicked: viewModel.requestRun()   // ← chuyển vào đây
    }
}
```

Tương tự [`BackTestTradeLogs.qml`](../../src/presentation/ui/screens/backtest/BackTestTradeLogs.qml),
`rowTradeLog_*`:

```qml
Button {
    objectName: "rowTradeLog_" + modelData.index
    MouseArea {
        onClicked: root.toggleTradeLogRow(modelData.index)   // ← chuyển vào đây
    }
}
```

Đây **chính xác** là quy ước đã đúc kết ở `BOT-057` §2.1 và ghi trong bộ nhớ phiên làm
việc: *"`MouseArea.clicked` signal takes a `QQuickMouseEvent*` argument that CANNOT be
cleanly emitted from Python test code — any QML element that needs Python-test-clickability
should use `Button` (with custom `background`/`contentItem`), not `Rectangle + MouseArea`."*

Refactor **giữ đúng `Button`** ở lớp ngoài (tốt), nhưng **đặt `onClicked` vào `MouseArea`
lồng bên trong** thay vì vào chính `Button`. Hệ quả:

- `qml_item(root, "btnRunBacktest").clicked.emit()` — test gọi đúng `Button.clicked`,
  **nhưng handler không nằm ở đó nữa** → tín hiệu phát ra, không ai lắng nghe, không có
  lỗi nào, không có gì xảy ra. Đây là lý do khó phát hiện: không crash, chỉ lặng lẽ vô tác
  dụng — cùng lớp "lỗi bị nuốt im lặng" mà `BOT-066` đã chống cho tầng Python, nhưng lớp
  đó không phủ được QML thuần.
- Click chuột **thật** vẫn hoạt động bình thường (mouse event chạm đúng `MouseArea` con)
  — đây là lý do bug **không lộ ra khi chạy tay**, chỉ lộ qua test.

### 2.2. `lblHeaderTitle` — đổi nội dung, không phải lỗi cấu trúc

[`DevBoardPanel.qml`](../../src/presentation/ui/screens/dashboard/DevBoardPanel.qml),
text đổi từ `"Developer Board (Live Testbed)"` thành `"Dev Board"`. Test
`test_dashboard_view_header_title` pin đúng chuỗi cũ (chủ đích từ `BOT-014`, phân biệt Dev
Board với dashboard người dùng cuối).

~~**Không rõ đây là refactor có chủ đích (rút gọn nhãn) hay đổi ngoài ý muốn**~~ → **User
đã chốt: giữ nguyên nhãn cũ.** Sửa `lblHeaderTitle` về lại `"Developer Board (Live
Testbed)"` — **không** đổi `test_dashboard_view_header_title`, nó đã đúng từ đầu.

## 3. Các bước thực hiện

- [x] **Chờ user xác nhận `BackTestTopPanel.qml`/`BackTestTradeLogs.qml`/`DevBoardPanel.qml`
      đã chốt bản redesign** — user xác nhận xong (13/08).
- [x] §2.1: chuyển `onClicked` từ `MouseArea` con lên chính `Button` cha (xoá `MouseArea`
      nếu nó không còn việc gì khác — `hoverEnabled`/`containsMouse` có thể thay bằng
      `Button.hovered` sẵn có, không cần `MouseArea` riêng).
- [x] Rà toàn bộ `BackTestTopPanel.qml`/`BackTestTradeLogs.qml` tìm pattern
      `Button { ... MouseArea { onClicked: ... } }` khác — 2 ca tìm được ở §2.1 nhiều khả
      năng không phải toàn bộ, refactor có vẻ áp dụng đồng loạt.
- [x] §2.2: **đã chốt** — sửa `lblHeaderTitle` về lại `"Developer Board (Live Testbed)"`.
- [x] Chạy lại `test_backtest_presenter.py` + `test_dashboard_view.py` + toàn bộ
      `tests/unit/`/`tests/sanity/` — phải xanh hoàn toàn, không riêng 3 test này.

## 6. Kết quả triển khai thực tế

- **`BackTestTopPanel.qml` (`btnRunBacktest`)**: thêm `id: runBtnRoot` cho `Button`,
  chuyển `onClicked: viewModel.requestRun()` lên chính `Button`, xoá hẳn `MouseArea` con.
  `runBtnBg.color` (đổi màu khi hover) đổi nguồn từ `runBtnMouse.containsMouse` sang
  `runBtnRoot.hovered` — property có sẵn của `Button`/`AbstractButton`, cùng tác dụng,
  cùng quy ước `id.hovered` đã dùng ở `OrderExecutionMenu.qml`.
- **`BackTestTradeLogs.qml` (`rowTradeLog_*`)**: cùng pattern sửa — `id: rowBtn`,
  `onClicked: root.toggleTradeLogRow(modelData.index)` lên `Button`, xoá `MouseArea`,
  `rowBg.color` đổi từ `rowMouse.containsMouse` sang `rowBtn.hovered`.
- **Rà lại toàn bộ 2 file** (`awk` tìm mọi cặp `Button { ... MouseArea {` trong khoảng
  40 dòng): xác nhận đúng **2 ca**, không còn ca nào khác — nghi ngờ ban đầu trong task
  ("refactor có vẻ áp dụng đồng loạt") không đúng, chỉ 2 nút này bị dính.
- **Không đụng** `MouseArea` ở `"lnkExpandMetrics"` (mở popup mở rộng chỉ số) — đây là
  `Item + MouseArea` thuần, không phải `Button`, không nằm trong diện bug này (đã verify
  qua `git show d49c656` — hunk đổi `btnRunBacktest` không đụng khối này), và **không**
  đụng `MouseArea` mới trong `DevBoardPanel.qml` (`chkScript_*` — `Rectangle + MouseArea`
  bọc ngoài `StyledCheck`) vì nằm ngoài phạm vi 2 file mà task này giới hạn, không thuộc
  triệu chứng đã báo cáo.
- **`DevBoardPanel.qml` (`lblHeaderTitle`)**: khôi phục text về
  `"Developer Board (Live Testbed)"`. Đồng thời khôi phục `Layout.preferredWidth` từ `90`
  (kích cỡ redesign cắt riêng cho `"Dev Board"` ngắn) về lại `170` (giá trị gốc trước
  `d49c656`) — nếu giữ `90`, chuỗi dài mới bị `elide` cụt còn `"Developer B…"`, làm mất
  đúng tác dụng của quyết định giữ nhãn cũ (phân biệt Dev Board ↔ dashboard người dùng
  cuối). Không đổi gì khác trong layout.
- **Test**: `tests/unit`+`tests/sanity` — **789 passed**, 0 fail (3 ca đỏ đã biết từ
  `BOT-082`/lúc phát hiện task này nay đều xanh, không phải bỏ qua). Không cần test QML
  mới — 3 test đã có từ trước (`test_qml_run_button_click_requests_a_run`,
  `test_qml_clicking_a_trade_log_row_toggles_its_detail_section`,
  `test_dashboard_view_header_title`) chính là guard cho đúng 3 hành vi vừa sửa.

## 4. Rủi ro / Lưu ý

- **Đây là lỗi lộ diện qua test, không qua chạy tay** — đúng loại rủi ro mà giữ suite xanh
  liên tục (`BOT-082`) tồn tại để bắt. Nếu suite đã đỏ sẵn thì đợt refactor này rất có thể
  đã lọt qua không ai để ý.
- Không tự sửa `DevBoardPanel.qml` (§2.2) khi chưa hỏi — có thể là quyết định UX có chủ
  đích, không phải lỗi.
- Không mở rộng phạm vi sang sửa/thẩm mỹ khác trong 3 file đang WIP — chỉ đúng phần gãy
  hành vi.

## 5. Phụ thuộc

- Không phụ thuộc task nào khác. Sửa **chỉ trong `Sagittarius_Elite_Warrior/src/`** →
  commit submodule + bump pointer.
- Liên quan quy ước đã ghi ở [`BOT-057`](../completed/BOT-057_backtest_trade_logs_table.md)
  §2.1 (Button thay Rectangle+MouseArea để test click được).
