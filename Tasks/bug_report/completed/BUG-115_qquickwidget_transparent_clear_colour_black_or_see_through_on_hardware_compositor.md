# BUG-115 — Mọi `QQuickWidget` nhúng trong QtWidgets dựa vào `setClearColor(transparent)` để "lộ nền cha" — chỉ đúng trên đường vẽ phần mềm; trên màn hình thật (Linux) vùng trong suốt thành **đen** (X11) hoặc **xuyên thấu** (Wayland)

**Reported date:** 2026-09-09
**Severity:** 🟠 P2 — không crash, không sai dữ liệu, nhưng thân của **mọi** modal QML
(`TimeframePicker`, `SymbolPicker`, `TimezonePicker`, `StrategyPicker`, `Capital`, `KlineInspector`,
`MetricsDetail`, …) và **mọi** widget QML nhúng inline (bảng Database Status, hàng stat card
Backtest, ProgressBanner, StatusPill, Positions/OpenOrders) hiển thị sai nền trên Ubuntu — user mô
tả là "glitch, không hiển thị đúng", còn trên Windows thì trông ổn.
**Status:** ✅ Đã sửa 2026-09-10 — root-caused, tái hiện trên X11 thật (Xvfb), sửa bằng `BOT-132`
(`QuickSurface`) + `TASK-042` bên Engine, đo lại trên màn hình thật: xem §6.
**Found by:** user báo ("trên Windows UI hiển thị tốt, trên Ubuntu bị glitch, nghĩ là do cơ chế
bridge nào đó không đúng"). Trực giác "bridge" là đúng: lỗi nằm ở cầu nối QtWidgets ↔ QML, cụ thể
là một giả định của **mọi** host `QQuickWidget` trong app, không phải ở một widget nào.

---

## 1. Hiện tượng (Symptom)

Tái hiện trong sandbox này bằng phiên X11 thật (`xvfb-run` + `QT_QPA_PLATFORM=xcb`, Mesa
llvmpipe, PySide6 6.11.1 đúng bản pin trong `requirements.txt`, engine cài từ GitHub), chụp
**những gì thực sự ra màn hình** (`QScreen.grabWindow`) và đối chiếu với **ảnh render nội bộ**
(`QWidget.grab()` — chính là đường mà mọi test render của repo nhìn thấy):

| Màn / widget | Điểm lấy mẫu (vùng QML "trong suốt") | Ra màn hình thật | `widget.grab()` |
| :--- | :--- | :---: | :---: |
| Modal `TimeframePickerDialog` (QmlOverlay thật, `open_dialog()`) | giữa thân QML `(280,260)` | `#000000` | `#111318` |
| Backtest — `StatCardRowWidget` | khe giữa 2 stat card `(370,230)` | `#000000` | `#111318` |
| Data Management — `DatabaseStatusPanel` | thân bảng dưới 2 dòng dữ liệu `(300,450)` | `#000000` | `#111318` |

`#111318` là `Palette.BG_CARD` — màu `StyleRole.SURFACE` mà panel/dialog cha đã vẽ. Ảnh chụp
(cùng thư mục `BUG-115_assets/`):

- `timeframe_picker_xcb_screen.png` — thân modal đen tuyền (đúng dialog user chụp ở `BUG-102`,
  lần này là trên X11 nên ra **đen** thay vì **xuyên thấu**).
- `timeframe_picker_widget_grab.png` — cùng dialog, cùng lúc, qua `grab()`: nền đúng. **Đây là lý
  do mọi test render của repo đều xanh trong khi user nhìn thấy lỗi.**
- `backtest_xcb_screen.png` — vạch đen giữa các stat card.
- `data_management_xcb_screen.png` — thân bảng Database Status đen thay vì `BG_CARD`.

Pixel-diff `grab()` ↔ màn hình trên màn Data Management: **24,12 %** số điểm ảnh khác nhau
(276 891 / 1 148 000), toàn bộ nằm đúng trong hình chữ nhật của `QQuickWidget`; màn Dashboard và
Settings (không có `QQuickWidget` nào trong khung nhìn) diff = 0.

Trên **Wayland** (môi trường thật của user — log `Qt platform=wayland | DPR=2` trong `BUG-110`),
cùng cơ chế cho ra triệu chứng **xuyên thấu** thay vì đen (xem §2.3) — chính là ảnh user gửi ở
`BUG-102`.

## 2. Root cause

### 2.1 Giả định chung của 10 host

Cả 10 host `QQuickWidget` sản xuất đều đặt:

```python
self._quick.setClearColor(Qt.GlobalColor.transparent)
# "Transparent so `Overlay`'s own SURFACE styling shows behind the QML body"
```

- `src/presentation/ui/qml/host.py:75` (`QmlOverlay` — thân của 10 dialog kế thừa)
- `src/presentation/ui/qml/SymbolPicker/symbol_picker_modal_host.py:116`
- `src/presentation/ui/qml/MetricsDetailPanel/metrics_detail_modal_host.py:135`
- `src/presentation/ui/qml/StatCardRow/stat_card_row_widget.py:72`
- `src/presentation/ui/qml/kit/progress_banner_widget.py:77`
- `src/presentation/ui/qml/kit/status_pill_widget.py:81`
- `src/presentation/ui/qml/PositionsTable/positions_panel.py:50`
- `src/presentation/ui/qml/OpenOrdersTable/open_orders_panel.py:52`
- `src/presentation/ui/screens/data_management/data_management_widgets/database_status_panel.py:73`
- `src/presentation/ui/components/chart_card/chart_toolbar.py:164`

Giả định: *"vùng QML không vẽ gì thì nền QtWidgets phía sau lộ ra"*. Giả định này **chỉ đúng trên
đường vẽ phần mềm** của `QQuickWidget`.

### 2.2 Hai đường vẽ của `QQuickWidget` (Qt 6.11, `qtdeclarative/src/quickwidgets/qquickwidget.cpp`)

| Đường | Khi nào | `QQuickWidget` vẽ thế nào | Vùng trong suốt ra sao |
| :--- | :--- | :--- | :--- |
| **Software** | scene graph là `QSGRendererInterface::Software` (`QT_QUICK_BACKEND=software`), `offscreen`, và **mọi `QWidget.grab()`/`render()`** | `paintEvent()` dùng `QPainter.drawImage(softwareImage)` **đè lên** backing store mà cha đã vẽ nền | lộ nền cha — đúng như giả định |
| **Texture (RHI)** | **mọi phiên desktop thật** (xcb, wayland, windows) với OpenGL/D3D11/… | widget là *render-to-texture widget*; texture được compositor ghép sau | **không** có nền cha phía sau (xem 2.3) |

### 2.3 Trên đường texture, Qt "đục lỗ" backing store và đổ màu clear của compositor vào

`qtbase/src/widgets/kernel/qwidget.cpp` 6.11, `QWidgetPrivate::drawWidget()` (dòng 5624–5631):

```cpp
if (renderToTexture) {
    // This widget renders into a texture which is composed later. We just need to
    // punch a hole in the backingstore, so the texture will be visible.
    beginBackingStorePainting();
    if (!q->testAttribute(Qt::WA_AlwaysStackOnTop) && repaintManager) {
        QPainter p(q);
        p.setCompositionMode(QPainter::CompositionMode_Source);
        p.fillRect(q->rect(), Qt::transparent);
```

→ hình chữ nhật của `QQuickWidget` trong backing store bị **xoá thành trong suốt** — nền SURFACE
mà `Overlay`/`Panel` đã vẽ ở đó **bị xoá đi**, bất kể `WA_StyledBackground` hay stylesheet nào.

`qtbase/src/gui/painting/qbackingstoredefaultcompositor.cpp` 6.11, `flush()`:

```cpp
QColor clearColor = translucentBackground ? Qt::transparent : Qt::black;
cb->beginPass(target, clearColor, ...);
// 1. renderToTexture widgets (không StacksOnTop): vẽ bằng m_psNoBlend  ← texture QML, KHÔNG blend
// 2. backing store (đã bị đục lỗ): vẽ blend lên trên                     ← lỗ trong suốt, không thêm gì
// 3. StacksOnTop textures
```

và `qwidgetrepaintmanager.cpp:1071`:

```cpp
const bool translucentBackground = widget->testAttribute(Qt::WA_TranslucentBackground);
```

Ghép lại: texel QML trong suốt được ghi **không blend** lên target vừa clear → điểm ảnh cuối cùng
là `(0,0,0,0)`:

- **X11 (cửa sổ không alpha):** hiện **đen** — đúng bảng §1.
- **Wayland (surface có alpha):** hiện **xuyên thấu** xuống cửa sổ/màn hình chính phía sau — đúng
  ảnh user gửi ở `BUG-102` ("chữ màn hình chính đè lên grid").

Tài liệu Qt của chính `QQuickWidget::setClearColor` nói thẳng điều kiện: *"To get a semi-transparent
QQuickWidget, call this function with color set to Qt::transparent, **set the
Qt::WA_TranslucentBackground widget attribute on the top-level window**, and request an alpha
channel via setFormat()."* App chưa từng làm 2 việc sau — và cũng không nên: `WA_TranslucentBackground`
trên toàn bộ dialog/cửa sổ chính là làm **cả cửa sổ** trong suốt (đo ở §3: trên Xvfb không có
compositor, cả cửa sổ thành đen kể cả phần QtWidgets).

### 2.4 Thí nghiệm cô lập (bằng chứng cơ chế, không phải suy luận)

`BUG-115_assets/quickwidget_transparency_probe.py`: một `QWidget` nền `#111318` chứa một
`QQuickWidget` vẽ đúng 1 ô đỏ, còn lại trống. Lấy mẫu điểm (100,100) — vùng QML trống:

| `MODE` | Nền tảng / backend | Màn hình thật | `grab()` |
| :--- | :--- | :---: | :---: |
| `transparent` (app hiện tại) | xcb / RHI OpenGL | **`#000000`** | `#111318` |
| `transparent` | xcb / `QT_QUICK_BACKEND=software` | `#111318` | `#111318` |
| `transparent` | `offscreen` (tầng test của repo) | `#111318` | `#111318` |
| `opaque` — `setClearColor(#111318)` | xcb / RHI | `#111318` | `#111318` |
| `qmlbg` — root QML tự vẽ `Rectangle` `#111318` | xcb / RHI | `#111318` | `#111318` |
| `translucent` — thêm `WA_TranslucentBackground` cho top-level (công thức của tài liệu Qt) | xcb / RHI | `#000000` **cả cửa sổ** | `#000000` |

Ba dòng đầu giải thích vì sao **toàn bộ tầng test (offscreen) và mọi `grab()` đều xanh** trong khi
màn hình thật sai: repo chưa có tầng nào chạy đường texture.

### 2.5 Vì sao `BUG-102` "đã sửa" mà user vẫn thấy lỗi

`BUG-102` (2026-09-03, cùng ảnh user trên Wayland) kết luận root cause là `Overlay` thiếu
`WA_StyledBackground` nên nền SURFACE "chưa từng vẽ". Cờ đó đúng và cần thiết cho **phần chrome**
(tiêu đề, nút) của dialog, nhưng **không thể** chạm tới vùng thân QML: §2.3 cho thấy backing store ở
đúng vùng đó bị đục lỗ **sau khi** cha vẽ, nên cha có vẽ nền hay không cũng không lộ ra. Regression
test của `BUG-102` chỉ assert cờ được set — không tái hiện được triệu chứng — và hồ sơ đó cũng tự ghi
"user nên tự mở lại app thật để xác nhận". Bảng §1 là kết quả xác nhận đó: **chưa hết**.

### 2.6 Vì sao Windows "trông ổn" — **chưa xác minh**

Sandbox này không có Windows. Mã compositor ở §2.3 không rẽ nhánh theo nền tảng, nên về nguyên tắc
Windows cũng phải ra đen — nếu Windows thực sự đúng thì máy đó đang đi một đường khác (ví dụ scene
graph rơi về software adaptation, hoặc driver/RHI D3D11 xử lý alpha của swapchain khác đi). Không
cần chốt câu hỏi này để sửa: cơ chế đúng là **không dựa vào clear màu trong suốt** trên bất kỳ
nền tảng nào (§4) — khi đó cả hai đường vẽ cho cùng một kết quả, và Windows/Linux/test/offscreen
đồng nhất. Khi sửa xong, cần user xác nhận trên chính máy Ubuntu Wayland của mình (§5).

## 3. Phạm vi ảnh hưởng

Mọi nơi đi qua 10 host ở §2.1 — tức toàn bộ phần QML của app:

- 10 dialog kế thừa `QmlOverlay` (`TimeframePickerDialog`, `TimeRangePickerDialog`,
  `MarketPickerDialog`, `IndicatorPickerDialog`, `TimezonePickerDialog`, `CapitalDialogWidget`,
  `StrategyPickerDialog`, `LimitationsDialog`, `OrderExecutionDialog`, `KlineInspectorDialogWidget`)
  + `SymbolPickerModal` + `MetricsDetailModal`: thân modal đen/xuyên thấu — với các picker dùng
  `SelectList`/`CheckboxList`/`TimeRangePicker` phần lớn diện tích thân là "trong suốt", nên đây là
  nơi lỗi lộ rõ nhất và là thứ user đã chụp ở `BUG-102`.
- Inline: `DatabaseStatusPanel`, `StatCardRowWidget`, `ProgressBannerWidget`, `StatusPillWidget`,
  `PositionsPanel`, `OpenOrdersPanel`, `ChartToolbar`.

## 4. Thiết kế sửa — bản đã rà lại (2026-09-10), thay cho bản nháp đầu

### 4.1 Vì sao bản nháp đầu ("một helper đặt clear colour đục, 10 host gọi") vẫn là hot fix

Bản nháp đầu của hồ sơ này đề xuất một hàm `configure_embedded_quick(quick, surface_token)`
mà 10 host gọi thay cho 3 dòng tự viết. User yêu cầu rà lại. Kết quả rà: nó **vẫn là vá**, vì ba lý do
đo được trong code, không phải cảm tính:

1. **Nó giữ nguyên 10 host tự dựng `QQuickWidget` bằng tay** và chỉ thêm *một việc nữa* mỗi host
   phải nhớ gọi. Đường lây của chính bug này là copy-paste 3 dòng kèm comment *"same reasoning as
   `QmlOverlay`"* sang 9 file — không có gì ép một host thứ 11 gọi helper. Cùng vector lây, cùng
   kết cục.
2. **Nó chép sự thật "host này ngồi trên `SURFACE`" ra lần thứ hai** dưới dạng chuỗi token
   `"bgCard"` truyền tay, trong khi cha đã khai báo đúng sự thật đó bằng
   `apply_role(self, StyleRole.SURFACE)`. Hai nơi giữ một sự thật, không gì ép khớp — đúng hình
   dạng `BUG-064`.
3. **Cầu nối QtWidgets ↔ QML đã tồn tại trong Engine — `create_quick_widget()`**
   (`pyside_mvc/runtime/qml_host_view.py`: pin style Basic, `Theme` context, icon provider, import
   path `Sagittarius.UI`; docstring của nó nói thẳng *"Factored out so every path configures
   identically instead of hand-rolling a partial copy"*). App **bỏ qua nó ở cả 17 chỗ** (10 host
   sản xuất + 7 `preview.py`), mỗi chỗ một bản chép thiếu: `EPIC-006F` gỡ `configure_app_qml()`
   khỏi bootstrap vì "không còn QML nào", rồi `EPIC-015` đưa QML trở lại mà không khôi phục — nên
   mỗi host tự set `Theme` bằng tay (comment trong `database_status_panel.py` mô tả đúng lỗ hổng
   này). Helper của bản nháp đầu sẽ là bản chép thiếu **thứ 18**.

Kết luận rà: lỗi `BUG-115` chỉ là **một thuộc tính sai của một quy ước** ("nhúng QML = 3 dòng +
comment", lặp ở mỗi host). Sửa đúng là biến quy ước đó thành **một abstraction**, để thuộc tính đó
(và mọi thuộc tính khác của việc nhúng) chỉ tồn tại ở **một** nơi. Đây là *hard design* theo nghĩa
`ONBOARDING.md` §7 — "hiện tại đang chạy" không phải lý do giữ.

### 4.2 As-is (hình `BUG-115_assets/design_as_is.puml`)

- `QQuickWidget` được **dựng tay ở 17 chỗ**, **kế thừa ở 4 chỗ** (`ChartToolbar`,
  `ProgressBannerWidget`, `StatusPillWidget`, `StatCardRowWidget`), **compose ở 6 chỗ** (`QmlOverlay`,
  `SymbolPickerModal`, `MetricsDetailModal`, `DatabaseStatusPanel`, `PositionsPanel`,
  `OpenOrdersPanel`).
- Mỗi chỗ lặp lại cùng hợp đồng nhúng, không nơi nào là nguồn sự thật: pin style (`qml/style.py` —
  chính nó đã là bản chép của `runtime/qml_style.py` bên Engine), `Theme` context, giữ context
  object sống, nạp `.qml` + fail to, `root_object`, resize mode, **và clear colour trong suốt**.
- Không guard nào chặn một `QQuickWidget` mới dựng tay.

### 4.3 To-be (hình `BUG-115_assets/design_to_be.puml`)

```
src/presentation/ui/qml/embed/                  ← tầng "cầu nối", một abstraction / một file
  quick_surface.py     QuickSurface(QWidget)     nơi DUY NHẤT trong app tạo ra một QQuickWidget
  size_policy.py       QuickSizePolicy(Enum)     FILL (SizeRootObjectToView) | HUG (SizeViewToRootObject)
  tests/               hợp đồng của QuickSurface (offscreen, không cần màn hình)
```

`QuickSurface(qml_file, *, surface: StyleRole, context: Mapping[str, QObject], size_policy=FILL,
object_name)` — **compose**, không kế thừa `QQuickWidget`:

| Trách nhiệm | Ai làm | Ghi chú |
| :--- | :--- | :--- |
| Dựng `QQuickWidget`, pin Basic, `Theme`, icon provider, import path | **Engine** `create_quick_widget()` | bootstrap gọi lại `configure_app_qml(...)` (1 dòng `EPIC-006F` đã gỡ); app **không** chép plumbing này nữa; `qml/style.py` của app (bản chép `ensure_qml_style`) bị xoá |
| **Nền của scene QML** | `QuickSurface`, từ `surface: StyleRole` | clear colour **đục**, đọc **cùng** token mà `apply_role(role)` vẽ nền cha — qua một hàm mới `background_token(role)` tách ra từ `_build_qss()` trong `kit/style.py`. Hai "hoạ sĩ" (QSS cha, clear colour con) đọc **một** mapping; không còn chuỗi màu truyền tay |
| Giữ context object sống, `setContextProperty` | `QuickSurface` | hợp đồng `qml-rule.md` §1.1 |
| Nạp `.qml`, **raise** khi lỗi, `root_object` | `QuickSurface` | hợp đồng `qml-rule.md` §7 |
| Resize | `QuickSurface` theo `QuickSizePolicy`; `sizeHint()` chuyển tiếp khi `HUG` | `ChartToolbar` là host duy nhất cần `HUG` |

Bất biến mới, ghi vào `qml-rule.md` §0: **"Một scene QML nhúng luôn đục, và nền của nó là token
của `StyleRole` mà nó được nhúng vào — đúng luật của một child `QWidget` nằm trên `QFrame`."** Hệ
quả có chủ đích: không nhúng QML lên một surface có nền động (hover/selected); `background_token()`
raise với role không có nền tĩnh, nên vi phạm lộ lúc dựng, không lúc render.

10 host sau khi migrate: 6 host compose giữ hình dạng, thay `self._quick = QQuickWidget()` + 12
dòng bằng `self._surface = QuickSurface(...)`; 4 host kế thừa `QQuickWidget` đổi thành kế thừa
`QuickSurface` (API công khai của cả 4 là setter/signal, không phải API `QQuickWidget`, nên caller
không đổi). 7 `preview.py` đi cùng đường, nên preview khớp sản xuất.

### 4.4 Guard — cơ chế, không phải kỷ luật review

1. `tests/unit/presentation/ui/qml/test_quick_widget_only_in_embed.py` — grep `src/presentation/ui/**`:
   `QQuickWidget(` và `(QQuickWidget)` chỉ được xuất hiện trong `qml/embed/`. **Đỏ hôm nay ở 17 chỗ**;
   xanh khi migrate xong. Cùng khuôn `test_qml_style_discipline.py` (guard hex literal).
2. Hợp đồng `QuickSurface` (unit, offscreen): clear colour có alpha 255 **và** bằng
   `background_token(surface)`; raise khi `.qml` lỗi; giữ context; `HUG` chuyển tiếp `sizeHint`.
   Đây là regression test cấp cơ chế của `BUG-115`: đỏ đúng lý do (alpha 0) trước, xanh sau.
3. **Tầng Desktop** (`ci-rule.md` §3, opt-in, cần phiên cửa sổ thật; trên Linux không có
   `DISPLAY` thì dùng `xvfb-run` nếu có, không thì báo rõ không chạy — không skip im lặng): nhúng một
   `QuickSurface` nhỏ nhất, assert `QScreen.grabWindow` == `widget.grab()` tại điểm trong vùng QML
   trống. Đây là test **duy nhất** nhìn thấy được đường texture — thứ đã bỏ lọt cả `BUG-102` lẫn
   `BUG-115`. Đỏ hôm nay (`#000000` vs `#111318`), xanh sau.

### 4.5 Thứ tự làm — mỗi bước xanh gate trước khi sang bước sau

| Bước | Việc | Rủi ro |
| :--- | :--- | :--- |
| S1 | bootstrap gọi lại `configure_app_qml`; thêm `embed/` + 3 guard ở §4.4 (guard 1 và 3 đỏ, đúng ý) | thấp |
| S2 | migrate `QmlOverlay` (kéo theo 10 dialog) → xác minh lại bảng §1 dòng 1 trên Xvfb | thấp — 1 file, 10 người dùng |
| S3 | migrate 5 host compose còn lại | thấp |
| S4 | migrate 4 host kế thừa (`ChartToolbar` cuối, vì `HUG`) | trung bình — sizing header `ChartCard` |
| S5 | migrate 11 `preview.py`; guard 1 xanh; xoá `qml/style.py` (app) | thấp |
| S6 | `qml-rule.md` §0/§1 ghi `QuickSurface` là hình dạng host duy nhất; phụ lục `BUG-102`: fix đó
      đúng cho chrome nhưng không chạm thân QML, `BUG-115` đóng nốt | — |

Blast radius đo được: 9 file test/src chạm `._quick` (5 dòng ngoài chính các host), 21 file test
dùng `root_object` — `QuickSurface` giữ nguyên tên `root_object`, nên 21 file đó không đổi.

### 4.6 Phương án đã cân nhắc và loại

- **(a) Mỗi `.qml` tự vẽ `Rectangle { color: Theme.bgCard }` ở root** — chạy được (dòng `qmlbg`
  §2.4) nhưng lặp ở ~15 file `.qml`, đúng bệnh "mỗi widget tự tô nền" repo dính hai lần
  (`qml-rule.md` §3); và vẫn để 17 chỗ dựng tay `QQuickWidget` nguyên đó.
- **(b) `WA_TranslucentBackground` cho top-level theo tài liệu Qt** — làm cả cửa sổ trong suốt, phụ
  thuộc compositor; đo được là tệ hơn (dòng `translucent` §2.4).
- **(c) Helper đặt clear colour, 10 host tự gọi** — bản nháp đầu, loại theo §4.1.
- **(d) Sửa trong Engine ngay** (đưa nền-theo-role vào `create_quick_widget()`/`QmlHostView`) — đúng
  hướng dài hạn: `QmlHostView` bên Engine mang **cùng lỗi tiềm ẩn** (clear colour mặc định của Qt là
  **trắng đục**, một route QML nguyên màn trên nền app sẽ lộ viền trắng — chưa lộ vì app chưa có route
  QML nào). Nhưng `StyleRole` là vocabulary của app, Engine không biết; và đây là 2 repo, 2 commit
  (`ONBOARDING.md` §2). Chọn: làm trong app trước (§4.3), **ghi TASK bên Engine** để đưa "embedded
  surface + nền đục theo token" lên framework khi `QuickSurface` đã chạy ổn — không làm trong hồ sơ này.

### 4.7 Cần user quyết trước khi code

1. Duyệt thiết kế §4.3–§4.5 (theo `ONBOARDING.md` §12.5 mục 3: design trước, code sau).
2. Xác nhận phạm vi: chỉ app (`Sagittarius_Elite_Warrior`), Engine để TASK sau — hay muốn làm
   Engine ngay (§4.6.d).

## 5. Xác minh sau khi sửa

- Chạy lại quy trình §1 trong sandbox (`xvfb-run -a -s "-screen 0 1600x1000x24"` + `QT_QPA_PLATFORM=xcb`).
- Chạy `scripts/quick_surface_desktop_probe.py` (tầng Desktop, `ci-rule.md` §3).
- **User mở app thật trên Ubuntu Wayland (DPR 2)** và mở `TimeframePicker`/`SymbolPicker`/màn Data
  Management — cả ba phải có nền đặc. Đây là bước `BUG-102` đã yêu cầu nhưng chưa từng làm; xem §6.4.

---

## 6. Đã sửa (2026-09-10)

### 6.1 Sửa gì

Đúng thiết kế §4, hai repo hai commit riêng (`ONBOARDING.md` §2):

| Repo | Thay đổi |
| :--- | :--- |
| `Sagittarius_Engine` | `TASK-042` (repo `Sagittarius_Engine`)  — `runtime/quick_background.py`: `DEFAULT_BACKGROUND`/`resolve_opaque_background()`; `create_quick_widget(background="bg")` clear **đục** theo token, từ chối token không đục/không phải màu. Rule `ui-architecture.md` §4 + `CHANGELOG` `[Unreleased]`. |
| `Sagittarius_Elite_Warrior` | [`BOT-132`](../../completed/BOT-132_quick_surface_tang_nhung_qml_duy_nhat.md) — `kit/style.py::background_token(role)` (và `_build_qss()` đọc **cùng** bảng đó, nên một nguồn duy nhất); `qml/embed/{quick_surface,size_policy}.py`; `theme_bootstrap.py::seed_app_theme()` gom việc mồi theme của bootstrapper + 6 script; **cả 10 host + 11 preview** đi qua `QuickSurface`; xoá `qml/style.py` (bản chép `ensure_qml_style` của Engine). |

### 6.2 Bằng chứng trên màn hình thật — cùng 3 điểm mẫu §1, cùng lệnh, sau khi sửa

| Màn / widget | Điểm lấy mẫu | Trước | Sau |
| :--- | :--- | :---: | :---: |
| Modal `TimeframePickerDialog` | `(280,260)` | `#000000` | **`#111318`** |
| Backtest — `StatCardRowWidget` | `(370,230)` | `#000000` | **`#111318`** |
| Data Management — `DatabaseStatusPanel` | `(300,450)` | `#000000` | **`#111318`** |

Pixel-diff `grab()` ↔ màn hình thật, cùng cách đo §1:

| Màn | Trước | Sau |
| :--- | :---: | :---: |
| Data Management | 24,12 % (276 891 / 1 148 000) | **0,00 %** |
| Backtest | có lệch | **0,00 %** |
| Giao dịch | có lệch | **0,00 %** |

Ảnh sau khi sửa, cạnh ảnh trước, trong `BUG-115_assets/`:
`timeframe_picker_xcb_screen_after_fix.png`, `data_management_xcb_screen_after_fix.png`,
`backtest_xcb_screen_after_fix.png`.

### 6.3 Test giữ lại vĩnh viễn (`fix-bug-rule.md` §4)

| Tầng | File | Khoá điều gì |
| :--- | :--- | :--- |
| Guard | `tests/unit/presentation/ui/qml/test_quick_widget_only_in_embed.py` | không ai được dựng/kế thừa `QQuickWidget` hay gọi `setClearColor(` ngoài `qml/embed/` — **đỏ ở 17 chỗ trước khi migrate**, xanh sau |
| Hợp đồng | `tests/unit/presentation/ui/qml/embed/test_quick_surface.py` (9 test) | clear colour **đục** và **bằng** `background_token(surface)`; role không có nền tĩnh bị từ chối lúc dựng; context sống; `.qml` hỏng thì raise; `FILL`/`HUG` |
| Engine | `tests/extensions/pyside_mvc/test_quick_background.py` (8 test) | token không đục / không phải màu / không tồn tại đều bị từ chối |
| Desktop | `scripts/quick_surface_desktop_probe.py` | **tầng duy nhất nhìn thấy đường texture** — so pixel màn hình thật với `grab()`; từ chối chạy dưới `offscreen` |

Tầng Desktop là câu trả lời cho câu hỏi *"vì sao cả `BUG-102` lẫn `BUG-115` lọt qua một tầng test
xanh"*: cho tới nay repo **chưa có** tầng nào chạy đường texture.

### 6.4 Việc user cần làm để đóng hoàn toàn

Sandbox này chỉ có X11 ảo (Xvfb), không có Wayland và không có DPR 2 như máy user. Cơ chế đã đo
đúng trên đường texture thật, nhưng **user nên mở app thật trên Ubuntu** (`scripts/run-ui.ps1`
hoặc tương đương), mở `TimeframePicker`, `SymbolPicker` và màn Data Management, xác nhận nền đặc.
Nếu đúng, không còn việc gì; nếu còn sai, ảnh chụp mới sẽ chỉ ra host nào lọt.
