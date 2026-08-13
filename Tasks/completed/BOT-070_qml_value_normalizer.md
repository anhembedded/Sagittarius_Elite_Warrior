# Nhiệm vụ: `from_qml()` — chuẩn hoá giá trị đi qua ranh giới QML→Python

> Thuộc nhóm 6 task cơ chế engine sinh ra từ
> 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — **lớp lỗi E**.
>
> **Task rẻ nhất trong cả 6** (~15-30 dòng cơ chế). Không phụ thuộc task nào khác, làm
> xen kẽ lúc nào cũng được.

## 1. Mục tiêu

`QJSValue` hiện được xử lý ở **đúng 1 chỗ** trong cả repo:
[`backtest_view_model.py:542`](../../src/presentation/ui/screens/backtest/backtest_view_model.py#L542)
— chính là bản vá [`BOT-061`](../completed/BOT-061_bot_params_save_qjsvalue_crash.md).

Nghĩa là: **mỗi `@Slot("QVariant")` viết mới sau này là một `BOT-061` mới.** PySide6 giao
tham số dựng từ JS object literal của QML dưới dạng `QJSValue`, không tự ép sang `dict`;
`dict(values)` ném `TypeError`, bị `safe_ui_action` nuốt, và mọi giá trị user gõ bị vứt
bỏ trong im lặng.

Mục tiêu: **không dòng code app nào còn phải nhìn thấy `QJSValue`.**

## 2. Thiết kế đề xuất

Một hàm chuẩn hoá trong `sagittarius_engine/extensions/pyside_mvc/QmlShared/`:

```python
def from_qml(value):
    """Unwrap QJSValue -> Python, đệ quy qua dict/list lồng nhau."""
```

- Gọi `.toVariant()` khi gặp `QJSValue`.
- **Đệ quy**: `.toVariant()` ở tầng ngoài **không** đảm bảo mọi phần tử lồng bên trong đều
  đã là kiểu Python thuần. Cần verify hành vi thật của PySide6 với dict lồng dict/list
  **bằng test**, không tin tài liệu.
- Giá trị đã là Python thuần → trả nguyên, không tốn gì (để gọi vô điều kiện được).

### 2.1. Chưa chốt — quyết lúc code
Có nên gói thành decorator `@qml_slot` tự chuẩn hoá mọi tham số, thay vì bắt call-site
gọi `from_qml(...)` bằng tay? Decorator an toàn hơn (không quên được) nhưng thêm một lớp
che giữa `@Slot` và hàm thật, dễ gây khó hiểu khi debug chữ ký. Chỉ có **1 call-site**
hôm nay nên chưa đủ dữ liệu để quyết — làm hàm trước, cân nhắc decorator khi có call-site
thứ 3.

## 3. Các bước thực hiện

- [ ] Viết test trước, đi qua **ranh giới QML thật** (không dựng `dict` Python bằng tay
      rồi gọi thẳng slot — đó chính là lý do bộ test cũ của `BOT-047` không phát hiện được
      `BOT-061`). Dùng pattern của
      `tests/unit/presentation/ui/screens/test_bot_params_dialog_qml.py` đã có.
- [ ] Test phải phủ: object literal phẳng, **object lồng nhau**, mảng, và giá trị đã là
      Python thuần (idempotent).
- [x] `from_qml()` ở engine.
- [x] Chuyển `backtest_view_model.py` sang dùng nó, bỏ `isinstance(values, QJSValue)` cục bộ.
- [x] Kiểm tra test `BOT-061` (`test_bot_params_dialog_qml.py`, 2 test) vẫn xanh **không sửa**.

## 4. Rủi ro / Lưu ý

- Rủi ro thấp. Cạm bẫy duy nhất đáng kể: **giả định `.toVariant()` đã xử lý xong đệ quy**.
  Phải chứng minh bằng test với dict lồng nhau, không suy luận.
- 7 dòng `Unable to assign [undefined] to QString/QColor` trong log
  [`BUG-002`](../bug_report/BUG-002.md) **không** phải bug và **không** thuộc phạm vi task
  này — đã xác định ở `BOT-061` là nhiễu vô hại lúc QML parse lần đầu. Ghi ở đây để lần
  sau không ai tưởng task này sẽ dọn sạch chúng.
- Engine là framework dùng chung — `from_qml()` không được giả định shape dữ liệu riêng
  của app này.

## 6. Kết quả triển khai thực tế

**Verify bằng test thật trước khi tin tài liệu** (đúng yêu cầu §4): dựng 1 `QQmlEngine`
+ `QQmlComponent.setData()` với QML nguồn nạp thẳng bằng bytes (không cần file), gọi
`receiver.receive({...})` từ `Component.onCompleted`, để 1 `@Slot("QVariant")` Python thật
nhận giá trị. Kết quả thật (không suy đoán): `.toVariant()` ở PySide6 6.11.1 **đã** tự đệ
quy qua dict/list lồng nhau trong 1 lần gọi (`nested`/`arr[2]` bên trong đã là `dict`/`list`
thuần ngay sau `.toVariant()`, không còn `QJSValue` sót lại). `from_qml()` **vẫn** tự đệ quy
thêm sau `.toVariant()` — không tin hành vi này sẽ giữ nguyên mãi ở version PySide6 khác,
đúng tinh thần "không giả định" của task.

**`from_qml()`** (`sagittarius_engine/extensions/pyside_mvc/QmlShared/qml_value_normalizer.py`,
mới, xuất qua `QmlShared/__init__.py` + `pyside_mvc/__init__.py`): `isinstance(value, QJSValue)`
→ `.toVariant()`, rồi đệ quy qua `dict`/`list`, trả nguyên giá trị khác (idempotent — gọi lại
trên giá trị Python thuần không tốn gì, không lỗi).

**Bẫy thật gặp khi viết test** (không phải suy đoán trong task, mà lỗi thật tự gặp): `QJSValue`
chỉ sống được trong vòng đời `QQmlEngine` đã sinh ra nó — gọi `from_qml(qjs_value)` **sau khi**
hàm helper dựng `engine`/`component` đã return (biến cục bộ bị Python GC dọn) khiến
`.toVariant()` âm thầm trả `None` thay vì báo lỗi. Sửa: gọi `from_qml()` **bên trong** slot
`receive()` (khi engine còn sống), không trì hoãn ra ngoài. Ghi lại làm bài học cho ai viết
test QML-boundary tương tự sau này.

5 test mới (`tests/extensions/pyside_mvc/test_qml_value_normalizer.py`): object phẳng, object
lồng nhau, mảng có object lồng, giá trị đã native (idempotent, không cần QML), gọi `from_qml()`
2 lần liên tiếp cho cùng kết quả. `backtest_view_model.py`'s `requestBotParamsSave()` đổi sang
`from_qml(values)`, bỏ `isinstance(values, QJSValue)`/import `QJSValue` cục bộ. Test `BOT-061`
(`test_bot_params_dialog_qml.py`, 2 test) pass **không sửa 1 dòng**, đúng yêu cầu.

**Xác nhận không có regression thật**: full suite lúc verify có 3 test backtest/dashboard fail
thêm — điều tra ra là do `BackTestTopPanel.qml`/`BackTestTradeLogs.qml`/`DevBoardPanel.qml`/
`MetricCard.qml` đang được user chỉnh sửa dở (redesign UI, chưa commit), không liên quan gì
đến `from_qml()`. Xác nhận bằng `git stash` tạm 4 file QML đó (giữ nguyên `backtest_view_model.py`)
→ chỉ còn đúng 1 fail đã biết từ trước (`test_interactive_shell_wait_for_exit_exception`,
không liên quan) → stash pop khôi phục nguyên trạng việc user đang làm dở.

402 test engine (`tests/`, gồm 5 test mới) pass, `ruff` sạch cả 2 repo (2 file
`pyside_mvc/__init__.py`/`QmlShared/__init__.py` tiện thể dọn `__all__`/import order chưa
sort sẵn từ trước — không phải do task này gây ra, dọn luôn vì đang sửa đúng chỗ đó).

## 5. Phụ thuộc

- 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — nguồn phân tích, lớp E.
- [`BOT-061`](../completed/BOT-061_bot_params_save_qjsvalue_crash.md) ✅ — bản vá cục bộ đang được tổng quát hoá.
- Sửa `sagittarius_engine/` (repo cha) → commit ở **cả hai** repo.
