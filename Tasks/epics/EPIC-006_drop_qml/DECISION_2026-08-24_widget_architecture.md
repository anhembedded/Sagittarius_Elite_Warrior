# ADR — Kiến trúc kế thừa cho widget QtWidgets thay thế kit QML

**Thuộc:** [`EPIC-006`](README.md)
**Ngày:** 2026-08-24
**Trạng thái:** Đã duyệt — user chốt sau 2 vòng chỉnh sửa

---

## 1. Vấn đề — "card với non-card đang lộn xộn"

Kit QML hiện tại (`Sagittarius_Engine/.../pyside_mvc/Sagittarius/UI/`) có 9 type đăng ký trong
`qmldir`, nhưng chỉ 3 cái thật sự là card:

```
Rectangle → BaseCard → LogPanel, TimeRangeCard, AppDataTable   (3 cái — thật sự là card)
Rectangle → FieldBackground                                     (không phải card)
Button    → StatefulButton                                      (không phải card)
CheckBox  → StyledCheck                                          (không phải card)
Item      → DateTimePicker                                       (không phải card)
Popup     → AppModal                                              (không phải card)
```

4 thư mục stub (`ActionCard`/`FormCard`/`StreamCard`/`TableCard`, chỉ có `NOTES.md`, không có
`.qml`) giả định **mọi thứ đều thuộc họ Card** — đó là trục phân loại sai, và là nguồn gốc thật
của câu hỏi "1 cái nút bấm thì sao lại là card được?".

Phía QtWidgets (viết tạm ở `EPIC-005`) còn tệ hơn: `base_card.py`'s `BaseCard(QFrame)` docstring
ghi "styling qua QSS target `#base_card`", nhưng file QSS đó **đã bị xoá ở `EPIC-005B` vì chết**
— `BaseCard` hiện không được style bởi bất cứ thứ gì, chỉ có 2 consumer thật
(`ChartCard`/`NativeChartCard`). 8 widget viết ở `EPIC-005` (`LogPanelWidget`,
`TimeRangeCardWidget`, các dialog) đều bỏ qua `BaseCard`, tự viết `setStyleSheet(f"...")` riêng
lẻ — mỗi cái là một nơi phải sửa khi đổi token.

## 2. Trục phân loại đúng — theo vai trò trong bố cục, không theo hình dạng

| Họ | Định nghĩa | Chứa thành phần khác? | Vòng đời |
| :--- | :--- | :---: | :--- |
| **Surface/Card** | Vùng nền chiếm chỗ, ôm thành phần khác | Có | `setEnabled()` lan xuống con (Qt có sẵn) |
| **Control** (`Styled*`) | Phần tử lá, tương tác trực tiếp | Không | `setEnabled()` cho chính nó |
| **Overlay** | Nổi trên layer, tự quản modal/đóng | Có | `open`/`accept`/`reject` |

## 3. Ràng buộc kỹ thuật quyết định hình dạng cây kế thừa: không đa kế thừa

Phiên bản sơ đồ đầu tiên đề xuất `StyledButton(QPushButton, AbstractControl)` với
`AbstractControl` kế thừa `AbstractStyledWidget→QFrame`. **Sai cả về mặt kỹ thuật lẫn theo yêu
cầu của user**: PySide6/Shiboken cấm một class kế thừa 2 lớp có gốc `QObject` khác nhau —
`QPushButton` và `QFrame` là 2 lineage Qt riêng biệt, không thể đứng chung trong MRO của 1
class. Cùng lỗi ở `AbstractOverlay(QDialog, AbstractStyledWidget)`.

User chốt rõ: **không đa kế thừa ở bất kỳ đâu**, kể cả những chỗ PySide6 có thể cho phép về mặt
kỹ thuật (mixin thuần Python không kế thừa QObject). Nên thiết kế cuối dùng **4 chuỗi kế thừa
đơn tuyến độc lập**, không có node nào dùng chung giữa các chuỗi:

```
QFrame  → Surface → Card → LogPanel, DataTable
QFrame  → Surface → Panel
QDialog → Overlay → ConfirmOverlay, PickerOverlay
QPushButton → StyledButton
QCheckBox   → StyledCheckBox
QLineEdit   → StyledField → DateTimeField
```

Styling dùng chung (thứ trước đây định nhét vào 1 base lai) chuyển thành **composition**, không
phải kế thừa:

```python
class StyleRole(Enum):
    PRIMARY_BUTTON = auto()
    DANGER_BUTTON = auto()
    FIELD = auto()
    BADGE = auto()
    CARD_SURFACE = auto()

def apply_role(widget: QWidget, role: StyleRole, *, state: State = State.NORMAL) -> None:
    """Nơi DUY NHẤT được phép chứa hex literal/Palette token trực tiếp.
    Mọi widget bất kể lineage nào gọi hàm này trong __init__."""
    widget.setStyleSheet(_build_qss(role, state))
```

Mọi lớp cụ thể (`Card`, `Overlay`, `StyledButton`, ...) gọi `apply_role()` trong `__init__` của
chính nó thay vì kế thừa hành vi style. Đây là cách giữ đúng lời hứa của `ui-architecture.md` §1
("đổi 1 token, 0 file consumer phải sửa") mà không cần ép mọi widget vào 1 cây kế thừa.

## 4. Kỷ luật "luôn có abstract" — áp dụng có giới hạn

User: "luôn luôn có abstract". Áp dụng cho **gốc của mỗi chuỗi phân loại thật**
(`Surface`, `Card`, `Overlay`) — đây là phân loại, không phải suy đoán, và mỗi cái đã có ≥2
instance cụ thể ngay từ đầu.

> ⚠️ **Hết hiệu lực 2026-08-25:** ngưỡng *"chỉ tạo abstraction khi có ≥2 nhu cầu thật"* đã bị user bỏ. Nay **luôn khuyến khích abstraction** — xem [`architecture-rule.md` §7.2](../../../.agents/rules/architecture-rule.md). Đoạn dưới giữ nguyên làm hồ sơ lịch sử; đừng dùng nó làm tiêu chí chặn.

**Không** áp dụng để tạo lại kiểu tầng trung gian như `FormCard`/`StreamCard`/`TableCard`/
`ActionCard` cũ — cả 4 cái đó được suy đoán ra từ một docstring, chưa từng có 2 nhu cầu thật
giống nhau, và khi kiểm tra lại thì **toàn bộ lý do chúng tồn tại tự biến mất** khi chuyển sang
QtWidgets: `setEnabled(False)` của Qt tự lan xuống mọi widget con, đúng thứ 4 stub đó cố tái
tạo thủ công trong QML (QML không có disable lan truyền sẵn). Giữ nguyên kỷ luật cũ từ
`EPIC-001C`: chỉ tạo abstraction mới khi có ≥2 instance thật cần đúng contract đó — kỷ luật này
chính là thứ đã ngăn được 4 abstraction thừa nói trên, nên giữ lại, không nới lỏng nó cho tầng
trung gian.

## 5. Đặt tên và vị trí

- Đổi `Sagittarius_Engine/.../pyside_mvc/Sagittarius/UI/` (QML) → `pyside_mvc/widgets/`
  (QtWidgets, Python). "Kit" là thuật ngữ mơ hồ không nói được nó là gì — bỏ, không dùng lại ở
  tên mới.
- Engine's `widgets/` **không được biết bất kỳ app nào tồn tại** — đúng `ui-architecture.md` §1
  vốn đã áp dụng cho QML, giữ nguyên cho QtWidgets: chỉ cung cấp hình dạng (`Card`, `Panel`,
  `Overlay`, `StyledButton`, ...), không có tên nghiệp vụ.
- Elite đặt tên nghiệp vụ, kế thừa từ engine: `ChartCard(Card)`, `MetricCard(Card)`,
  `SyncControlsCard(Card)`, `GapInspectorOverlay(Overlay)`.

## 6. Guard mới thay guard QML cũ

3 guard hiện có (`raw_primitive_guard`, `qml_literal_guard`, `rectangle_card_guard`,
`gallery_coverage_guard`) đều nhắm QML, mất referent khi kit QML bị tháo (`EPIC-006F`). Guard
thay thế cho QtWidgets:

- Cấm `setStyleSheet(...)` chứa hex literal ở bất kỳ file nào **ngoài** module chứa
  `apply_role()`/`_build_qss()` — thay `qml_literal_guard`.
- Cấm kế thừa thẳng `QFrame`/`QDialog` khi đã có `Surface`/`Overlay` tồn tại — thay
  `rectangle_card_guard`.
- Coverage guard: mọi type trong engine's `widgets/` phải xuất hiện trong showcase/preview
  tương đương — thay `gallery_coverage_guard`.

Viết cụ thể ở `EPIC-006B`, khi các base class thật đã tồn tại để guard có gì mà kiểm tra.
