# EPIC-006 — Bỏ hẳn QML, thuần QtWidgets

**Trạng thái:** 🟡 Đang làm (5/6 sub-task xong)
**Loại:** Presentation / Kiến trúc UI
**Ưu tiên:** P2 — không có tác động runtime tức thời; quyết định hướng đi dài hạn
**Nhánh:** `epic/EPIC-006-drop-qml` — **đã merge vào `master-warrior`** (`f4076a7`, 2026-08-24,
`--no-ff`, gate xanh thật). Nhánh vẫn còn để rollback cho tới khi `006F` xong.

> **Hai việc còn nợ, ghi ở đây để không ai tưởng epic đã sạch (rà soát 2026-08-25):**
>
> 1. ~~`EPIC-006F` chưa có file task~~ — **đã tạo 2026-08-25**:
>    [`incomplete/EPIC-006F_thao_do_kit_qml.md`](incomplete/EPIC-006F_thao_do_kit_qml.md).
>    Nó ghi lại phạm vi đo thật, và **một câu hỏi mở phải để user chốt**: kit QML của Engine
>    vẫn là backend **mặc định** của `examples/student_management`, nên xoá kit là tước một
>    backend của framework vì lý do chỉ đúng với Elite.
> 2. **22 file `.qml` chết vẫn còn trong `src/`** (`components/*.qml`, `screens/backtest/*.qml`
>    …). Đã kiểm chứng: **không `.py` nào còn nạp chúng** — mọi hit `load_qml`/`QQuickWidget`
>    trong `src/` giờ đều là docstring/comment. Chúng chỉ tham chiếu lẫn nhau nên phép dò
>    "file mồ côi" thông thường **không** phát hiện được; phải kiểm từ phía Python. Đây đúng
>    loại rác mà `EPIC-006A` đã dọn 1 lần (4 file, 2.099 dòng `EPIC-005` để lại) — đợt này do
>    `006C`/`006D`/`006E` sinh ra và chưa ai dọn.

> **Đảo ngược kết luận §4 của [`EPIC-005`'s ADR](../EPIC-005_qml_to_qtwidgets_migration/DECISION_2026-08-23.md)**,
> ghi lại rõ ràng chứ không lặng lẽ bỏ qua. ADR đó hoãn `EPIC-005F` vô thời hạn vì hai lý do:
> (1) Backtest/Dashboard nhận mockup mới liên tục — QML nhanh hơn khi AI dịch mockup, và
> (2) chart bắt buộc ở lại QtQuick vì hiệu năng GPU. Lý do (2) đã sập hoàn toàn ở `BUG-039`
> (2026-08-24): chart native chưa từng render 1 khung hình nào trong production, bản
> QtWidgets/pyqtgraph mới là bản đầy đủ hơn. Lý do (1) vẫn đúng về mặt hiện tượng (Backtest có
> `StrategyPropertiesModal.qml` 766 dòng vẫn đang sửa), nhưng `EPIC-005D/E` đã chứng minh chi
> phí migrate **thấp hơn ước lượng ban đầu 3 lần** ở mọi sub-task — premise "QtWidgets làm chậm
> chu kỳ tính năng" chưa từng được đo thật, chỉ suy đoán.
>
> Quyết định của user (2026-08-24): bỏ hết QML, triết lý hiện tại của dự án là không dùng QML
> để giảm chi phí phát triển (một stack, một cách styling, một cách test — không phải maintain
> song song 2 pipeline). Giữ nguyên giao diện/hành vi hiện có qua `qdarktheme` + `Palette`
> token, đúng cách `EPIC-005` đã làm.

---

## 1. Phạm vi thật (đo 2026-08-24, không ước lượng)

| Nhóm | LOC | Trạng thái |
| :--- | ---: | :--- |
| QML đã chết ở Elite (4 file, EPIC-005 để lại) | 2.099 | ✅ Xoá ở `EPIC-006A` |
| QML còn sống ở Elite | 4.806 | 🔴 Chưa làm — 22 file |
| ↳ `Sidebar.qml` (chrome always-on) | 238 | |
| ↳ `DevBoardPanel.qml` (Dashboard) | 385 | |
| ↳ Backtest (top panel, trade logs, modals) | ~4.183 | |
| Kit QML ở Engine (`Sagittarius_Engine/sagittarius_engine/extensions/pyside_mvc/Sagittarius/UI/`) | 1.683 | 🔴 Chưa làm — chỉ tháo được sau khi Elite hết consumer |
| Python chỉ-phục-vụ-QML ở Engine (`QmlHostView`, `configure_app_qml`, `theme_bridge`, image provider, `BaseQmlViewModel`, `OverlayHost`) | 608 | 🔴 Chưa làm |

Không phải toàn bộ phần "còn sống" đều phải viết lại tay: `DateTimePicker.qml` (400) →
`QDateTimeEdit` có sẵn, `AppDataTable.qml` (252, engine, 0 consumer thật ở Elite) → xoá thẳng,
`AppModal.qml`+`ModalDialogCard.qml` (339) → `QDialog` có sẵn. Chi phí thật thấp hơn tổng LOC
đáng kể.

## 2. Kiến trúc widget thay thế — quyết định trước khi migrate bất kỳ màn nào

Xem [`DECISION_2026-08-24_widget_architecture.md`](DECISION_2026-08-24_widget_architecture.md)
(ADR riêng, vì đây là quyết định kiến trúc độc lập với quyết định "có bỏ QML hay không" — có
thể đúng ngay cả khi ta không bỏ QML, và ngược lại). Tóm tắt:

- **4 chuỗi kế thừa đơn tuyến, không đa kế thừa** (PySide6/Shiboken cấm 2 gốc QObject):
  `QFrame→Surface→Card`, `QDialog→Overlay`, và mỗi `Styled*` kế thừa đúng 1 lớp Qt gốc của nó
  (`QPushButton`, `QCheckBox`, `QLineEdit`).
- **Styling dùng chung qua composition (`apply_role()`), không qua kế thừa** — mọi widget bất
  kể lineage nào gọi hàm này trong `__init__`, đây là nơi duy nhất chứa QSS/hex literal.
  Guard mới cấm hex literal xuất hiện ngoài file này (thay `qml_literal_guard`).
- **Luôn có abstract ở gốc mỗi chuỗi** (`Surface`, `Card`, `Overlay`) — nhưng không tạo tầng
  trung gian suy đoán (bài học từ 4 stub `ActionCard`/`FormCard`/`StreamCard`/`TableCard` của
  kit QML cũ — cả 4 tự biến mất khi có `setEnabled()` sẵn của Qt, không cần base riêng).
- **Ranh giới engine/app giữ nguyên** từ `ui-architecture.md` §1: engine's `widgets/`
  (đổi tên từ `Sagittarius/UI/` — "kit" là thuật ngữ mơ hồ, bỏ) không biết bất kỳ app nào tồn
  tại, chỉ cung cấp hình dạng (`Card`, `Panel`, `Overlay`, `Styled*`). Elite đặt tên nghiệp vụ
  (`ChartCard`, `SyncControlsCard`, `GapInspectorOverlay`) kế thừa từ đó.

## 3. Thứ tự thực hiện — rủi ro tăng dần, mỗi bước tự rollback được

| ID | Việc | Trạng thái |
| :--- | :--- | :---: |
| **EPIC-006A** | Xoá 2.099 dòng QML đã chết (4 file EPIC-005 để lại) + 1 test standalone lỗi thời (`BUG-028` không còn khả năng xảy ra khi hết QML) | ✅ Xong |
| **[EPIC-006B](completed/EPIC-006B_engine_widget_base_classes.md)** | Engine: xây `Surface`/`Card`/`Overlay`/`Styled*`/`apply_role()` theo ADR §2, guard mới (`TASK-038`) | ✅ Xong |
| **[EPIC-006C](completed/EPIC-006C_sidebar.md)** | Elite: `Sidebar.qml` (238 dòng, always-on, pilot rủi ro thấp nhưng lỗi lộ ngay) | ✅ Xong |
| **[EPIC-006D](completed/EPIC-006D_dev_board_panel.md)** | Elite: `DevBoardPanel.qml` (385 dòng, Dashboard, độc lập) | ✅ Xong |
| **[EPIC-006E](completed/EPIC-006E_backtest.md)** | Elite: Backtest — top panel / trade logs / 11 modal (không tách 3 lần commit như dự kiến — 1 file test dùng chung cả 3 phần) | ✅ Xong |
| **[EPIC-006F](incomplete/EPIC-006F_thao_do_kit_qml.md)** | Engine: tháo dỡ kit QML (`Sagittarius/UI/`, `QmlHostView`, `configure_app_qml`, `theme_bridge`, guard cũ) sau khi Elite hết consumer; xử lý `examples/student_management/RosterScreen.qml` (consumer duy nhất còn lại ngoài Elite). **Kèm: xoá 22 file `.qml` chết còn sót ở `src/` của Elite** (xem cảnh báo đầu file) | 🔴 Chưa làm — file task đã tạo 2026-08-25; **có 1 câu hỏi mở cần user chốt** (sample app của Engine vẫn dùng QML làm backend mặc định) |

`EPIC-006B` phải xong trước `C`/`D`/`E` vì các sub-task đó cần base class thật để kế thừa, không
tự chế QSS inline như `EPIC-005` từng làm tạm (bài học rút ra: 8 widget viết ở `EPIC-005` đều tự
viết `setStyleSheet` riêng — đúng thứ đang gây lộn xộn được nêu ra khi bắt đầu epic này).

## 4. Điều kiện dừng (kill criteria)

- Bất kỳ sub-task nào vượt quá 3 lần ước lượng ban đầu → dừng, đánh giá lại trước khi tiếp.
- Regression thị giác không sửa được trong buổi làm việc đó → dừng, rollback (nhánh riêng, chưa
  merge — chi phí rollback ~0, đúng pattern `EPIC-005`).
- Gate không giữ baseline tự chụp trước mỗi sub-task → dừng, sửa nguyên nhân trước, không merge
  lúc đỏ.
- Nếu Backtest/Dashboard nhận mockup mới **trong lúc** đang migrate màn đó → dừng migrate màn
  đó, làm mockup theo cách nhanh nhất hiện có, quay lại sau khi màn hình ổn định.

## 5. Ngoài phạm vi

- `examples/student_management` (Engine sample app) không bị xoá QML — nó là ví dụ minh hoạ
  cách dùng framework QML, không phải code Elite tiêu thụ. Quyết định số phận của nó thuộc về
  Engine repo, không phải epic này. `EPIC-006F` chỉ cần đảm bảo không xoá nhầm thứ nó cần.
