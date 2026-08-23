# EPIC-005 — Rút khỏi QML, quay về QtWidgets (form/bảng tra cứu, không phải toàn app)

**Trạng thái:** 🟡 Đang làm (5/6 task con xong)
**Loại:** Presentation / Kiến trúc UI
**Ưu tiên:** P2 — không có tác động runtime; đây là quyết định hướng đi dài hạn
**Nhánh:** `epic/EPIC-005-qml-to-qtwidgets` — tách riêng vì epic này **có thể phải rollback**

> **Phạm vi đã thu hẹp sau `EPIC-005A`'s ADR (2026-08-23, user đã duyệt).** Xem
> [`DECISION_2026-08-23.md`](DECISION_2026-08-23.md) toàn văn. Tóm tắt: lý do gốc chọn QML
> (`BOT-030` — *"AI dịch mockup sang code trực tiếp hơn ở QML"*) vẫn đúng và vẫn đang hoạt
> động (15+ task `BOT-040`..`BOT-112C` tiếp tục theo mockup). Epic **không huỷ**, nhưng
> **`EPIC-005F` (backtest + dashboard) hoãn vô thời hạn** — đó chính là nơi lý do gốc phát
> huy tác dụng. Chỉ migrate `SettingsScreen`/`DatabaseScreen` (form/bảng tra cứu, ít nhận
> mockup mới, giá trị QtWidgets áp dụng trực tiếp).

---

## 🎯 Mục tiêu

Chuyển phần lớn UI của app từ QML về QtWidgets, **giữ nguyên chart trên QtQuick**, theo
từng màn hình một, mỗi bước tự rollback được.

## 📊 Số liệu thật (đo 2026-08-23, không ước lượng)

| Nhóm | File `.qml` | LOC |
| :--- | ---: | ---: |
| `components/` | 16 | 2.783 |
| `screens/backtest/` (gồm cả chart) | 6 | 1.811 |
| `screens/data_management/` | 3 | 1.736 |
| `screens/dashboard/` | 1 | 385 |
| `screens/settings/` | 1 | 363 |
| **Tổng Elite** | **27** | **7.078** |

Engine còn thêm 11 component QML (1.722 LOC) trong `pyside_mvc` — **ngoài phạm vi epic này**,
xử lý sau khi app chứng minh được hướng đi.

Thuận lợi sẵn có: **mọi màn hình đã có view Python dạng `QWidget`** (`settings_view.py`,
`data_management_view.py`, `backtest_view.py`, `dashboard_view.py`, …). QML hiện chỉ là *đảo
nhúng* qua `QQuickWidget` bên trong các shell đó. Nên đây **không phải thay nền móng** —
nền móng đã là QtWidgets.

## ⚠️ Ranh giới cứng: chart ở lại QtQuick

```
native/chart_renderer/native_chart_item.h:29
  class NativeChartItem : public QQuickItem
  QSGNode* updatePaintNode(QSGNode* oldNode, ...)
```

~1.950 dòng C++ render trực tiếp trên **QtQuick scene graph (GPU)**, đăng ký làm QML plugin,
có benchmark Python-vs-Native với CI contract riêng. QtWidgets **không có scene graph** —
thay thế nghĩa là viết lại bằng `QPainter` (raster CPU) hoặc `QOpenGLWidget`, đánh đổi hiệu
năng ở đúng component nặng nhất của một app giao dịch.

`NativeBacktestChart.qml` và `components/native_chart_card.py` **không nằm trong epic này.**

## 🧭 Hệ quả phải chấp nhận trước khi bắt đầu

**Migrate KHÔNG xoá được pipeline styling thứ hai.** Vì chart ở lại QtQuick, app vẫn phải
nuôi `QQuickWidget` + Theme bridge mãi mãi. Kết quả cuối là "QtWidgets + QML(chart)", không
phải "chỉ QtWidgets".

Nghĩa là **lợi ích thu được không phải "bớt một stack"**, mà là:

- Form/bảng/picker dùng widget gốc: tab-order, focus, keyboard nav, accessibility, sort/resize
  cột — có sẵn thay vì tự viết.
- Lỗi lộ ra lúc compile/type-check thay vì lúc chạy. QML sai chỉ biết khi render, đó chính là
  lý do phải đẻ ra cả bộ guard (anti-literal-colour, anti-raw-primitive, gallery-coverage).
- Debug bằng công cụ Python bình thường, không qua JS engine.

Ai đọc epic này mà kỳ vọng "bỏ QML cho gọn stack" là kỳ vọng sai — nói rõ ở đây để không ai
đo thành công bằng tiêu chí đó.

## 🔁 Chiến lược rollback

- Toàn bộ epic nằm trên nhánh `epic/EPIC-005-qml-to-qtwidgets`, **không merge vào
  `master-warrior` cho tới khi ít nhất `EPIC-005D` (pilot) chạy xanh và được chấp nhận.**
- Mỗi màn hình là một commit độc lập — QML và QtWidgets là file khác nhau, nên revert một
  màn hình không đụng màn hình khác.
- **Không xoá file `.qml` ở commit migrate.** Chỉ ngừng nạp nó. Xoá dồn vào một commit dọn
  dẹp riêng ở cuối, sau khi đã chạy thật. Đây là điều làm rollback rẻ.
- Mốc so sánh **tại thời điểm tạo epic này (2026-08-23)**: `1789 passed / 54 sanity`.

  ⚠️ **Đừng chép lại con số này như chân lý.** Nó đã trôi ngay trong ngày: mốc sau EPIC-004 là
  `1780/50`, rồi `BUG-036` (chart benchmark) và task gỡ mypy override merge vào thành `1789/54`
  chỉ sau vài giờ. **Mỗi task con phải tự chụp baseline ngay trước khi sửa dòng đầu tiên**, và
  so với chính con số đó — không so với con số viết trong tài liệu.

## 🗂️ Task con

| ID | Tên | Trạng thái |
| :--- | :--- | :---: |
| **[EPIC-005A](incomplete/EPIC-005A_quyet_dinh_va_dieu_kien_dung.md)** | Ghi lại vì sao đảo chiều, và điều kiện dừng | ✅ Xong — ADR duyệt 2026-08-23 |
| **[EPIC-005B](completed/EPIC-005B_xoa_qss_chet_va_chan_tai_phat.md)** | `style.qss` hoá ra đã chết — xoá + chặn trùng lặp token thật | ✅ Xong |
| **[EPIC-005C](completed/EPIC-005C_dong_bang_qml_va_go_xung_dot.md)** | Đóng băng QML (phạm vi thu hẹp) + gỡ xung đột với EPIC-003D | ✅ Xong — xung đột tự biến mất sau khi `F` hoãn |
| **[EPIC-005D](completed/EPIC-005D_pilot_settings_screen.md)** | Pilot: `SettingsScreen` (nhỏ nhất) — đo chi phí thật | ✅ Xong — chi phí thấp hơn dự kiến, N=0 component kit |
| **[EPIC-005E](completed/EPIC-005E_data_management.md)** | `data_management` (mật độ form cao nhất) — chia 3 sub-task (E1/E2/E3) | ✅ Xong (3/3) |
| **[EPIC-005F](incomplete/EPIC-005F_backtest_dashboard_va_don_dep.md)** | `backtest` (trừ chart) + `dashboard` | ⏸️ **Hoãn vô thời hạn** — xem ADR §4 |

**Thứ tự bắt buộc:** `A` ✅ → `B` ✅ → `C` ✅ → `D` ✅ *(điểm quyết định — đi tiếp)* → `E` ✅.
`F` không nằm trong lộ trình chủ động nữa — xem lại nếu Backtest/Dashboard vào giai đoạn bảo
trì (ít nhận mockup mới liên tục), không phải theo lịch cố định.

## 🚧 Xung đột đã biết: EPIC-003D

[`EPIC-003D — Dọn components/`](../EPIC-003_presenter_and_god_file_decomposition/incomplete/EPIC-003D_qml_component_split.md)
đang 🔴 chưa làm, và nội dung của nó là **sắp xếp lại 16 file QML trong `components/`** (9 file
chỉ dùng bởi đúng 1 màn hình, cần dời về thư mục màn hình đó).

Hai epic này đá nhau: dời file QML rồi sau đó xoá chính nó là công cốc. `EPIC-005C` phải
chốt một trong hai hướng, **không được để cả hai cùng mở**:

- **Hoãn EPIC-003D** cho tới khi EPIC-005 kết thúc (khi đó phần lớn `components/` đã biến mất,
  việc dọn còn lại nhỏ hơn nhiều); **hoặc**
- **Huỷ EPIC-005 và làm EPIC-003D** nếu `EPIC-005A` kết luận không nên đảo chiều.

Việc phát hiện 9/18 file bị đặt sai chỗ của EPIC-003D **vẫn là dữ liệu có giá trị** cho
EPIC-005 — nó cho biết component nào thật sự dùng chung, component nào chỉ thuộc về một màn
hình (và do đó migrate cùng màn hình đó, không cần làm thành widget dùng chung).

## 📌 Ngoài phạm vi

- Chart (`NativeChartItem`, `NativeBacktestChart.qml`, `native_chart_card.py`).
- 11 component QML trong engine `pyside_mvc` (1.722 LOC) — chỉ tính sau khi app xong.
- Đổi behaviour, đổi layout, "nhân tiện" cải tiến UI. Migrate là **đổi công nghệ, giữ nguyên
  hành vi**; trộn thêm thay đổi vào sẽ làm mất khả năng khẳng định "không regression".
