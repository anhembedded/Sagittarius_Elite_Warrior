# BUG-104 — Zoom vào rất sâu: trục Y của nến (candle) đứng hình trong khi volume vẫn tự co giãn, gây lệch tỉ lệ giữa 2 khu vực chart

**Reported date:** 2026-09-03
**Severity:** 🟡 **P3** — không mất dữ liệu, không crash; chart vẫn hiển thị được nhưng trục Y nến
sai (đóng băng ở biên độ toàn bộ lịch sử) khi user zoom vào rất sâu, gây cảm giác "candle không
zoom nữa, nhưng volume thì có" đúng như user mô tả kèm ảnh chụp Dev Board.

**Status:** ✅ **Đã sửa (2026-09-03)**

---

## 1. Hiện tượng (Symptom)

User zoom vào rất sâu trên chart Dev Board (nút `H+` nhiều lần liên tiếp): trục Y của khu vực nến
(candlestick) ngừng phản hồi zoom — biên độ giữ nguyên ở mức toàn bộ lịch sử đã tải — trong khi
trục Y của khu vực volume ngay bên dưới vẫn tiếp tục co giãn theo từng lần zoom, tạo cảm giác 2
khu vực "sai tỉ lệ" so với nhau dù cùng chia sẻ một trục X.

Tái hiện bằng probe script thật (`ChartCard` thật, 2000 nến 1 phút tổng hợp, click nút `H+` 40
lần liên tiếp và log `main_y`/`vol_y` mỗi bước) — xác nhận đúng: sau một số lần zoom, `main_y`
(biên độ trục Y của nến) đứng yên ở giá trị của toàn bộ lịch sử trong khi `vol_y` vẫn thay đổi
mỗi bước.

## 2. Nguyên nhân gốc rễ (Root cause)

`FastCandlestickItem.dataBounds(ax, orthoRange=...)` (`candlestick_item.py`) — hàm pyqtgraph gọi
để tự động co giãn trục Y theo đúng phần dữ liệu đang hiển thị trên trục X (`orthoRange`) — dùng
`visible_slice_indices()` để tìm cửa sổ nến nằm trong `orthoRange`, **nhưng gọi hàm này không có
tham số `padding`**, trong khi path vẽ thật (`_visible_history_slice()`, dùng để paint()) luôn áp
`padding = self.candle_width * self._VISIBLE_PADDING_WIDTHS`.

Ở mức zoom càng sâu, cửa sổ X (`orthoRange`) càng hẹp. Vì các nến cách đều nhau `candle_width`
đơn vị, tới một mức zoom đủ sâu, `orthoRange` có thể lọt hoàn toàn vào khoảng trống **giữa** 2 mốc
thời gian của 2 nến liền kề — khi đó lookup **không có padding** trả về khoảng rỗng (`lo == hi`),
trong khi lookup **có padding** (path vẽ) vẫn còn nến. Khoảng rỗng đó khiến `dataBounds()` rơi vào
nhánh fallback (biên độ toàn bộ lịch sử) thay vì biên độ đúng của các nến đang hiển thị. Một khi đã
rơi vào trạng thái này, mọi lần zoom sâu hơn tiếp theo cũng là một cửa sổ hẹp hơn nữa (vẫn rỗng) —
nên trục Y "đứng hình" vĩnh viễn ở biên độ toàn bộ lịch sử, đúng như log đo được.

`VolumeItem._apply()` (`volume_renderer.py`) không có lỗi này — nó đã áp padding từ trước — nên
volume vẫn tiếp tục co giãn đúng, tạo ra sự lệch pha quan sát được giữa 2 khu vực.

## 3. Cách khắc phục (Fix)

- `candlestick_item.py`: trong nhánh `ax == 1` (Y bounds) của `dataBounds()`, thêm đúng dòng
  `padding = self.candle_width * self._VISIBLE_PADDING_WIDTHS` trước khi gọi
  `visible_slice_indices(self.history_data, min_x, max_x, padding, key=lambda row: row[0])` —
  cùng công thức padding path vẽ đã dùng, để lookup cho Y-bounds và lookup cho render luôn đồng bộ
  ở mọi mức zoom.
- **Gộp chung** (theo yêu cầu của user — "tính năng zoom nên là chung ... gôm lại common đi"):
  thêm hằng số `DEFAULT_VISIBLE_PADDING_WIDTHS = 2.0` vào `viewport_windowing.py` (module đã là
  nơi dùng chung giữa các renderer), và đổi cả `FastCandlestickItem._VISIBLE_PADDING_WIDTHS` lẫn
  `volume_renderer._VISIBLE_PADDING_WIDTHS` sang import từ hằng số này thay vì mỗi file tự khai
  báo literal `2.0` riêng. Trước fix, `volume_renderer.py` còn ghi thẳng trong comment "mirrors
  FastCandlestickItem._VISIBLE_PADDING_WIDTHS" — tức đã biết 2 giá trị này phải giống nhau nhưng
  không có cơ chế nào đảm bảo, và đúng là 2 *cách dùng* (không phải giá trị) đã lệch nhau ở
  `dataBounds()`. Một nguồn chân lý duy nhất không tự ngăn lỗi *usage* tái diễn ở call site khác,
  nhưng loại bỏ khả năng lệch *giá trị* trong tương lai và làm rõ ràng ý định "2 chart này phải
  hành xử giống nhau".

## 4. Regression test

`tests/unit/presentation/ui/components/test_candlestick_item.py`:

- `test_data_bounds_stays_windowed_when_orthorange_falls_between_two_candles` — dựng 200 nến cách
  đều 60 đơn vị (`candle_width = 20`), gán nến đầu tiên biên độ rõ ràng khác biệt
  (`high=500.0, low=-500.0`) để một fallback sai là không thể nhầm lẫn, gọi
  `item.dataBounds(1, orthoRange=(t + 10, t + 30))` với `t` là mốc thời gian nến thứ 100 — cửa sổ
  20 đơn vị này nằm lọt giữa 2 nến (không trúng mốc thời gian nến nào) nhưng vẫn nằm trong biên độ
  padding (`candle_width * 2.0 = 40`) — assert kết quả đúng bằng biên độ cục bộ `(99.0, 101.0)`,
  không phải fallback `(-500.0, 500.0)`.
- `test_candlestick_and_volume_share_one_visible_padding_constant` — drift guard: assert cả
  `FastCandlestickItem._VISIBLE_PADDING_WIDTHS` và `volume_renderer._VISIBLE_PADDING_WIDTHS` đều
  bằng `DEFAULT_VISIBLE_PADDING_WIDTHS`.

Xác nhận đỏ trước fix bằng mutation test (revert dòng `padding = ...` trong `dataBounds()`):
`test_data_bounds_stays_windowed_when_orthorange_falls_between_two_candles` fail đúng như dự đoán
— `assert (-500.0, 500.0) == (99.0, 101.0)`. Xanh sau khi khôi phục fix — toàn bộ
`test_candlestick_item.py` + `test_chart_card.py` (84 test) pass.
