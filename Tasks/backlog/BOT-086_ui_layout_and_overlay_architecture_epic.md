# Epic: Kiến trúc Layout & Overlay của UI — hết vá pixel bằng tay

> Nguồn: 📄 [`BUG-004`](../bug_report/BUG-004.md) — user báo *"Extension window not so full,
> layout not optimize"* kèm câu hỏi thẳng: ***"Do we need dynamic layout mechanism?"***
>
> Đánh giá của user: *"UI mechanical, philosophy chưa tốt, chứ không phải riêng 1 view nào"*
> — **đã verify là đúng**, và đo được cơ chế cụ thể (xem §2). Đây **không phải bug của một
> màn hình nào**, mà là hệ quả của 2 quyết định kiến trúc đang thiếu.
>
> 🤝 **HANDOFF (15/08)**: Track B (`BOT-089`/`BOT-090`) đã xong. **Track A
> (`BOT-087`/`BOT-088`) chưa bắt đầu** — chuyển cho một AI session khác vì phiên trước hết
> hạn mức. Đọc [`.agents/ONBOARDING.md`](../../.agents/ONBOARDING.md) trước, rồi bắt đầu từ
> `BOT-087` §2 (đã có probe khả thi thật, không phải lý thuyết).

## 1. Hai vấn đề **trực giao** — cần cả hai, không thay thế nhau

Sai lầm dễ mắc khi đọc `BUG-004`: tưởng chỉ có 1 vấn đề "layout xấu". Thực tế là 2, và
**sửa cái này không tự sửa cái kia**:

| Triệu chứng trong ảnh `BUG-004` | Track A (Overlay) | Track B (Dynamic layout) |
| :--- | :---: | :---: |
| Modal "Chỉ số chi tiết" 606px bị cắt còn 190px | ✅ sửa | ❌ |
| Trade Logs hiện `75 Lệnh · Trang 1/4` nhưng **bảng trống** | ❌ | ✅ sửa |
| `_TOP_PANEL_HEIGHT = 190` hardcode (QML tự khai `implicitHeight = 200`) | ❌ | ✅ sửa |
| Toolbar bị cắt ngang ở rìa phải ("CHẠY BACKT…") | ❌ | ✅ sửa |

Kể cả khi panel co giãn đúng theo nội dung (~150px cho 4 stat card), modal 606px **vẫn**
phải thoát ra khỏi widget cha. Ngược lại, có overlay host rồi thì Trade Logs **vẫn** 0
dòng. → **2 track song song, không phụ thuộc nhau.**

## 2. Bằng chứng đo được (không suy đoán)

Đo bằng chính `create_quick_widget()` của repo, `QT_QPA_PLATFORM=offscreen`:

### 2.1. `Overlay.overlay` bị giam trong `QQuickWidget`, không phải cửa sổ

```
host QWidget window : 1400x900
QQuickWidget        : 1378x190      ← backtest_view.py: setFixedHeight(_TOP_PANEL_HEIGHT)
Overlay.overlay     : 1378x190      ← KHÔNG phải 1400x900
```

Mọi `Popup` QML mặc định coi `Overlay.overlay` là toàn cửa sổ. Ở màn Backtest nó chỉ bằng
đúng widget con 190px. **6 popup** đều khai báo trong `BackTestTopPanel.qml` (tức nằm
trong 190px đó): `extendedMetricsPopup`, `limitationsPopup`, `capitalPopup`,
[`BotParamsDialog`](../../src/presentation/ui/components/BotParamsDialog.qml),
[`IndicatorPickerMenu`](../../src/presentation/ui/components/IndicatorPickerMenu.qml),
[`OrderExecutionMenu`](../../src/presentation/ui/components/OrderExecutionMenu.qml).

Chiều cao thật của `extendedMetricsPopup`: 11 card ÷ 2 cột = 6 hàng × 80px + spacing +
padding = **606px trong 190px → chỉ 31% hiển thị**. Khớp chính xác ảnh chụp (thấy header
+ ~2 hàng, "AVG TRADE" bị cắt ngang).

**Vì sao lọt lâu tới giờ**: Settings/Database dùng `QmlHostView` (1 `QQuickWidget` full
màn) → overlay = toàn màn → popup chạy đúng. Chỉ Backtest tách 3 widget (vì chart phải
giữ QtWidgets — quyết định từ [`BOT-030`](../completed/BOT-030_full_qml_migration.md)) nên
mới lộ. **Cạm bẫy nằm ở mô hình hosting, không ở view nào.**

### 2.2. Container phớt lờ chiều cao nội dung tự khai

```
window 1920px -> top_widget 1900px, implicitHeight=200, height=190  ← bị ép
window 1400px -> top_widget 1380px, implicitHeight=200, height=190
window 1100px -> top_widget 1080px, implicitHeight=200, height=190
```

Chính QML nói nó cần **200px**, `setFixedHeight(190)` ép xuống 190. Và comment trong
[`backtest_view.py`](../../src/presentation/ui/screens/backtest/backtest_view.py) ghi rõ
con số này **đã từng bị nâng 120 → 190** vì `BOT-055` bị cắt card — tức **cùng một lớp
lỗi, lần trước vá bằng cách tăng magic number**, và giờ lại thiếu 10px nữa.

Trade Logs: `PAGE_SIZE = 20` × `implicitHeight: 44` = **880px** chỉ riêng phần rows, trong
khi `setSizes([600, 200])` cho pane này **200px** → 0 dòng hiển thị, đúng như ảnh.

`implicitWidth` của QML root là hằng số khai cứng `1200`, không phải chiều rộng nội dung
thật → toolbar tràn ngang mà không có tín hiệu nào báo lên container.

## 3. Hướng đã chốt với user: **B — overlay host full-window** (cho Track A)

User đã chốt hướng B sau khi cân nhắc 3 phương án:

| | Nội dung | Vì sao **không** chọn |
| :--- | :--- | :--- |
| A | Modal lớn chuyển sang `QDialog` QtWidgets | Phá vỡ "toàn bộ UI là QML" của `BOT-030`; 2 hệ style song song |
| **B** | **1 `QQuickWidget` trong suốt phủ toàn cửa sổ, mọi modal reparent vào đó** | **✅ đã chốt** |
| C | Popup tự kẹp `height` + `ScrollView` bên trong | Vá triệu chứng — modal 606px cuộn trong 190px vẫn tệ về UX |

Ảnh tham chiếu `image-3.png` user đưa (modal chiếm ~55% chiều cao cửa sổ, căn giữa toàn
màn) xác nhận đích nhắm là A/B, không phải C.

### 3.1. Hướng B **đã verify khả thi**, không phải lý thuyết

Probe thật (`QQuickWidget` trong suốt, `WA_AlwaysStackOnTop`, `setClearColor(transparent)`,
`WA_TransparentForMouseEvents` khi rảnh):

```
overlay QQuickWidget : 1400x900   ← full window
Overlay.overlay      : 1400x900   ← không còn 190
606px modal fits?    : YES
click-through idle   : YES        ← click xuyên xuống widget bên dưới khi không có modal
after resize         : 1000x600   ← geometry bám theo cửa sổ
```

→ Không có rào cản kỹ thuật nào chặn hướng B. Rủi ro còn lại là **chi tiết triển khai**
(bàn giao input khi mở/đóng modal, z-order với `ChartCard` QtWidgets), không phải khả thi
hay không.

## 4. Bảng task con

| Task | Track | Tên | Phụ thuộc |
| :--- | :---: | :--- | :--- |
| [`BOT-087`](BOT-087_overlay_host_engine.md) | A | `OverlayHost` — hạ tầng overlay full-window ở `pyside_mvc` | — |
| [`BOT-088`](BOT-088_migrate_backtest_popups_to_overlay_host.md) | A | Chuyển 6 popup màn Backtest sang overlay host | `BOT-087` |
| [`BOT-089`](BOT-089_content_driven_panel_sizing.md) | B | Panel co giãn theo nội dung — bỏ `setFixedHeight`/magic number | — |
| [`BOT-090`](BOT-090_trade_logs_visible_rows.md) | B | Trade Logs hiển thị đủ dòng (rows-per-page theo chiều cao thật) | `BOT-089` |

**Thứ tự đề xuất**: `BOT-089` → `BOT-090` (Track B, rẻ hơn, không đụng engine, thấy kết
quả ngay) **song song** `BOT-087` → `BOT-088` (Track A, đụng engine, tốn hơn). Nếu phải
chọn 1 track trước: **Track B**, vì Trade Logs 0 dòng là mất tính năng hoàn toàn, còn
modal bị cắt vẫn còn đọc được một phần.

## 5. Rủi ro / Lưu ý

- **`BOT-087` sửa `sagittarius_engine/` (repo cha)** → commit ở **cả hai repo** + bump
  submodule pointer, giống `BOT-066`…`BOT-071`.
- **Cám dỗ cần đề phòng — đừng biến thành refactor toàn UI.** Epic này chỉ đóng đúng 2 lỗ
  kiến trúc đo được ở §2. Không nhân dịp đổi theme, không đổi mockup, không "dọn dẹp" QML
  không liên quan.
- **Không tự ý nâng magic number thêm lần nữa** (190 → 200 → …). Đó chính là cái vòng lặp
  task này tồn tại để cắt. Nếu `BOT-089` bế tắc, dừng lại hỏi user chứ đừng vá tạm.
- Sanity test hiện **không phủ được nội dung `Popup`** — giới hạn harness đã ghi từ
  [`BOT-047`](../completed/BOT-047_dynamic_params_form_ui.md) (*"Popup content không test
  được qua `find_qml_item`"*). `BOT-087` nên đóng luôn gap này (đo `Overlay.overlay` được
  từ Python, như probe đã làm), nếu không thì mọi test popup sau vẫn chỉ verify được
  "bấm không crash" — đúng lỗ hổng đã để lọt `BOT-081`.

## 6. Nợ tự nhận — không đổ cho người khác

`extendedMetricsPopup` **đã tràn sẵn từ [`BOT-055`](../completed/BOT-055_backtest_performance_metrics_panel.md)**
(8 card = 422px > 190px). Nhưng các task gần đây làm nó **tệ hơn** mà không ai đo:

- [`BOT-079`](../completed/BOT-079_fee_transparency_and_trade_frequency.md) thêm "Total Fees Paid" (8 → 9 card)
- [`BOT-080`](../completed/BOT-080_out_of_sample_walk_forward.md) thêm 2 card in/out-of-sample (9 → 11 card)
- → **422px → 606px**, tức tràn thêm 184px
- [`BOT-081`](../completed/BOT-081_backtest_limitation_disclosure.md) tạo `limitationsPopup` mới (~410px) **trong đúng panel 190px đó**, test chỉ verify "bấm nút không crash"

Ghi lại để lần sau **bất kỳ ai thêm card/popup vào panel có chiều cao cố định đều phải đo
trước**, và để `BOT-087` hiểu vì sao việc test được `Overlay.overlay` từ Python là bắt
buộc chứ không phải "nice to have".
