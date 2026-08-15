# Nhiệm vụ: Panel co giãn theo nội dung — cắt vòng lặp "nâng magic number"

> Thuộc Epic [`BOT-086`](BOT-086_ui_layout_and_overlay_architecture_epic.md), **Track B**,
> task 1/2. Nguồn: 📄 [`BUG-004`](../bug_report/BUG-004.md) — user hỏi thẳng
> *"Do we need dynamic layout mechanism?"*. **Câu trả lời: có.**

## 1. Vấn đề — container phớt lờ chiều cao nội dung tự khai

Đo thật ([`backtest_view.py`](../../src/presentation/ui/screens/backtest/backtest_view.py)):

```
window 1920px -> top_widget 1900px, implicitHeight=200, height=190   ← bị ép
window 1400px -> top_widget 1380px, implicitHeight=200, height=190
window 1100px -> top_widget 1080px, implicitHeight=200, height=190
```

Chính QML khai **cần 200px**, `setFixedHeight(_TOP_PANEL_HEIGHT)` ép xuống **190px**.

Và đây là lần thứ **hai**. Comment ngay trong file thừa nhận con số này **đã từng bị nâng
120 → 190** vì [`BOT-055`](../completed/BOT-055_backtest_performance_metrics_panel.md) bị
cắt mất hàng value/badge của stat card:

> *"120 (BOT-022's original budget, sized for a single plain result-text line, before
> BOT-055's real stat cards existed) clipped the cards' value/badge row off entirely."*

→ Mỗi lần thêm nội dung, lại nâng số tay. **Task này tồn tại để cắt đúng vòng lặp đó**,
không phải để nâng 190 → 200.

Kèm theo: `implicitWidth` của QML root là hằng số khai cứng `1200`, **không phải** chiều
rộng nội dung thật → toolbar tràn ngang ("CHẠY BACKT…" bị cắt ở rìa phải trong ảnh
`BUG-004`) mà container không hề nhận được tín hiệu nào.

## 2. Các bước thực hiện

### 2.1. Chiều cao theo nội dung

- [x] Bỏ `setFixedHeight(_TOP_PANEL_HEIGHT)` + hằng số `_TOP_PANEL_HEIGHT`. Thay bằng
      chiều cao lấy từ `rootObject().implicitHeight` của chính QML (có sẵn, đang bị bỏ
      qua — probe đo được `200.0`).
- [x] `implicitHeight` phải **thật sự động**: hiện QML root khai `implicitHeight: 200`
      cứng. Phải để nó chảy lên từ `ColumnLayout` con (`implicitHeight` của layout +
      margins), nếu không thì chỉ là đổi một magic number ở QML thay vì ở Python.
- [x] Cập nhật lại khi nội dung đổi (hiện/ẩn hàng cảnh báo `BOT-079`, panel stat card
      xuất hiện sau lần chạy đầu) — nối `implicitHeightChanged` chứ không đọc 1 lần lúc
      khởi tạo.

### 2.2. Chiều rộng — chống tràn ngang

- [x] Bỏ `implicitWidth: 1200` khai cứng ở QML root, để nó phản ánh chiều rộng nội dung
      thật.
- [x] Toolbar phải xử lý được khi hẹp: chốt cách lúc code (`Flickable` cuộn ngang, hoặc
      cho nhóm control xuống dòng, hoặc thu gọn nhãn). ⚠️ **Không cho phép cắt cụt im
      lặng như hiện tại** — nút "Chạy Backtest" bị cắt là mất chức năng, không phải xấu.

### 2.3. Test

- [x] Test tái hiện bug trước khi sửa: dựng panel với nội dung thật (4 stat card + hàng
      cảnh báo), assert chiều cao widget **>= `implicitHeight` của QML** — hiện tại sẽ
      **fail** (190 < 200), đúng như phải thế.
- [x] Test ở nhiều chiều rộng cửa sổ (vd 1920/1400/1100) xác nhận không control nào bị
      cắt cụt.

## 3. Rủi ro / Lưu ý

- ⚠️ **Tuyệt đối không "sửa" bằng cách nâng 190 → 200.** Đó là lần vá thứ ba của cùng một
  lỗi, và sẽ hỏng lại ngay khi ai đó thêm 1 dòng vào panel. Nếu hướng động bế tắc →
  **dừng, hỏi user**, đừng vá tạm rồi đóng task.
- Panel cao lên sẽ **lấy chỗ của chart** (cùng nằm trong `QVBoxLayout`). Cần xác nhận
  chart vẫn đủ cao dùng được ở cửa sổ nhỏ — có thể phải cho panel một trần tương đối
  (vd % chiều cao cửa sổ) thay vì cao vô hạn. Trần theo tỉ lệ ≠ magic number pixel.
- **Không đụng `MetricCard.qml`** trừ khi bắt buộc — user vừa tự sửa file này (commit
  `8c72eaa`).
- Task này **không** sửa được modal bị cắt (`extendedMetricsPopup` 606px) — đó là Track A
  (`BOT-087`/`BOT-088`), cơ chế hoàn toàn khác. Đừng gộp.

## 4. Phụ thuộc

- Không phụ thuộc task nào — làm được ngay, không đụng `sagittarius_engine/`.
- Là nền cho [`BOT-090`](BOT-090_trade_logs_visible_rows.md) (Trade Logs cần biết chiều
  cao thật khả dụng mới tính được số dòng/trang).

## 5. Kết quả triển khai thực tế

- **`backtest_view.py`**: bỏ hẳn `_TOP_PANEL_HEIGHT`. `load_qml()` gọi
  `_bind_top_panel_height()` (mới) — đọc `contentColumn.implicitHeight` (không phải
  `root.implicitHeight`, xem ghi chú quan trọng bên dưới), gọi `setFixedHeight()` với giá
  trị đó, và nối `root.implicitHeightChanged` để tự cập nhật mỗi khi nội dung đổi.
- **`BackTestTopPanel.qml`**: `implicitHeight: contentColumn.implicitHeight + panelMargin*2`
  ở root (không còn hardcode 200); `implicitWidth: 1200` bỏ hẳn. Toolbar bọc trong
  `ScrollView` ngang khi cửa sổ hẹp.
- ⚠️ **2 bug thật phát sinh trong lúc code, cả 2 đã sửa và verify bằng ảnh chụp UI thật
  (không chỉ test offscreen)**:
  1. **`ensurePolished()` gọi sai item.** `ensurePolished()` chỉ ép polish cho đúng item
     được gọi trên nó, không lan xuống con — gọi trên `root` (Rectangle, không có polish
     job) là vô tác dụng; phải gọi trên `contentColumn` (chính `ColumnLayout` có pending
     polish job thật). Bug này khiến `implicitHeight` đọc được giá trị **trễ đúng 1 lần
     đổi** — chỉ lộ ra khi chạy chung với ~75 test UI khác trong cùng 1 session (tự chạy
     riêng thì trùng hợp luôn pass). Sửa bằng `qtbot.waitUntil()` thay vì tin 1 lần
     `processEvents()`.
  2. **"ROW 2" (stat card / kết quả thô) dùng `Layout.fillHeight: true`.** Đây mới là bug
     THẬT gây ra ảnh chụp gốc của `BUG-004` (card bị cắt ngang) — `fillHeight` chỉ phân
     phối chỗ trống ĐÃ CÓ, không tự báo nhu cầu chiều cao lên `contentColumn`, nên toàn bộ
     hàng này (cả stat card lẫn hộp text kết quả) bị `contentColumn.implicitHeight` bỏ
     qua hoàn toàn. Sửa: `Item` bọc ngoài giờ khai `implicitHeight` tường minh theo đúng
     trạng thái đang hiện (`statCardsRow.implicitHeight` hoặc `resultColumn.implicitHeight`).
     Xác nhận bằng **mutation test thật** (khôi phục lại `fillHeight`, đo toạ độ tuyệt đối
     của card qua `mapToItem()`: card render đúng 80px nhưng lệch xuống dưới đáy widget
     68px — khớp chính xác kiểu lỗi trong ảnh chụp gốc).
- **Thanh cuộn ngang của toolbar**: `ScrollBar.horizontal.policy: AsNeeded` (lựa chọn tự
  nhiên đầu tiên) **không đủ** — đọc thẳng `Basic/ScrollBar.qml` xác nhận `contentItem`
  của nó là `opacity: 0.0` mặc định, chỉ lên `0.75` khi `policy === AlwaysOn` hoặc đang
  hover/kéo. Với `AsNeeded`, thanh cuộn tồn tại về mặt chức năng (kéo được) nhưng **vô
  hình cho tới khi user tình cờ rê chuột đúng vị trí** — không giải quyết đúng "discoverability"
  mà `BUG-004` yêu cầu. Sửa: `policy` chuyển thẳng `AlwaysOn`/`AlwaysOff` theo điều kiện
  tràn, xác nhận bằng ảnh chụp thật (không phải suy đoán từ tài liệu).
- **Trần chiều cao** (rủi ro đã nêu ở §3): **không cần** — `primaryStatCards` luôn đúng 4
  card cố định (`build_primary_stat_cards()`, không phụ thuộc dữ liệu), nên panel bị chặn
  tự nhiên, không có ca nào tăng vô hạn.
- **Test**: 3 test mới (`test_backtest_view_layout.py`) — bất biến chính (`height ==
  root.implicitHeight`), card không bị cắt (đo toạ độ tuyệt đối qua `mapToItem`, không
  phải `card.y` cục bộ — cạm bẫy y hệt bug #2 ở trên khi viết test), và dòng cảnh báo
  `BOT-079` vẫn đúng ý đồ gốc "không tốn thêm chiều cao". Cả 3 verify bằng mutation test
  (tái hiện đúng bug gốc → test đỏ → khôi phục → xanh lại) trước khi tin. 825 test toàn
  `tests/unit/`+`tests/sanity/` pass, `ruff` sạch, chạy ổn định qua nhiều lần lặp lại kể
  cả khi kết hợp với suite Backtest presenter đầy đủ.
