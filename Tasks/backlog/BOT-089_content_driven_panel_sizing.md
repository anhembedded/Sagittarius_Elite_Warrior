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

- [ ] Bỏ `setFixedHeight(_TOP_PANEL_HEIGHT)` + hằng số `_TOP_PANEL_HEIGHT`. Thay bằng
      chiều cao lấy từ `rootObject().implicitHeight` của chính QML (có sẵn, đang bị bỏ
      qua — probe đo được `200.0`).
- [ ] `implicitHeight` phải **thật sự động**: hiện QML root khai `implicitHeight: 200`
      cứng. Phải để nó chảy lên từ `ColumnLayout` con (`implicitHeight` của layout +
      margins), nếu không thì chỉ là đổi một magic number ở QML thay vì ở Python.
- [ ] Cập nhật lại khi nội dung đổi (hiện/ẩn hàng cảnh báo `BOT-079`, panel stat card
      xuất hiện sau lần chạy đầu) — nối `implicitHeightChanged` chứ không đọc 1 lần lúc
      khởi tạo.

### 2.2. Chiều rộng — chống tràn ngang

- [ ] Bỏ `implicitWidth: 1200` khai cứng ở QML root, để nó phản ánh chiều rộng nội dung
      thật.
- [ ] Toolbar phải xử lý được khi hẹp: chốt cách lúc code (`Flickable` cuộn ngang, hoặc
      cho nhóm control xuống dòng, hoặc thu gọn nhãn). ⚠️ **Không cho phép cắt cụt im
      lặng như hiện tại** — nút "Chạy Backtest" bị cắt là mất chức năng, không phải xấu.

### 2.3. Test

- [ ] Test tái hiện bug trước khi sửa: dựng panel với nội dung thật (4 stat card + hàng
      cảnh báo), assert chiều cao widget **>= `implicitHeight` của QML** — hiện tại sẽ
      **fail** (190 < 200), đúng như phải thế.
- [ ] Test ở nhiều chiều rộng cửa sổ (vd 1920/1400/1100) xác nhận không control nào bị
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
