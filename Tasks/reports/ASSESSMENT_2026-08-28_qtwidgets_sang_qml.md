# Đánh giá rủi ro — chuyển QtWidgets → QML

**Ngày:** 2026-08-28
**Người yêu cầu:** user — *"giúp tôi đánh giá, chuyển đổi từ từ QtWidget sang QML xem có
risk lắm không, tôi nhất quyết muốn chuyển"*
**Trạng thái:** đánh giá, chưa phải quyết định. Không có dòng code nào bị đổi bởi báo cáo này.

> Mọi con số dưới đây **đo bằng lệnh trên cây làm việc hôm nay**, không ước lượng. Lệnh đo
> ghi kèm để chạy lại được.

---

## 0. Kết luận ngắn

**Rủi ro tập trung vào đúng MỘT chỗ, và đó không phải chỗ ai cũng đoán.**

Không phải 20 nghìn dòng view. Không phải công sức viết lại. Mà là **chart** — 4.253 dòng
pyqtgraph, và repo này đã **thử đường QtQuick một lần, thất bại, và không ai phát hiện suốt 5
ngày** (`BUG-039`). Bản QtQuick đó nay đã bị xoá khỏi cây.

Phần còn lại rẻ hơn vẻ ngoài **rất nhiều**, vì một lý do ít ai để ý: **tầng ViewModel chưa
bao giờ rời QML.** Cả 4 ViewModel vẫn `class X(BaseQmlViewModel)`, vẫn gọi `from_qml()` —
trong đúng đoạn code tôi sửa hai ngày trước.

Con số quyết định: **chuyến về đắt gấp ~3,2 lần chuyến đi.** `EPIC-006` đổi 4.806 dòng QML
sống thành widget. Đổi ngược lại bây giờ là **~15.500 dòng** (chưa tính chart), vì tầng
widget đã mọc thêm một bộ kit 4.327 dòng mà bên QML không có bản tương đương.

---

## 1. Đo thật

```bash
# tầng presentation, chia theo vùng
for d in kit components screens state assets common; do
  find src/presentation/ui/$d -name "*.py" | wc -l
  cat $(find src/presentation/ui/$d -name "*.py") | wc -l
done
```

| Vùng | File | LOC | Số phận nếu chuyển QML |
| :--- | ---: | ---: | :--- |
| `screens/` — presenter, coordinator, logic, ports, view_model, signal wiring | 58 | **12.801** | ✅ **Không đụng tới** |
| `screens/` — widget view thật | 44 | 7.767 | 🔴 Viết lại |
| `components/` — không phải chart | ~26 | ~3.423 | 🔴 Viết lại |
| `components/chart_card/` — pyqtgraph | 26 | **4.253** | 🔴🔴 Xem §3.1 |
| `kit/` — `apply_role`, `StyleRole`, guard, `binding.py`, `widget_value.py` | 27 | 4.327 | 🔴 Viết lại |
| `state/` (`EPIC-010` ui_state) | 13 | 723 | ✅ Không đụng tới |
| `common/`, `assets/` (`Palette`) | 16 | 1.268 | ✅ Không đụng tới |

**Phải viết lại (chưa tính chart): ~15.517 dòng. Giữ nguyên: ~14.792 dòng.**

Test:

```bash
find tests -name "test_*.py" | wc -l                                    # 247
grep -rl "QtWidgets\|qapp\|qtbot\|QWidget\|QPushButton" tests | wc -l   # 110
grep -rl "findChild\|\.click()\|_btn_\|isVisible()\|setText(" tests | wc -l  # 47
cat $(find tests -path "*presentation*" -name "*.py") | wc -l           # 32.095
```

---

## 2. Điều làm nó RẺ hơn bạn nghĩ

### 2.1 ViewModel chưa bao giờ rời QML — đây là phát hiện lớn nhất

```
src/.../backtest/backtest_view_model.py:51      class BackTestViewModel(BaseQmlViewModel)
src/.../settings/settings_view_model.py:7       class SettingsViewModel(BaseQmlViewModel)
src/.../data_management/..._view_model.py:27    class DataManagementViewModel(BaseQmlViewModel)
src/.../dashboard/dashboard_view_model.py:39    class DashboardQmlViewModel(BaseQmlViewModel)
```

Một cái còn **tên là `Qml`**. `from_qml()` vẫn được gọi ở `backtest_view_model.py:1222/1228/1236`
— dòng 1236 là code `BUG-064` tôi thêm **hai ngày trước**.

`Property("QStringList", notify=...)`, `@Slot`, `Signal` — 2.460 dòng ViewModel này viết đúng
hình dạng QML cần và **chưa từng bị tháo ra**. `EPIC-006` chỉ thay tầng View; nó không chạm
ViewModel.

**Hệ quả:** đây là migration **một tầng**, không phải ba tầng. Presenter (4.157 dòng) nói
chuyện với ViewModel, không biết View là gì.

### 2.2 Đường băng QML bên Engine vẫn còn nguyên

`EPIC-006F` **không** tháo nó — sample app cần, nên nó ở lại:

```
sagittarius_engine/extensions/pyside_mvc/Sagittarius/UI/     1.860 dòng QML (kit)
sagittarius_engine/extensions/pyside_mvc/runtime/qml_host_view.py
sagittarius_engine/extensions/pyside_mvc/runtime/overlay_host.py
sagittarius_engine/extensions/pyside_mvc/runtime/qml_style.py
sagittarius_engine/extensions/pyside_mvc/runtime/base_view_model.py
```

`get_theme_bridge()` vẫn đang chạy trong production — `app_bootstrapper.py` gọi nó, và
`apply_role()` của kit widget đọc nó. Cầu theme QML→Python **vẫn sống**.

### 2.3 QML cũ lấy lại được từ git

`EPIC-006F` xoá 22 file `.qml` (4.978 dòng kể cả 2 test). Chúng nằm trong lịch sử, `git show`
là ra. Không phải viết lại từ số 0 cho những màn đó — nhưng **cẩn thận**: chúng là ảnh chụp
của tháng 8, còn app đã đi tiếp (`EPIC-010` ui_state, `EPIC-013` port tường minh, `EPIC-014`
picker dùng chung, `BUG-063/064`). Dùng làm **tham chiếu bố cục**, không phải để dán vào.

---

## 3. Bốn rủi ro, xếp theo mức độ

### 3.1 🔴🔴 CHART — đây là thứ có thể giết dự án chuyển đổi

4.253 dòng, 26 file, và **23 file trong `src/` import pyqtgraph**. pyqtgraph là
`QGraphicsView` — thuần QtWidgets. Nó **không** chạy trong QML scene graph.

Chỉ có hai đường, và repo này đã đi thử cả hai:

**(a) Nhúng qua `QQuickWidget`** — đây đúng là kiến trúc app từng có. `BUG-039` ghi lại kết
quả: từ `30ffa18` (18/08), chart native là mặc định *trên giấy tờ*, nhưng
`_emit_strategy_trend_zones()` bắn mỗi lần chạy và native không có ABI vẽ background region →
**mọi run đều raise và dựng lại host giữa chừng**. Suốt **5 ngày**, pixel trên màn hình luôn
là pyqtgraph. Native **chưa từng render một khung hình nào trong production** — và không ai
nhận ra.

Đó không phải một lỗi. Đó là bằng chứng rằng kiến trúc hai-pipeline này **hỏng mà không kêu**.

**(b) Viết lại trên QtQuick scene graph** — bản đó **đã bị xoá khỏi cây**:

```bash
find src -type d -name "native*" -o -name "*chart_renderer*"   # rỗng
ls .agents/rules/ | grep native                                # rỗng
```

Và lúc còn sống nó **thiếu cả ba**: grid, thân nến đúng, background region (ADR §7 của
`EPIC-005`). Đi đường này = viết lại renderer chart tài chính từ đầu, đúng component nặng nhất
của app.

**Đây là rủi ro không thể "làm từ từ" được.** Mọi thứ khác chuyển dần từng màn được; chart thì
không — nó là một quyết định nhị phân, và cả hai vế đều có vết thương trong repo này.

### 3.2 🔴 Test — 47 file assert thẳng vào ruột widget

`panel._btn_symbol.click()`, `view._symbol_picker._cards`, `toolbar._btn_more.width()` — chính
những test tôi vừa viết tuần này. Trong QML **không có cái nào trong số đó**. `QQuickItem`
không lộ ra Python theo kiểu ấy; bạn phải `findChild(QObject, objectName)` rồi
`QMetaObject.invokeMethod`, hoặc chuyển sang **QtQuickTest** — một runner riêng, ngôn ngữ
riêng, không nằm trong `pytest`, không vào được `--cov`, không chạy được trong
`ci-local.ps1` như hiện nay.

32.095 dòng test presentation. Không phải tất cả đều chết, nhưng **47 file chết chắc**, và cái
mất lớn hơn là **loại đảm bảo**: tuần này gate bắt được bốn lỗi thật của tôi
(`set_symbol_preferences` chưa khai trong port, `set_symbol_options` thiếu `@Slot`, nút `…`
rộng 13px, `_btn_more` kẹt sáng). Ba trong bốn cái đó **chỉ bắt được vì test chạm được vào
widget Python**.

### 3.3 🟡 Kit — 4.327 dòng không có bản QML tương đương

`apply_role()` + `StyleRole` (27 role), `guards.py` (cấm hex literal ngoài một file), `binding.py`,
`widget_value.py`. Kit QML bên Engine chỉ 1.860 dòng — **và `EPIC-005`'s ADR §3 ghi rõ Elite
chưa bao giờ dùng nó**, mỗi modal tự viết `Repeater`/`ListView` riêng. Nghĩa là con số 1.860
kia **không** trừ được vào 4.327.

Riêng `binding.py` là chuyện trớ trêu: nó tồn tại vì `BUG-064` — mất binding QML nên phải dựng
lại binding hai chiều trên Qt metaobject. **QML làm việc này miễn phí.** Đây là điểm cộng thật
cho phía bạn, xem §4.

### 3.4 🟡 Lỗi chỉ lộ lúc render

`EPIC-005`'s ADR §3, vẫn đúng nguyên: *"Lỗi QML chỉ lộ lúc render, không lúc biên dịch/type-check"*.
Cộng thêm `AppDataTable` từng bắn ~75 dòng `TypeError ... of null` ra stderr lúc first paint,
**bypass `qInstallMessageHandler`**.

Đối chiếu: hôm nay `mypy` gác 155 file và `ruff` gác toàn bộ `src`. QML nằm ngoài tầm cả hai.

---

## 4. Điều bạn đúng, mà chưa nói ra

Tôi sẽ không giả vờ đây là ý tưởng tồi. Có **hai lập luận thật** đứng về phía bạn, và cả hai
đều nằm trong tài liệu của chính repo này:

**(1) Lý do gốc chọn QML chưa bao giờ sai, và bạn vẫn đang làm đúng nó.**
`BOT-030` ghi: *"AI dịch mockup sang code trực tiếp hơn ở QML."* `EPIC-005`'s ADR §2 đo lại
bằng git log và **xác nhận còn đúng** — 15+ task mockup-driven. Và **hai tin nhắn trước bạn
gửi tôi một ảnh mock để tôi dựng lại.** Đó chính xác là workflow mà QML phục vụ. `EPIC-006`
không bác bỏ lập luận này — nó chỉ nói *chi phí migrate thấp hơn dự đoán 3 lần*, đó là câu trả
lời cho một câu hỏi khác.

**(2) `BUG-064` là hoá đơn của việc bỏ QML, và nó có thật.**
Dialog Strategy Properties không lưu giá trị nào, năm vòng sửa, và nguyên nhân gốc là binding
hai chiều mất khi QML đi. Tôi phải dựng lại bằng tay trên `QMetaObject.userProperty()`. Bên
QML: `text: viewModel.foo` — hết.

Nói thẳng: **bản năng của bạn có cơ sở.** Câu hỏi không phải "QML có giá trị không" mà là
"giá trị đó có bù nổi §3.1 không".

---

## 5. Có BA lựa chọn, không phải hai

| | Nội dung | Rủi ro chart | Chi phí |
| :--- | :--- | :--- | :--- |
| **A. QML toàn bộ** | Cả 4 màn + kit + chart | 🔴🔴 §3.1, không né được | ~15.5k + chart |
| **B. Lai** | QML cho màn nhận mockup (Backtest, Dashboard); QtWidgets giữ chart + màn form/bảng | 🟢 **Không đụng chart** | ~8–10k |
| **C. Ở lại** | Giữ widget, tiếp tục `EPIC-014` | 🟢 | 0 |

**B chính là kết luận của `EPIC-005`'s ADR §4**, viết ra sau khi đo git log thật. `EPIC-006` đảo
nó ngược lại, và lý do đảo được ghi rõ: *"một stack, một cách styling, một cách test — không
phải maintain song song 2 pipeline."*

Đó là một đánh đổi hợp lệ, **không phải một sự thật**. Nếu bạn thấy tốc độ dựng mockup quan
trọng hơn chi phí hai pipeline, B là đường mà tài liệu của chính repo này đã từng chọn — và nó
tránh được đúng cái rủi ro duy nhất có thể giết dự án.

**Nếu tôi phải khuyến nghị một cái: B.** Nó lấy được thứ bạn thật sự muốn (dựng mockup nhanh,
binding miễn phí, ở đúng hai màn nhận mockup) mà không chạm vào 4.253 dòng chart có tiền sử
hỏng-mà-không-kêu.

---

## 6. Nếu vẫn đi đường A — lộ trình và điều kiện dừng

Bạn đã nói rõ là quyết. Đây là cách đi ít rủi ro nhất, theo đúng khuôn `EPIC-005`/`EPIC-006`
đã dùng (nhánh riêng, rollback ~0, kill criteria chốt trước).

**Thứ tự bắt buộc — rủi ro tăng dần, mỗi bước tự rollback được:**

| Bước | Việc | Vì sao ở vị trí này |
| :--- | :--- | :--- |
| **0** | **Spike chart, 1 buổi, vứt đi được.** Nhúng `ChartCard` hiện tại vào một `QQuickWidget` bên trong một màn QML rỗng. Chạy một backtest thật, xác nhận có pixel và có background region. | §3.1 là rủi ro duy nhất giết được dự án. Trả lời nó **trước khi** tiêu một giờ nào cho 15.5k dòng kia. Nếu bước này đỏ → dừng, chuyển sang B. |
| **1** | Quyết chiến lược test, viết ra giấy. `objectName` + `findChild` trong pytest, hay QtQuickTest riêng? | Sai chỗ này thì phát hiện lúc đã viết xong 3 màn. |
| **2** | Dựng lại kit QML ở Engine cho ngang `apply_role`/`StyleRole` hiện tại | `EPIC-006B` phải xong trước C/D/E vì cùng lý do — không có base thật thì mỗi màn tự chế QSS inline, đúng cái đống lộn xộn `EPIC-005` để lại. |
| **3** | **Sidebar** (pilot) — always-on, nhỏ, lỗi lộ ngay | `EPIC-006C` chọn đúng file này làm pilot, vì lý do đó. |
| **4** | **Settings** — form thuần, không mockup mới, không chart | Màn rẻ nhất và độc lập nhất. |
| **5** | **Dev Board**, rồi **Backtest** | Hai màn nhận mockup — nơi QML trả lại giá trị nhiều nhất, làm sau cùng vì lớn nhất. |
| **6** | **Data Management** | Nặng bảng/form; giá trị QML thấp nhất. Cân nhắc để lại widget. |

**Điều kiện dừng — chốt bây giờ, không chốt lúc đang đau:**

- **Bước 0 không cho ra một khung hình chart thật trong một buổi → DỪNG, đi đường B.** Không
  thương lượng. `BUG-039` là 5 ngày chạy sai mà không ai biết; đừng mua lại nó.
- Bất kỳ bước nào vượt **3 lần** ước lượng ban đầu → dừng, đánh giá lại.
- Regression thị giác không sửa được trong buổi đó → rollback (nhánh riêng, chưa merge).
- Gate không giữ được baseline chụp ngay trước bước đó → dừng, sửa nguyên nhân, không merge lúc đỏ.
- **Mới, không có trong `EPIC-005/006`:** nếu số test bị mất (không port được sang QML) vượt
  **20 file** → dừng và đánh giá lại. Tuần này gate bắt 4 lỗi thật của tôi; mất khả năng đó là
  chi phí ẩn lớn nhất của A.

**Việc cần làm ngay trước bước 0:** cập nhật `.agents/rules/qml-rule.md` — nó đang mô tả thế
giới trước `EPIC-006` (bảo "QML là mặc định", trỏ tới chart QtQuick "permanent" nay đã bị xoá).
Agent nào đọc nó hôm nay cũng bị dẫn sai đường.

---

## 7. Thứ báo cáo này CỐ Ý không làm

Không quyết thay bạn. §5 nói rõ tôi nghiêng về B và vì sao, nhưng cả ba lựa chọn đều có lý lẽ
đứng được, và lựa chọn giữa chúng là đánh đổi về **tốc độ phát triển tính năng** — bạn nắm dữ
liệu đó, không phải tôi. Cái tôi khẳng định được là §3.1: rủi ro chart có thật, đo được, và có
tiền sử trong chính repo này.
