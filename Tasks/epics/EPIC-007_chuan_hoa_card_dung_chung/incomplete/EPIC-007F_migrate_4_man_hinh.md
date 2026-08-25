# EPIC-007F — Elite: migrate 4 màn hình sang widget dùng chung

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Elite_Warrior` · **Trạng thái:** 🟡 Đang làm (Settings 9/13; Dashboard: `SectionLabel` + 3 `Panel`, guard 17→16)
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

### Settings, bước 3/13: thêm 2 role ở Engine, áp vào title/subtitle/nhãn field, và bịt 2 chỗ cascade

**Engine trước, Elite sau** — đúng thứ tự đã học được từ sự cố merge lệch ở `EPIC-007E`. Engine
PR #191 merge vào `main` xong mới đụng tới Elite.

**Hai `StyleRole` mới, đo consumer thật trước khi thêm** (đúng phương pháp §5 kill-criteria: hình
dạng phải có consumer thật để đối chiếu, không được đoán):

| Role mới | Consumer thật | Vì sao role sẵn có không dùng được |
| :--- | ---: | :--- |
| `BODY_LABEL` (`textPrimary`, `fontSizeMd`) | 4, ở 3 màn | `CAPTION` cố ý mờ hơn (`muted`, nhỏ hơn 1 bậc) để **lùi ra sau** heading. Nhãn field là chữ user đọc để **thao tác**, không được lùi. |
| `HEADING` (`accent`, `fontSizeMd`, bold) | 3 | `SECTION_LABEL` là nhãn mờ + letter-spacing cho **một nhóm bên trong** panel. Dùng nó cho tiêu đề dialog sẽ làm tiêu đề tụt xuống ngang hàng các nhãn nhóm bên dưới nó. |

Mỗi nhóm mang sẵn kích thước gần-trùng hard-code (12/13px cho body, 13/14px cho heading) — gộp cả
hai về `fontSizeMd` chính là việc epic này sinh ra để làm. Có test ghim rằng chúng không lặng lẽ
tách lại thành hai literal bên trong `style.py`.

**Không thêm widget class mới** — nhãn chỉ cần constructor thì thuộc về `QLabel` + `apply_role()`,
đúng luật `StyledLabel` tự ghi trong docstring của nó.

**`subtitle` dùng `CAPTION` có sẵn, không thêm role.** Đo được **19** chỗ `MUTED` + 11px trong
Elite khớp đúng `CAPTION` — role này đã tồn tại từ `007C` và chưa ai dùng.

**Hai chỗ cascade `BUG-008` bị bịt (giá trị thật, không phải dọn dẹp hình thức):**

- `self.setStyleSheet(background-color: BG)` ở `_build_ui` — bare property list trên widget chứa
  **toàn bộ màn hình**. Đây đúng là `BUG-008` ở quy mô lớn nhất có thể trên một màn. Nay scoped
  `SettingsView { ... }`.
- Dải header (`BG_CARD_HEADER` + border-bottom + bo góc trên) — không scoped thì màu và viền của
  nó đổ xuống icon, title, subtitle và nút Save nằm trong nó. Nay scoped bằng
  `#settingsCardHeader`. Giữ tay viết, **không** cấp `StyleRole`: một dải header có bo góc trên
  riêng hiện là hình dạng của **một** màn, và header của `Card` bên Engine là hình dạng khác
  (một label + hàng action).

**Diff pixel: 16.096 / 1.600.000 (1,0%)**, bbox `286,21 → 616,668` — đúng cột nhãn + vùng tiêu đề,
không lan ra ngoài. Chênh lệch là nhãn field 12px → 13px và tiêu đề 14px → 13px, đúng phần gộp
token đã nêu ở bảng trên.

**Kiểm tra:** Engine `1267 passed` (1262 + 5 test mới), `mypy` sạch 343 file. Elite: `ruff` sạch,
`mypy` giữ baseline, full suite `1809 passed, 4 skipped, 0 failed`.

### Settings: 4 chỗ `setStyleSheet` còn lại — cố ý dừng, không phải bỏ sót

Cả 4 đều là **widget lá** (không có con), nên **không** mang rủi ro cascade `BUG-008`, và đều đã
dùng token `Palette` nên guard `find_inline_stylesheets` vẫn 0. Chúng là "chưa lên role", không
phải "sai":

| Chỗ | Còn gì | Cần gì để đóng |
| :--- | :--- | :--- |
| `_apply_status()` | `color: DANGER/SUCCESS` đổi theo runtime | Đúng ca `semantic_colour()` sinh ra để phục vụ — màu chọn theo *instance*, không theo *role*. `apply_role` không diễn đạt được. |
| status label | `font-size: 11px` | Gộp được vào `CAPTION` nếu chấp nhận đổi màu sang `muted` |
| warning label | `ACCENT` + 11px | Cần role mới. Đo được 5 chỗ `ACCENT` + 11px nhưng **4 trong số đó bold** và chỗ này không — hai hình dạng khác nhau, chưa đủ rõ để chốt một role |
| reveal button + `QSpinBox` | chrome kiểu field | `StyledField` là `QLineEdit`; `QSpinBox` chỉ có **1** consumer trong toàn app |

## Màn 2 — Dashboard (Dev Board), 2026-08-25

`_SectionLabel(QHBoxLayout)` → `SectionLabel(tick=True)` của Engine (4 call site);
3 × `QFrame` + `_card_style()` → `Panel`; `setStyleSheet` gốc của `DevBoardPanel` được scoped.

**Guard giảm lần đầu trong `007F`: 17 → 16.** `DevBoardPanel` nhận `# base-exempt` chứ **không**
kế thừa `Panel`: nó vẽ nền app (`Palette.BG`), không viền — là **vùng các card nằm lên**, không
phải card. Cho nó kế thừa `Panel` sẽ thành `BG_CARD` + viền, tức card thứ tư bọc quanh ba card
kia. Trần `_BARE_QT_BASE_CEILING` hạ theo, kèm lý do ngay tại chỗ.

`Panel` **tự sở hữu layout của nó** (`body_layout`) — không lắp được layout thứ hai lên widget,
Qt từ chối và nội dung mất cha. Ba chỗ chuyển đổi đều phải đi qua `body_layout`, không phải
`QVBoxLayout(card)`. Ghi lại vì đây là cái bẫy sẽ gặp lại ở Backtest và Data Management.

### `BUG-008` lộ ra lần ba — và lần này nó **thêm** chrome chứ không phải đổi cỡ chữ

Trước/sau khác nhau rõ ở hai chỗ: mỗi dòng chỉ báo (`RSI (14)`, `EMA 20`, ...) và mỗi nhãn
`Market:`/`Symbol:`/`Strategy:` **mất cái khung viền bao quanh**.

Không phải regression. Đã **đo bằng repro tối giản**, không phỏng đoán: dựng một `QFrame` con
khai báo đúng `QFrame { background-color: transparent; border-radius: 6px; }` bên trong một
`QFrame` cha mang QSS **không selector** (`background-color: BG_CARD; border: 1px solid ...`),
rồi lấy pixel ngay mép trên của frame con — ra `(17, 19, 24)` = `#111318` = đúng `BG_CARD` của
cha. Nói cách khác **QSS không-selector của cha đè lên chính chữ `transparent` mà widget con tự
khai báo**. Đổi cha sang dạng scoped thì frame con không còn bị chạm tới.

Nên cái khung quanh mỗi dòng chỉ báo **chưa bao giờ là ý đồ của code** — code viết rõ
`transparent` + hover highlight. Nó là chrome do `BUG-008` âm thầm thêm vào. Sau bước này widget
hiển thị đúng thứ nó khai báo.

⚠️ **Đây là thay đổi thị giác thấy rõ trên một màn đang chạy** (khác với bước 1 của Settings, chỉ
là cỡ chữ lệch ~2px). Bảng chỉ báo giờ phẳng hơn, không còn khung từng dòng. Giữ nguyên vì khôi
phục khung nghĩa là **viết styling mới chưa từng tồn tại**, không phải khôi phục thứ đã có. Cần
user xem lại và quyết nếu muốn khung đó thật.

**Kiểm tra:** `ruff` sạch, `mypy` sạch, guard hex vẫn 0, guard bare-base 17 → 16, full suite
`1809 passed, 4 skipped, 0 failed`.

### Dashboard còn lại

`_field_style()` (4 chỗ: 3 combo + 2 date field), nhãn `_field_row`, tiêu đề header + tick riêng
của nó, badge WS, nút action (`_action_button_style`), `_ws_dot`, scroll area. Cùng loại với phần
còn lại của Settings: phần lớn là widget lá, cần role mới ở Engine (`ACCENT` + bold + 11px cho
nhãn field; chrome `QComboBox`) mà hình dạng chưa đủ rõ để chốt.

**Backtest, Data Management:** chưa bắt đầu — đây là phần nặng nhất (33+27+16 và 31+65
`setStyleSheet`) và là nơi 15 finding guard còn lại nằm.
