# Nhiệm vụ: RSI compose 2 instance smoothing tổng quát thay vì tự tính avg_gain/avg_loss

> Không thuộc epic nào — refactor DRY độc lập trên
> [`src/domain/indicators/rsi.py`](../../src/domain/indicators/rsi.py).
> **Không chặn, không bị chặn bởi [`BOT-042`](BOT-042_tick_level_strategy_engine_support.md)**
> — nảy sinh từ review thiết kế `BOT-042A` nhưng cố tình tách ra để không
> tăng rủi ro cho epic đó (`BOT-042` đã tự nhận "rủi ro cao nhất epic").
> Ưu tiên thấp.

## 1. Mục tiêu

`RSI.update()` hiện tự tay quản lý `_avg_gain`/`_avg_loss`/`_gain_sum`/
`_loss_sum`/`_deltas_seen` để làm Wilder's smoothing — nhưng về mặt toán,
công thức đó:

```python
self._avg_gain = (self._avg_gain * (self._period - 1) + gain) / self._period
```

**là 1 dạng EMA** với `α = 1/period` (so với `EMA` hiện tại dùng cố định
`α = 2/(period+1)`). Nghĩa là RSI đang viết tay lại 1 biến thể của recurrence
mà `EMA` đã có sẵn, chỉ khác hệ số — vi phạm DRY.

## 2. Việc cần làm — 2 hướng, chọn 1 khi bắt đầu code

- [ ] **Hướng (a) — tổng quát hoá `EMA`**: thêm cách khởi tạo `EMA` nhận
      `alpha` tường minh (thay vì luôn tự suy từ `period`), vd
      `EMA.from_alpha(alpha)` hoặc tham số `alpha: float | None = None`
      trong `__init__`. `EMA(period)` hiện tại phải **cho kết quả giống
      hệt** sau khi đổi — guard test bắt buộc.
- [ ] **Hướng (b) — class `WilderRMA` riêng**: implement `IIndicator[float]`
      mới, cùng shape với `EMA` nhưng `α = 1/period` cố định, không đụng
      `EMA` hiện có. Ít rủi ro hơn (a) vì không sửa class đang được dùng ở
      nhiều nơi (`MACD`, indicator scripts...), nhưng chấp nhận thêm 1 class
      gần giống `EMA`.
- [ ] Chọn xong, `RSI` compose **2 instance** của class đã chọn — 1 quản lý
      chuỗi Gain, 1 quản lý chuỗi Loss — bỏ hẳn `_avg_gain`/`_avg_loss`/
      `_gain_sum`/`_loss_sum`/`_deltas_seen`. `_previous_close`/`_seed()`
      logic tính `gain`/`loss` từ delta giá **giữ nguyên** (không phải phần
      trùng lặp).

## 3. Guard test bắt buộc

- [ ] Với cùng 1 chuỗi giá cố định, `RSI.update()` trước/sau refactor phải
      cho **kết quả giống hệt từng giá trị, từng bước** — không chỉ giá trị
      cuối cùng. Test hiện có của `RSI` phải xanh **không sửa 1 dòng**.
- [ ] Nếu chọn hướng (a): test riêng cho `EMA(alpha=...)` xác nhận
      `EMA(period)` cũ và `EMA.from_alpha(2/(period+1))` mới cho kết quả
      giống hệt nhau trên cùng input.

## 4. Lưu ý phối hợp với `BOT-042`

`BOT-042B` sẽ thêm `peek_provisional()` cho `RSI` dựa trên cấu trúc
`_avg_gain`/`_avg_loss` **hiện tại** — không chờ task này. Nếu task này làm
**sau** `BOT-042B`, `peek_provisional()` của RSI cần viết lại cho khớp cấu
trúc composed mới (không phức tạp hơn, chỉ đổi chỗ đọc state). Nếu làm
**trước** `BOT-042B`, thì `BOT-042B` viết thẳng trên cấu trúc composed —
không việc nào bị chặn bởi việc kia, chỉ là thứ tự làm trước/sau đổi chỗ
sửa.

## 5. Rủi ro / Lưu ý

- Đây là refactor **nội bộ, không đổi hành vi quan sát được** — nếu bất kỳ
  test nào phải sửa để xanh lại, nghĩa là đã phá bất biến "kết quả giống
  hệt", không phải dấu hiệu "cần cập nhật test".
- Không liên quan tới `MACD` — đề xuất tương tự cho `MACD` (tiêm
  `IIndicator` qua DI thay vì hard-code `EMA`) đã bị từ chối lúc review
  (2026-08-19): MACD hard-code `EMA` là đúng theo **định nghĩa toán học**
  của chính thuật toán, không phải coupling cần gỡ.
