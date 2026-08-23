# EPIC-005D — Pilot: `SettingsScreen` — đo chi phí thật

**Thuộc Epic:** [`EPIC-005`](../README.md)
**Trạng thái:** 🔴 Chưa làm
**Phụ thuộc:** `EPIC-005A` (cổng chặn), `EPIC-005B` (cần token dùng được từ QtWidgets),
`EPIC-005C` (cần rule đã chốt)

---

## 0. Vì sao chọn `SettingsScreen`

`screens/settings/SettingsScreen.qml` — **1 file, 363 LOC**, nhỏ nhất trong các màn hình.
Đã có `settings_view.py` dạng `QWidget` làm shell sẵn.

**Cố tình không chọn Dashboard** (nó gánh `QQuickWidget` + `DevBoardPanel.qml`) và **không
chọn Backtest** (nó chứa chart — ranh giới cứng). Pilot phải đo được chi phí migrate *thuần*,
không lẫn chi phí gỡ chart.

## 1. Mục tiêu thật sự — đây là task đo lường, không phải task giao hàng

Câu hỏi cần trả lời chính xác:

> Một màn hình QtWidgets có đạt **parity thị giác** chỉ với `Palette` + QSS, **không cần**
> bộ kit QML (`BaseCard`, `StatefulButton`, `FieldBackground`, `StyledCheck`…), hay không?

Nếu câu trả lời là "không, phải viết lại N component" — thì **N chính là chi phí thật của cả
epic**, vì các màn hình sau dùng lại đúng những component đó.

## 2. Yêu cầu

1. Viết `SettingsScreen` bằng QtWidgets trong `settings_view.py` (hoặc module cạnh nó).
2. **Không xoá `SettingsScreen.qml`.** Chỉ ngừng nạp. Đây là điều khiến rollback chỉ là revert
   một commit.
3. **Ghi lại, trong lúc làm chứ không phải nhớ lại sau**:
   - Mỗi component kit QML phải thay thế → thay bằng gì (widget gốc? tự viết? bao nhiêu dòng?)
   - Chỗ nào QtWidgets **tốt hơn** thấy rõ (tab-order, focus, keyboard nav…)
   - Chỗ nào QtWidgets **tệ hơn** thấy rõ (layout, animation, styling…)
   - Thời gian thực tế bỏ ra
4. **So sánh thị giác**: chụp ảnh trước/sau. Repo đã có sẵn kỹ thuật render offscreen
   (`scripts/render_gallery_snapshot.py` bên engine) — tái dùng cách đó thay vì tự nghĩ cách mới.
5. Test: mọi test đang phủ màn hình settings phải xanh. Nếu màn hình này **chưa có test nào**
   — ghi lại như một phát hiện, và viết tối thiểu một smoke test, nếu không thì không có cơ sở
   nào để nói "không regression".

## 3. Điểm quyết định

Kết thúc task này là **điểm dừng chính thức của epic**. Trình cho user: chi phí đo được, ảnh
so sánh, danh sách component phải viết lại. User quyết đi tiếp `E`/`F` hay dừng.

Được phép dừng tại đây và giữ nguyên phần còn lại là QML. Pilot chỉ tốn 363 LOC — đó chính
là lý do chọn nó.

## 4. Xác minh

Gate phải giữ đúng baseline **tự chụp ngay trước khi sửa dòng đầu tiên** — con số trong
README epic đã trôi một lần trong đúng ngày viết nó, đừng dùng lại. So
bằng log file, không bằng console.
