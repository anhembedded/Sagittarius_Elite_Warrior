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
- [ ] `from_qml()` ở engine.
- [ ] Chuyển `backtest_view_model.py` sang dùng nó, bỏ `isinstance(values, QJSValue)` cục bộ.
- [ ] Kiểm tra test `BOT-061` (`test_bot_params_dialog_qml.py`, 2 test) vẫn xanh **không sửa**.

## 4. Rủi ro / Lưu ý

- Rủi ro thấp. Cạm bẫy duy nhất đáng kể: **giả định `.toVariant()` đã xử lý xong đệ quy**.
  Phải chứng minh bằng test với dict lồng nhau, không suy luận.
- 7 dòng `Unable to assign [undefined] to QString/QColor` trong log
  [`BUG-002`](../bug_report/BUG-002.md) **không** phải bug và **không** thuộc phạm vi task
  này — đã xác định ở `BOT-061` là nhiễu vô hại lúc QML parse lần đầu. Ghi ở đây để lần
  sau không ai tưởng task này sẽ dọn sạch chúng.
- Engine là framework dùng chung — `from_qml()` không được giả định shape dữ liệu riêng
  của app này.

## 5. Phụ thuộc

- 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — nguồn phân tích, lớp E.
- [`BOT-061`](../completed/BOT-061_bot_params_save_qjsvalue_crash.md) ✅ — bản vá cục bộ đang được tổng quát hoá.
- Sửa `sagittarius_engine/` (repo cha) → commit ở **cả hai** repo.
