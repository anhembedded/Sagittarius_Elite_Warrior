# Nhiệm vụ: BOT-042A — Thiết kế Provisional vs Commit (class + sequence diagram)

> Thuộc Epic [`BOT-042`](BOT-042_tick_level_strategy_engine_support.md).
> Không phụ thuộc task nào; **chặn `BOT-042B`/`BOT-042C`** — đừng code trước
> khi task này được duyệt.

## 1. Mục tiêu

Chốt thiết kế kỹ thuật cho việc thêm đường "tính tạm, không mutate" (
`peek_provisional`/`poke_provisional`) song song với đường "chốt" hiện có
(`update`/`push`) trên `IIndicator` và `Series` — **trước khi viết code
thật** — để review/phê duyệt, đúng quy trình thiết kế trước-code của các
epic khác trong repo (vd `Docs/Diagrams/symbol_market_metadata_design.md`
cho `BOT-095E1`).

**Đây là task tài liệu, không phải task code.** Không có dòng code sản
xuất nào được viết trong task này.

## 2. Sản phẩm bàn giao

- [x] [`Docs/Diagrams/tick_provisional_commit_design.md`](../../Docs/Diagrams/tick_provisional_commit_design.md)
      gồm:
      - Class diagram (mermaid) — `IIndicator`/`EMA`/`RSI`/`MACD`/`WMA`/`Series`
        với method mới, ghi rõ khác biệt xử lý từng lớp (đặc biệt `WMA` — không
        có công thức đóng nên phải dựng view tạm từ `deque`, khác `EMA`/`RSI`).
      - Sequence diagram (mermaid) — vòng đời 1 tick giữa bar đang hình thành
        tới lúc bar đóng, minh hoạ `Series[0]`/`Series[1]` không bị lẫn lộn.
      - Nguyên tắc thiết kế: additive-only, zero-mutation guarantee, O(1)
        (trừ `WMA`), và ghi rõ lời hứa "batch ≡ incremental" của `BOT-020`
        bị vô hiệu có chủ đích.
- [x] **User duyệt (2026-08-19)** — qua 2 vòng review thật: (1) đề xuất DIP
      cho `MACD`/DRY cho `RSI` → MACD bị từ chối có lý do, RSI tách thành
      `BOT-101` riêng (không chặn `BOT-042`); (2) ca cold-start/IndexError →
      xác nhận đã được `Series.__getitem__` xử lý an toàn từ trước, bổ sung
      guard test tường minh vào `BOT-042C`. User chốt "ok, commit và bắt đầu
      làm task" sau cả 2 vòng — không phản đối tên method hay cách `WMA` xử
      lý provisional (câu 1-2 dưới), coi như chấp nhận.

## 3. Câu hỏi cần user trả lời khi duyệt

1. Tên method `peek_provisional`/`poke_provisional` có ổn không, hay muốn
   tên khác? (Đổi tên ở giai đoạn này rẻ, đổi sau khi `BOT-042B`/`C` đã
   code thì tốn hơn nhiều chỗ.) → Không bị phản đối qua 2 vòng review, giữ
   nguyên.
2. `WMA` xử lý provisional bằng cách dựng view tạm từ `deque` (không phải
   O(1) thuần như `EMA`/`RSI`, mà O(period)) — chấp nhận được không, hay
   cần thiết kế khác? → Không bị phản đối, giữ nguyên.
3. Phạm vi `BOT-042D` (sửa lời hứa `BOT-020`) đúng là action item bắt buộc,
   không phải tuỳ chọn — xác nhận lại trước khi nó trở thành 1 task riêng.
   → Không bị phản đối, giữ nguyên là bắt buộc.

## 4. Phụ thuộc

- Không phụ thuộc task nào để bắt đầu (đọc code hiện có, không cần code mới).
- Chặn [`BOT-042B`](BOT-042B_indicator_provisional_contract.md) và
  [`BOT-042C`](BOT-042C_series_provisional_slot.md).
