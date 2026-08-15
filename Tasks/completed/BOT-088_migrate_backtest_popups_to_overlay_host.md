# Nhiệm vụ: Chuyển 6 popup màn Backtest sang overlay host

> **Trạng thái:** 🟢 Hoàn tất — Cả 6 popups/dialogs đã được chuyển sang `BackTestModals.qml` được host bởi `OverlayHost` full-window, không còn bị kẹp trong top widget 190px.

> Thuộc Epic [`BOT-086`](../backlog/BOT-086_ui_layout_and_overlay_architecture_epic.md), **Track A**,
> task 2/2. Phụ thuộc [`BOT-087`](BOT-087_overlay_host_engine.md).

## 1. Danh sách popup phải chuyển — đã liệt kê đủ, không phải "vài cái"

Tất cả đều khai báo trong
[`BackTestTopPanel.qml`](../../src/presentation/ui/screens/backtest/BackTestTopPanel.qml),
tức nằm trong `QQuickWidget` cao **190px**:

| Popup | Chiều cao thật | Vừa 190px? |
| :--- | :---: | :---: |
| `extendedMetricsPopup` (11 card, 2 cột) | **606px** | ❌ chỉ 31% |
| `limitationsPopup` (9 dòng text wrap) | ~410px | ❌ |
| [`BotParamsDialog`](../../src/presentation/ui/components/BotParamsDialog.qml) | form động theo strategy | ❌ khi nhiều param |
| `capitalPopup` | nhỏ | ⚠️ đo lại |
| [`IndicatorPickerMenu`](../../src/presentation/ui/components/IndicatorPickerMenu.qml) | theo số script | ⚠️ đo lại |
| [`OrderExecutionMenu`](../../src/presentation/ui/components/OrderExecutionMenu.qml) | 4 mục | ⚠️ đo lại |

- [ ] **Đo từng cái trước khi sửa** (dùng cơ chế test `BOT-087` §3.3 vừa mở ra), đừng
      đoán. 3 cái đánh ⚠️ có thể đang vừa — nếu vừa thì vẫn nên chuyển cho nhất quán,
      nhưng phải biết mình đang sửa bug hay đang phòng xa.

## 2. Các bước thực hiện

- [ ] Chuyển từng popup sang overlay host theo API `BOT-087` chốt. **Từng cái một, chạy
      tay kiểm tra sau mỗi cái** — không chuyển cả 6 rồi mới chạy.
- [ ] Giữ nguyên `objectName` của mọi popup và control bên trong → test hiện có
      (`test_backtest_presenter.py`) không phải viết lại, và `BOT-083`'s quy ước
      "`Button` để test click được" vẫn giữ.
- [ ] Thêm test **đo chiều cao** cho ít nhất `extendedMetricsPopup` và `limitationsPopup`:
      modal phải vừa trong `Overlay.overlay` sau khi chuyển. Đây là test tái hiện đúng
      bug `BUG-004`, không phải chỉ test hành vi mong muốn.
- [ ] Chạy tay thật (không chỉ offscreen): mở từng modal, xác nhận **phủ lên `ChartCard`**
      và click ra ngoài đóng đúng.

## 3. Rủi ro / Lưu ý

- **Không nhân dịp đổi nội dung/thiết kế popup.** Task này chỉ đổi *chỗ popup sống*, không
  đổi *popup hiển thị gì*. Muốn giảm 11 card xuống cho gọn là quyết định UX riêng — hỏi
  user, task khác.
- `MetricCard.qml` vừa được user tự sửa layout (commit `8c72eaa`: `clip`, `elide`,
  `Layout.maximumWidth`, co `font.pixelSize`) để chống tràn. Sau khi popup hết bị kẹp
  190px, một phần các bản vá đó có thể **không còn cần** — nhưng **không tự ý revert**,
  hỏi user trước, vì chúng cũng có tác dụng phòng thủ độc lập.
- Nếu `BOT-087` phát hiện z-order với `ChartCard` không xử lý được → task này **dừng**,
  không tự chuyển sang phương án khác.

## 4. Phụ thuộc

- [`BOT-087`](BOT-087_overlay_host_engine.md) — bắt buộc xong trước.
- Chỉ sửa `Sagittarius_Elite_Warrior/src/` → commit submodule + bump pointer.
