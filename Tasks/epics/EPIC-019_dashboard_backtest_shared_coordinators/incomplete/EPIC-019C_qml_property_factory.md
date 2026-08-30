# EPIC-019C — Factory cho Qt `Property` boilerplate ở ViewModel

**Thuộc Epic:** [`EPIC-019`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu
**Phụ thuộc:** Không.
**Nguồn:** ADR D3 (finding tự phát hiện, độc lập với báo cáo Gemini).

---

## Hiện trạng

133 method `_get_*`/`_set_*` trên toàn `presentation/ui/screens/*/*.py` —
mỗi property QML-bindable trong 4 ViewModel (`BackTestViewModel`,
`DashboardQmlViewModel`, `DataManagementViewModel`, `SettingsViewModel`) tự
tay viết cùng một khuôn:

```python
def _get_x(self) -> T: return self._x
def _set_x(self, value: T) -> None:
    if value != self._x:
        self._x = value
        self.xChanged.emit()
x = Property(T, _get_x, _set_x, notify=xChanged)
```

`BaseQmlViewModel` (engine, `pyside_mvc/runtime/base_view_model.py`) — lớp
cha chung thật sự của cả 4 ViewModel — chỉ cung cấp `uiMode`/
`controlsEnabled`, không có factory nào cho property khác. `selectedSymbol`
tồn tại gần giống hệt ở `backtest_view_model.py:374` và
`data_management_view_model.py:170`, khác nhau đúng phần normalize
(`data_management` tự `.strip().upper()`, `backtest` thì không).

## Việc cần làm

1. Viết `notifying_property(attr_name, signal, normalize=None)` — hàm
   factory sống trong app này (**không** sửa `BaseQmlViewModel` của
   engine — 2 repo độc lập theo `CLAUDE.md`, sửa engine là quyết định
   khác, ngoài phạm vi task này). Trả về `(getter, setter, Property)` hoặc
   trực tiếp một `Property` đã bọc getter/setter closure, giữ nguyên hành
   vi "chỉ emit khi giá trị thực sự đổi" + hỗ trợ tham số `normalize`
   optional (callable áp lên value trước khi so sánh/gán, để giữ được
   hành vi `.strip().upper()` riêng của Data Management).
2. **Chỉ áp dụng thử nghiệm trên `DataManagementViewModel`** trước (nhiều
   property nhất trong 4 ViewModel, nhiều cơ hội đo lợi ích/rủi ro nhất) —
   không đổi cả 4 ViewModel cùng lúc. Sau khi xong, đo lại: giảm bao nhiêu
   dòng, test có xanh không, rồi mới quyết có lan tiếp sang 3 ViewModel còn
   lại hay dừng ở đây (quyết định đó thuộc lần rà soát sau, không tự động
   nằm trong task này).
3. Giữ nguyên tên property/signal hiện có ở QML — không đổi hợp đồng
   QML-facing, chỉ đổi cách Python định nghĩa nó.

## Tiêu chí xong

- `DataManagementViewModel` dùng `notifying_property(...)` cho ít nhất các
  property đã nêu ở "Hiện trạng" (`selectedSymbol`, `selectedInterval`,
  `symbolOptions`) — không bắt buộc đổi hết mọi property của file này
  trong 1 lần, ưu tiên minh hoạ được lợi ích rõ ràng trước.
- Test hiện có của `DataManagementViewModel`/`data_management_presenter.py`
  xanh không đổi assertion — QML-facing behavior (giá trị đọc/ghi qua
  `selectedSymbol`, `selectedInterval`, thời điểm signal `*Changed` phát)
  giữ nguyên y hệt.
- Không đụng tới `BaseQmlViewModel` ở repo `sagittarius_engine`.
