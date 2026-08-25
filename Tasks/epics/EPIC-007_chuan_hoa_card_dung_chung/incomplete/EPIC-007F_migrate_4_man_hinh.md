# EPIC-007F — Elite: migrate 4 màn hình sang widget dùng chung

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Elite_Warrior` · **Trạng thái:** 🟡 Đang làm (Settings: 6/13 `setStyleSheet` xong)
**Phụ thuộc:** `007D`, `007E`

---

## Phạm vi

Bốn màn, làm **theo thứ tự rủi ro tăng dần, mỗi màn một commit riêng, rollback được**:

| Thứ tự | Màn | Đổi gì | Hiện `setStyleSheet` |
| :-: | :--- | :--- | ---: |
| 1 | **Settings** | card inline (`settings_view.py:166`) → `Card` | 13 |
| 2 | **Dashboard (Dev Board)** | `DevBoardPanel` → `Panel`; `_SectionLabel` → `SectionLabel`; log → `LogPanel` | 22 |
| 3 | **Backtest** | `BackTestTopPanel` → `Panel`; `MetricCardWidget` → `StatCard`; 4 banner → `Banner`; `DynamicTabBarWidget` → `TabBar`; `_TradeLogRowWidget` → `DataRow`; bảng log → `TableCard` | 33 + 27 + 16 |
| 4 | **Data Management** | `_StatusRowWidget`/`_KLineRowWidget`/`_GapRowWidget` → `DataRow`; 4 `QDialog` → `ConfirmOverlay`/`PickerOverlay`; audit banner → `Banner`; 2 inspector → `TableCard` | 31 + 65 |

Settings đi đầu vì nhỏ nhất và lỗi lộ ra ngay; Data Management đi cuối vì nặng nhất và là nơi
`007E` vừa rút widget ra.

## Yêu cầu

1. **Sau task này, `find_bare_qt_base_widgets` (đã mở rộng sang `QWidget` ở `007A`) phải về 0**
   trên `src/presentation/ui/screens/`, trừ danh sách miễn trừ có ghi lý do.
2. **Giữ nguyên hành vi.** Đây **không** phải task đổi thị giác — phần đổi màu đã làm trọn ở
   `007D`. Mọi khác biệt thị giác phát sinh ở đây là **regression**, phải sửa hoặc rollback.
3. **Không widget nào tự viết `setStyleSheet` có hex.** Cần một biến thể chưa có → thêm
   `StyleRole` ở Engine (`007B`), không vá tại chỗ. Đây chính là sai lầm `EPIC-005` đã mắc.
4. **Test theo màn**: mỗi commit giữ nguyên số test pass so với baseline chụp trước khi bắt đầu
   màn đó. Số test đổi thì phải giải thích từng cái.
5. `_CoverageSegmentWidget` (`data_management_widgets.py:913`) **ở lại screens/** — nó vẽ dải
   phủ dữ liệu theo khoảng thời gian, là khái niệm nghiệp vụ của riêng DataMgmt, không phải
   hình dạng chung. Kế thừa `Panel`, không lên Engine.

## Bằng chứng phải nộp

- Ảnh chụp trước/sau **từng màn** — dùng để chứng minh **không** đổi gì, ngược với `007D`.
- Output guard trước/sau.
- `pwsh -NoProfile -File scripts/ci-local.ps1` sau **mỗi** màn, không phải chỉ ở cuối.

## Rủi ro

Backtest có 11 `Overlay` đã làm đúng từ `EPIC-006E3` — **không đụng vào**, trừ chỗ chúng dựng
`MetricCardWidget` (`ExtendedMetricsModal`). Sửa nhầm phạm vi ở đây là cách nhanh nhất để phá
một phần đang chạy tốt.

## Tiến độ — 2026-08-25

### Settings, bước 1/13: card ngoài cùng → `Panel`

`settings_view.py:165` — `card = QFrame(); card.setStyleSheet(f"QFrame {{ ... }}")` → `card =
Panel()`. Header tự viết (icon + tiêu đề 2 dòng + dải nền `BG_CARD_HEADER` riêng) **giữ nguyên**,
đưa vào `body_layout` của `Panel` thay vì cố nhét vào header có sẵn của `Card` — header của
`Card` chỉ là một label + `header_actions`, không đủ hình dạng cho header này, ép vào sẽ tạo ra
hai lớp header chồng nhau. `Card` dành cho screen khác trong task này có header đơn giản hơn.

**Bằng chứng thị giác — hai phát hiện, không phải một:**

1. **Bán kính góc 8px → 6px (chấp nhận).** Card hard-code `border-radius: 8px`; `Panel` dùng
   token `radiusMd` = 6px (giá trị chung toàn app từ `EPIC-006B`, không đổi được tại chỗ mà
   không lệch khỏi mọi `Card`/`Panel` khác — đúng thứ yêu cầu 3 cấm). Lệch 2px trên góc bo, không
   thấy bằng mắt thường ở độ phóng đại bình thường, cùng loại phán đoán đã dùng ở
   `SECTION_LABEL_TICKED` (`style.py`) và màu nền `EPIC-007D`.

2. **Cỡ chữ nhãn field nhỏ đi ~2px chiều cao — không phải regression, mà là `BUG-008` lộ ra
   lần hai.** Đo trực tiếp: `QLabel` cùng `font-size: 12px` cho `sizeHint()` cao 16px khi cha là
   `QFrame` tự viết `setStyleSheet` **không có selector** (`background-color: ...; border: ...;`
   — đúng dạng bare-property-list `BUG-008` mô tả), nhưng chỉ cao 14px khi không có cha nào viết
   QSS kiểu đó (dựng độc lập, hoặc cha là `Panel` — QSS đã được `apply_role()` bọc scoped từ khi
   `BUG-008` sửa). Cùng `QFont` (family/pointSize/pixelSize) ở cả hai trường hợp — khác biệt nằm
   ở `QStyleSheetStyle` tính `sizeHint()` khác đi cho widget bị cascade trúng bởi rule không có
   selector của cha, không phải ở font thật sự đổi. Nói cách khác: **card cũ của Settings tự
   dính đúng bug `BUG-008` bằng QSS tay viết của chính nó**, âm thầm phóng to `sizeHint` của toàn
   bộ nhãn field bấy lâu nay — không ai biết vì không có ảnh so sánh pixel-by-pixel trước đây.
   Sau khi lên `Panel` (đã scoped từ bản vá `BUG-008` merge sớm hơn trong phiên này), nhãn hiển
   thị đúng kích thước nó luôn khai báo (`font-size: 12px`), không còn bị thổi phồng.

   Vì lý do 2, diff pixel-by-pixel giữa ảnh trước/sau đo được **772.248 / 1.600.000 pixel khác
   nhau** (48%) — con số đáng sợ nếu đọc ngây thơ, nhưng gần hết là viền anti-alias của MỌI ký tự
   trên màn dịch theo cỡ chữ đúng thay vì cỡ bị bug thổi phồng, không phải một thứ gãy. Xác nhận
   bằng: (a) `card.geometry()`/`header.geometry()`/`body.geometry()` **giống hệt tuyệt đối** giữa
   hai bản (đo trực tiếp qua đúng fixture `main_window`/`navigate` của bộ ảnh chụp, không phải
   script viết riêng), (b) mọi nhãn field neo đúng cùng toạ độ Y tuyệt đối
   (`abs=(286, 387)` cho "Binance API Key" ở cả hai), chỉ có `sizeHint`/độ rộng khác — tức layout
   không xê dịch, chỉ chữ vẽ nhỏ gọn hơn đúng như khai báo.

   **Không sửa gì thêm cho việc này** — nó tự sửa khi màn khác cũng lên `Card`/`Panel`, và đã âm
   thầm áp dụng cho MỌI consumer `Surface`/`Card`/`Panel` hiện có kể từ khi `BUG-008` merge trong
   chính phiên làm việc này (Dashboard/`AppLogPanel`, `ChartCard`, ... — chưa đối chiếu lại từng
   cái, ghi làm việc cần làm nếu có ai hỏi vì sao chữ "nhỏ hơn trước" trên các màn đã lên `Card`).

**Kiểm tra:** `ruff`/`mypy` sạch (baseline không đổi), guard `find_bare_qt_base_widgets` **không
đổi số** — guard chỉ bắt `class X(QFrame):`, không bắt `QFrame()` dựng tại chỗ, nên bước này nằm
ngoài phạm vi đo của nó dù vẫn đáng làm (bỏ 1 khối QSS tay viết). 24 test liên quan (`settings`,
2 guard, `no_cross_screen_imports`) xanh; full suite `1809 passed, 4 skipped, 0 failed`.

### Settings, bước 2/13: 4 `QLineEdit` → `StyledField`, save button → `StyledButton`

`_style_line_edit()` (một khối QSS tay viết dùng lại cho 4 field) bị xoá, thay bằng
`_make_field()` dựng `StyledField` (role `FIELD` của Engine). Hai thứ role `FIELD` **cố ý không
có ý kiến** — chiều cao 34px (phải khớp nút reveal `setFixedSize(36, 34)` bên cạnh) và font
monospace (credential là chuỗi user phải dò từng ký tự) — đặt qua **API widget**
(`setMinimumHeight`, `setFont`), **không** qua stylesheet thứ hai: thêm QSS ở đây sẽ dựng lại
đúng cái cascade không-selector mà `BUG-008` vừa sửa.

Save button → `StyledButton(role=PRIMARY_BUTTON)`.

**Một regression thật, bắt được đúng bằng ảnh so sánh (không phải bằng test):** nút Save mất
`font-weight: bold`. `PRIMARY_BUTTON` mang màu và chrome, không mang weight; QSS cũ có
`font-weight: bold` và role không thay được phần đó. Không có test nào assert lên weight, và
suite vẫn xanh — **chỉ ảnh chụp cho thấy**. Đúng loại lỗi yêu cầu "bằng chứng phải nộp" của task
này sinh ra để bắt. Khôi phục bằng `QFont.setBold(True)` qua API widget, giữ nguyên nguyên tắc
màn này không tự viết QSS.

**Diff pixel: 23.409 / 1.600.000 (1,5%)**, khu trú đúng vùng field + nút (bbox `286,32 →
1563,617`), không lan ra chỗ khác — khác hẳn bước 1 (48%, vì bước 1 đổi `sizeHint` của mọi nhãn).
Phần còn lại là bo góc field 6px → 4px (`radiusSm`) và dịch 1px theo trục dọc, cùng loại chấp
nhận đã ghi ở bước 1: token dùng chung, không sửa tại chỗ được mà không lệch khỏi mọi field khác.

**Kiểm tra:** `ruff` sạch, `mypy` giữ nguyên baseline, 862 test UI unit xanh, full suite
`1809 passed, 4 skipped, 0 failed`.

**Còn lại của Settings (7/13 `setStyleSheet`):** `self.setStyleSheet(background BG)` ở
`_build_ui`, header (dải `BG_CARD_HEADER` + border-bottom), title, subtitle, warning label,
status label, `_field_label()`, reveal button, `QSpinBox`.

Bốn cái trong số đó **chưa có role tương ứng ở Engine**, và theo yêu cầu 3 phải thêm `StyleRole`
mới chứ không vá tại chỗ — chưa làm, ghi lại cụ thể để lần sau không phải đo lại:

| Chỗ | Cần gì | Vì sao role hiện có không khớp |
| :--- | :--- | :--- |
| `_field_label()` | Nhãn body thường: `TEXT_PRIMARY`, 12px, không bold, không letter-spacing | `CAPTION` là `muted` + `fontSizeSm` (11px) — chữ mờ hơn và nhỏ hơn, dùng vào đây là đổi thị giác |
| title (`SAGITTARIUS API KEYS VAULT`) | `ACCENT`, 14px, bold | `SECTION_LABEL` là `muted` + 11px + letter-spacing |
| subtitle / warning | `MUTED` 11px / `ACCENT` 11px | `CAPTION` khớp subtitle; warning cần accent, chưa có |
| `QSpinBox` | Chrome field cho `QSpinBox` | `StyledField` là `QLineEdit`; không có `StyledSpinBox` |

Header riêng (icon + dải `BG_CARD_HEADER` + border-bottom) **giữ tại `screens/settings/`** theo
tiêu chí "1 màn dùng" (§3) — không đẩy lên Engine chỉ vì đây là nơi đầu tiên cần nó.

**Dashboard, Backtest, Data Management:** chưa bắt đầu. Đây mới là phần guard đo được — cả 17
finding `find_bare_qt_base_widgets` nằm ở ba màn này cộng `components/` (Settings đóng góp **0**,
nên yêu cầu 1 của task không đổi số qua hai bước trên).
