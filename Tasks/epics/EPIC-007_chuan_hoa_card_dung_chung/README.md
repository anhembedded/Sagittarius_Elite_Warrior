# EPIC-007 — Chuẩn hoá card dùng chung, đưa hình dạng lên Engine

**Trạng thái:** 🟡 Đang làm (5/7 task con — `007A`–`007E` xong 2026-08-25; `007F` đang làm — Settings + Dashboard, guard bare-base 17→16)
**Loại:** Presentation / Kiến trúc UI
**Ưu tiên:** P2 — không có tác động runtime tức thời; giảm chi phí sửa UI về sau
**Nhánh đề xuất:** `epic/EPIC-007-chuan-hoa-card`
**Epic song sinh:** [`EPIC-008`](../EPIC-008_chuan_hoa_luong_event/) (event) — độc lập, làm
song song được, không chia sẻ file nào.

> **Nối tiếp [`EPIC-006`](../EPIC-006_drop_qml/README.md), không thay thế nó.** `EPIC-006B` đã
> xây `Surface`/`Card`/`Panel`/`Overlay`/`Styled*` ở Engine. Epic này giải quyết chuyện xảy ra
> sau đó: **một nửa số base class ấy chưa từng được dùng một lần nào**, và 4 màn hình vẫn tự
> đẻ card riêng.

---

## 1. Vấn đề — đo bằng chính guard của Engine, 2026-08-24

Chạy `widgets.guards.find_bare_qt_base_widgets` + `find_inline_stylesheets` lên
`src/presentation/ui`:

| Chỉ số | Giá trị |
| :--- | ---: |
| Lớp kế thừa thẳng `QFrame`/`QDialog` | **12** |
| Hex literal ngoài `style.py` | **130** |
| Lời gọi `setStyleSheet` | **246** |
| Hằng màu riêng cấp module ở 4 màn | **18** |
| Biến thể màu nền card gần trùng nhau | **~10** |

Mức độ dùng lại base class của Engine trong toàn Elite:

| Base class | Số consumer thật |
| :--- | ---: |
| `Overlay` | 11 (chỉ Backtest modals) |
| `SelectableCard` | 7 |
| `StyledCheckBox` | 3 |
| **`Surface` / `Card` / `Panel`** | **0** |
| **`StyledButton` / `StyledField` / `DateTimeField`** | **0** |

Hình dạng bị viết lại nhiều lần: nhãn mục ×3 · badge ×4 · dòng dữ liệu + nút hành động ×4 ·
header cột + phân trang ×3 · banner ×5 · thẻ số liệu ×2.

Và một rò rỉ kiến trúc: **`data_management_widgets.py` (1.156 dòng) đã vô tình trở thành thư
viện widget chung của cả app** — 3 file ở 2 màn khác import chéo vào lấy `LogPanelWidget` /
`AppProgressBarWidget`.

Chi tiết đầy đủ + sơ đồ: [`design/`](design/) — 4 file PlantUML (2 hiện trạng, 2 đề xuất).

## 2. Năm điều phản trực giác epic này phải sửa

Ghi lại theo `.agents/rules/surprising-findings.md` — mỗi cái đều là một yêu cầu, không phải
ghi chú.

| # | Phát hiện | Sửa ở |
| :-: | :--- | :--- |
| 1 | `Surface`/`Card`/`Panel` **0 consumer** — nửa `EPIC-006B` ship rồi nằm không | 007B, 007E, 007F |
| 2 | `Overlay` báo lỗi bảo người dùng dựng `ConfirmOverlay`/`PickerOverlay` — **cả hai không tồn tại** ở bất kỳ đâu trong engine | 007A (`BUG-004` bên Engine) |
| 3 | Docstring `dev_board_panel.py` nói màu riêng là "bản sắc testbed cố ý" — **đã không còn đúng**: `backtest_top_panel.py` chép y hệt 5 giá trị đó | 007D |
| 4 | Guard chỉ khớp `QFrame`/`QDialog` → **7 widget kế thừa `QWidget`** mà thực chất là surface đều lọt lưới. Con số "12" là mức sàn | 007A |
| 5 | `data_management_widgets.py` thành thư viện chung ngoài ý muốn — 3 import chéo màn hình | 007E, 007G |

## 3. Quyết định đã chốt (user, 2026-08-24)

1. **Gộp màu về 1 token**, chấp nhận đổi pixel. `Palette.BG_CARD` (`#111318`) là màu nền card
   duy nhất; ~10 biến thể bị xoá. Đây là cách duy nhất giữ được lời hứa của
   `ui-architecture.md` §1 ("đổi 1 token, 0 file consumer phải sửa").
2. **Phạm vi 4 màn**: Dashboard (Dev Board), Backtest, Data Management, Settings.
3. **Tiêu chí 3 tầng** quyết định "cái này để đâu":
   - **Engine** — mô tả được mà không nhắc tới giao dịch/Binance/nến/backtest, **và** đã có
     **≥2 instance thật** ở Elite hôm nay.
   - **Elite `components/`** — dùng ở ≥2 màn nhưng tên/hành vi mang nghiệp vụ.
   - **`screens/`** — chỉ 1 màn dùng.

   ⚠️ **Sửa 2026-08-25:** ngưỡng *"≥2 nhu cầu thật"* đã bị user bỏ; nay **luôn khuyến khích
   abstraction** ([`architecture-rule.md` §7.2](../../../.agents/rules/architecture-rule.md)).
   Bài học chống-đoán-sai vẫn giữ: 4 stub kia sai vì **đoán sai hình dạng** thứ chưa tồn tại,
   không phải vì "có abstraction". Câu gốc giữ lại bên dưới làm bối cảnh — chính
   nó đã ngăn được 4 stub thừa `ActionCard`/`FormCard`/`StreamCard`/`TableCard`.
4. **Phân rã file**: 1 file 1 lớp cho widget ở Engine. Ngưỡng phải tách: **>400 dòng** hoặc
   **>15 phương thức công khai**. Giới hạn duy nhất là Single-Scope Cohesion — `StyleRole` và
   `_build_qss()` phải ở chung `style.py` vì cùng một vòng đời.

## 4. Thứ tự thực hiện — rủi ro tăng dần, mỗi bước rollback được

| ID | Việc | Repo | Trạng thái |
| :--- | :--- | :--- | :---: |
| **[007A](completed/EPIC-007A_guard_va_overlay_con.md)** | Engine: mở rộng guard sang `QWidget`; thêm `ConfirmOverlay`/`PickerOverlay` thật | Engine | ✅ |
| **[007B](completed/EPIC-007B_engine_surface_family.md)** | Engine: `LogPanel`, `StatCard`, `DataRow`, `TableCard`, `Banner`, `TabBar` — 1 file 1 lớp | Engine | ✅ |
| **[007C](completed/EPIC-007C_engine_controls_va_showcase.md)** | Engine: `StyledLabel`/`SectionLabel`/`Badge`/`StyledProgressBar` + showcase + coverage guard | Engine | ✅ |
| **[007D](completed/EPIC-007D_gop_token_mau.md)** | Elite: xoá 18 hằng màu riêng, gộp về `Palette`; sửa docstring sai của Dev Board | Elite | ✅ |
| **[007E](completed/EPIC-007E_elite_components_dung_chung.md)** | Elite: `components/` — `ChartCard(Card)` thay `BaseCard`, `TimeRangeCard`, `SymbolPickerOverlay`; cắt 3 import chéo | Elite | ✅ |
| **[007F](incomplete/EPIC-007F_migrate_4_man_hinh.md)** | Elite: migrate 4 màn sang widget mới | Elite | 🔵 |
| **[007G](incomplete/EPIC-007G_tach_file_qua_nguong.md)** | Elite: tách các file vượt ngưỡng | Elite | 🔵 |

`007A`→`007C` phải xong trước `007D`→`007G`: các task Elite cần base class thật để kế thừa,
không được tự chế QSS inline tạm — đúng bài học `EPIC-005` (8 widget tự viết `setStyleSheet`
riêng, chính là thứ sinh ra epic này).

**Hai repo, hai commit, không có bước đồng bộ** (`Sagittarius_Engine/.agents/ONBOARDING.md` §8).
Task Engine (`007A`–`007C`) commit ở repo Engine; task Elite commit ở repo Elite.

## 5. Điều kiện dừng (kill criteria)

- Sub-task nào vượt quá 3 lần ước lượng ban đầu → dừng, đánh giá lại.
- Regression thị giác ngoài phần đã được duyệt ở §3.1 (gộp màu) mà không sửa được trong buổi
  làm việc đó → dừng, rollback.
- `scripts/ci-local.ps1` không giữ được baseline chụp trước mỗi sub-task → dừng, sửa nguyên
  nhân trước, không merge lúc đỏ.
- ~~Một base class mới sinh ra mà chưa có ≥2 consumer thật → **không tạo**~~ — ngưỡng ≥2 đã bị
  user bỏ 2026-08-25 (xem cảnh báo ở §3.3). Thay bằng: **một base class mới mà hình dạng của nó
  là phỏng đoán** — chưa có consumer thật nào để đối chiếu — thì **không tạo**, ghi lại làm ứng
  viên. Cái sai của 4 stub `ActionCard`/`FormCard`/`StreamCard`/`TableCard` là đoán sai hình
  dạng thứ chưa tồn tại, không phải "mới có 1 consumer". `007A` áp đúng luật này khi để
  multi-select của `IndicatorPickerDialog` ra ngoài `PickerOverlay`.

## 6. Ngoài phạm vi

- Luồng sự kiện — thuộc [`EPIC-008`](../EPIC-008_chuan_hoa_luong_event/).
- `Sidebar` và `_NavButton`: `EPIC-006C` đã quyết định có chủ đích rằng chúng **không** ép vào
  `Surface`/`StyledButton` (window chrome, không phải nội dung màn hình). Giữ nguyên quyết
  định đó, không lật lại.
- `ChartCard`'s pyqtgraph internals — chỉ đổi lớp cha, không đụng phần vẽ.
- `examples/student_management` của Engine.
