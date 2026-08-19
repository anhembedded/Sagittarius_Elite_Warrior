# Nhiệm vụ: BOT-042C — `Series` ô tạm tách khỏi lịch sử đã chốt

> Thuộc Epic [`BOT-042`](BOT-042_tick_level_strategy_engine_support.md).
> Phụ thuộc [`BOT-042A`](BOT-042A_provisional_commit_design.md) (design phải
> được duyệt trước). Không phụ thuộc [`BOT-042B`](BOT-042B_indicator_provisional_contract.md)
> — 2 task này làm song song được.

## 1. Mục tiêu

Thêm khái niệm "giá trị tạm của bar đang hình thành" vào
[`Series`](../../src/domain/scripting/series.py), tách biệt khỏi lịch sử đã
chốt (`_values`), để `crossed_above`/`crossed_below`/`is_above`/`is_below`
đọc đúng "bar đang sống" ở offset `[0]` mà **không** cần sửa 4 hàm đó — thiết
kế đã chốt ở `BOT-042A` chứng minh việc này tự động đúng nếu shift offset
đúng cách khi có provisional.

Chi tiết thiết kế: xem [`Docs/Diagrams/tick_provisional_commit_design.md`](../../Docs/Diagrams/tick_provisional_commit_design.md)
§2-3 (đã duyệt ở `BOT-042A`).

## 2. Các bước thực hiện

- [ ] Thêm sentinel riêng (không phải `None`, vì `None` là giá trị hợp lệ
      cho 1 bar "chưa có giá trị") để phân biệt "chưa có tick nào trong bar
      này" với "tick báo giá trị `None` có chủ đích".
- [ ] `poke_provisional(value: float | None) -> float | None`: ghi đè ô tạm.
      Gọi nhiều lần trong cùng 1 bar chỉ ghi đè, **không** đẩy slot mới vào
      `self._values`.
- [ ] `push(value)`: xoá ô tạm (reset về sentinel) rồi mới ghi vĩnh viễn như
      hiện tại — **hành vi ghi vĩnh viễn giữ nguyên 100%**.
- [ ] `__getitem__(offset)`: khi có ô tạm active, `offset=0` đọc ô tạm,
      `offset=1` đọc `self._values[0]` (bar đã chốt gần nhất — TRƯỚC đây là
      offset 0), `offset=2` đọc `self._values[1]`, v.v. (shift lên 1 khi có
      provisional). Khi không có ô tạm, giữ nguyên hành vi hiện tại.
- [ ] `current`/`previous` property: tự động đúng vì chỉ gọi `self[0]`/
      `self[1]` — không cần sửa riêng.

## 3. Guard test bắt buộc (viết trước khi coi là xong)

- [ ] Gọi `poke_provisional()` nhiều lần với giá trị khác nhau trong "1 bar
      giả lập", rồi `push()` — kiểm tra: trong lúc chưa `push()`, độ dài
      lịch sử (`len(series)`) **không đổi**; sau `push()`, đúng 1 slot mới
      xuất hiện, không phải N slot (N = số lần `poke_provisional` đã gọi).
- [ ] `crossed_above`/`crossed_below` với 1 series có provisional active:
      dựng kịch bản 2 tick trong cùng 1 bar mà giá trị tạm dao động qua lại
      2 phía của 1 ngưỡng — phải **không** báo cross giả (vì `[1]` luôn là
      bar đã chốt, không đổi giữa 2 tick đó). Đây là bất biến quan trọng
      nhất của cả `BOT-042`.
- [ ] Toàn bộ test hiện có của `Series`/`crossed_above`/`crossed_below`/
      `is_above`/`is_below` phải xanh **không sửa 1 dòng nào** — bao gồm
      `test_missing_history_reads_as_none_rather_than_raising` và
      `test_no_cross_reported_while_either_side_is_warming_up`
      (`tests/unit/domain/scripting/test_series.py`), 2 test đang chứng minh
      "đọc quá lịch sử hiện có trả `None`, không raise" — **giữ đúng bất
      biến đó với offset đã shift**.
- [ ] **Test mới, riêng cho ca "tick đầu tiên của cả run"**: gọi
      `poke_provisional(value)` khi `Series` còn hoàn toàn rỗng (`len() ==
      0`, chưa từng `push()` lần nào) — `series[0]` phải trả đúng giá trị
      tạm, `series[1]` phải trả `None` (không raise `IndexError`), và
      `crossed_above()`/`crossed_below()` gọi ở trạng thái này phải trả
      `False`, không exception. Đây chính là ca "nến đầu tiên chưa có nến
      trước đó" — cơ chế nền (`__getitem__` trả `None` khi
      `index >= len(self._values)`) đã có sẵn từ trước `BOT-042`, task này
      chỉ phải **không phá nó** khi thêm offset shift, nhưng cần test tường
      minh vì diagram thiết kế (`BOT-042A`) mới vẽ ca đã có lịch sử, chưa vẽ
      ca cold-start này.

## 4. Phụ thuộc

- [`BOT-042A`](BOT-042A_provisional_commit_design.md) — design phải duyệt trước.
- Chặn [`BOT-042D`](BOT-042D_strategy_engine_tick_path_and_docs.md).
