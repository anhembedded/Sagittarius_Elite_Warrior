# EPIC-018C — Rà soát Hard Design: `src/domain/`

**Thuộc Epic:** [`EPIC-018`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu (rà soát xong, việc sửa chưa làm)
**Phụ thuộc:** Không.
**Nguồn:** [`DECISION_2026-08-30_module_scoped_audits_round2.md`](../DECISION_2026-08-30_module_scoped_audits_round2.md) §2 mục `018C`.

---

## Kết quả rà soát

Đọc hết 58 file `.py` trong `src/domain/`. 3 finding, verify độc lập:

- **C1** — `IStrategy`/`IIndicator` là `Protocol` không lý do (không khớp 1
  trong 3 lý do luật cho phép), mọi implementer đều kế thừa danh nghĩa,
  không consumer nào cần structural typing → đổi sang `ABC`.
- **C2** — `IStoppablePosition` cũng là `Protocol` không lý do hình thức,
  nhưng có lý do thật (tránh lộ `_OpenPosition` private qua ranh giới
  policy) → giữ `Protocol`, thêm `@runtime_checkable` + docstring nêu lý do.
- **C3** — `paper_exchange.py` 451 dòng, vượt ngưỡng 400 → **từ chối tách
  thêm** (method count 12 chưa vượt 15, cắt tiếp không rõ ràng, đã tách
  Policy ở `EPIC-003C` rồi).

`base_indicator_script.py` (ADR D7 cũ) re-verify lại: đọc cả 9 script con
kế thừa, xác nhận DSL surface được dùng thật, không API chết — **giữ
nguyên quyết định từ chối tách**.

## Việc cần làm

1. `src/domain/strategies/i_strategy.py`: `IStrategy(Protocol)` →
   `IStrategy(ABC)`. Kiểm tra `BaseStrategy` đã implement `evaluate()` —
   không cần đổi gì ở implementer, chỉ đổi base của interface.
2. `src/domain/indicators/i_indicator.py`: `IIndicator(Protocol[T_co])` →
   `IIndicator(ABC, Generic[T_co])`. Kiểm tra `EMA`/`MACD`/`RSI`/`WMA`/
   `SupportResistance` đã kế thừa danh nghĩa — không đổi gì ở chúng.
3. `src/domain/backtesting/policies/order_matching_policy.py`:
   `IStoppablePosition` giữ `Protocol`, thêm `@runtime_checkable` +
   docstring nêu rõ lý do (1 trong 3 lý do luật cho phép: tránh lộ type
   private `_OpenPosition` qua ranh giới policy, không dùng ABC được vì
   `_OpenPosition` là dataclass nội bộ của `paper_exchange.py`, không nên
   import ngược).

## Tiêu chí xong

- `IStrategy`/`IIndicator` là `ABC`, mọi implementer hiện có vẫn pass
  không cần sửa (kế thừa danh nghĩa sẵn có).
- `IStoppablePosition` có `@runtime_checkable` + docstring lý do.
- Test hiện có của `strategies/`, `indicators/`, `backtesting/` xanh không
  đổi assertion.
- `paper_exchange.py` **không** bị đụng tới trong task này (quyết định từ
  chối tách đã ghi ở ADR).
