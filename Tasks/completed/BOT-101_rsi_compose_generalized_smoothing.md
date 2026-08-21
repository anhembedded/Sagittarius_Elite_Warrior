# Nhiệm vụ: RSI compose 2 instance smoothing tổng quát thay vì tự tính avg_gain/avg_loss

> Không thuộc epic nào — refactor DRY độc lập trên
> [`src/domain/indicators/rsi.py`](../../src/domain/indicators/rsi.py).
> **Trạng thái:** ✅ **Hoàn thành (2026-08-21)**
> **Không chặn, không bị chặn bởi [`BOT-042`](BOT-042_tick_level_strategy_engine_support.md)**
> — nảy sinh từ review thiết kế `BOT-042A` nhưng cố tình tách ra để không
> tăng rủi ro cho epic đó (`BOT-042` đã tự nhận "rủi ro cao nhất epic").
> Ưu tiên thấp.

## 1. Mục tiêu

`RSI.update()` trước đây tự tay quản lý `_avg_gain`/`_avg_loss`/`_gain_sum`/
`_loss_sum`/`_deltas_seen` để làm Wilder's smoothing — nhưng về mặt toán,
công thức đó:

```python
self._avg_gain = (self._avg_gain * (self._period - 1) + gain) / self._period
```

**là 1 dạng EMA** với `α = 1/period` (so với `EMA` hiện tại dùng cố định
`α = 2/(period+1)`). Nghĩa là RSI đang viết tay lại 1 biến thể của recurrence
mà `EMA` đã có sẵn, chỉ khác hệ số — vi phạm DRY.

## 2. Việc đã làm (Chọn Hướng a)

- [x] **Hướng (a) — tổng quát hoá `EMA`**: thêm tham số `alpha: float | None = None`
      vào `EMA.__init__`. Khi `alpha is None`, `multiplier` tính theo công thức
      chuẩn `2.0 / (period + 1)` (bảo toàn 100% kết quả cũ). Khi truyền `alpha`,
      thực hiện validate biên chặt chẽ theo Sentinel: `math.isfinite(alpha)` và
      `0.0 < alpha <= 1.0`, ném `ValueError` nếu không hợp lệ.
- [x] **RSI compose 2 instance**: `_gain_smoother = EMA(period, alpha=1.0/period)`
      và `_loss_smoother = EMA(period, alpha=1.0/period)`. Xoá bỏ hoàn toàn các
      biến thủ công `_avg_gain`/`_avg_loss`/`_gain_sum`/`_loss_sum`/`_deltas_seen`.
      `_previous_close` và logic tính `gain`/`loss` từ delta giá giữ nguyên.
- [x] **`peek_provisional()` tinh gọn**: ủy quyền trực tiếp cho `peek_provisional()`
      của 2 smoothers, đảm bảo tính bất biến của state không bị mutate.

## 3. Kiểm thử & Guard tests

- [x] **Guard test hồi quy**: Toàn bộ unit tests hiện có của `RSI`, `EMA`, `MACD`,
      `WMA`, `SupportResistance` pass 100% không đổi bất kỳ assertion nào.
- [x] **Toàn bộ Edge Cases**:
  - `test_ema_explicit_default_alpha_matches_implicit_alpha`: so sánh `EMA(p)` với `EMA(p, alpha=2/(p+1))`.
  - `test_ema_custom_wilder_alpha_matches_recurrence`: đối chiếu recurrence formula.
  - `test_ema_invalid_alpha_raises`: tham số alpha $0, -0.1, 1.0001, \text{NaN}, \pm\infty$.
  - `test_ema_alpha_one_tracks_input_immediately_post_seed`: alpha = 1.0.
  - `test_ema_negative_inputs` & `test_ema_extreme_magnitude_scales`: giá âm, $10^9, 10^{-8}$.
  - `test_rsi_strictly_decreasing_prices_yields_zero`: giá giảm liên tục $\rightarrow$ RSI = 0.0.
  - `test_rsi_flat_prices_yields_fifty`: giá đi ngang $\rightarrow$ RSI = 50.0.
  - `test_rsi_period_one`: chu kỳ cực tiểu $N = 1$ seed ngay nến 2.
  - `test_rsi_large_period_warmup`: chu kỳ lớn $N = 50$.
  - `test_rsi_negative_price_series` & `test_rsi_extreme_scales`: chuỗi giá âm, quy mô $10^9$ và $10^{-8}$.
  - `test_rsi_oscillating_prices_converges_within_bounds`: dao động xen kẽ trong $(0, 100)$.
  - `test_rsi_matches_independent_mathematical_reference`: đối chiếu độc lập với hàm chuẩn sách giáo khoa Wilder.
  - `test_rsi_peek_provisional_stress_pure_state`: stress test 500+ probes không làm bẩn state.
  - `test_rsi_peek_provisional_extreme_directional_moves`: nhảy vọt cực đại / giảm cực đại.
  - `test_rsi_batch_vs_incremental_identity`: bất biến Batch ≡ Incremental streaming.

## 4. Ghi chú Triển khai

- **File sửa**:
  - [`src/domain/indicators/ema.py`](../../src/domain/indicators/ema.py): Thêm `alpha: float | None = None` kèm Sentinel validation.
  - [`src/domain/indicators/rsi.py`](../../src/domain/indicators/rsi.py): Refactor `RSI` sang composition 2 instance `EMA`.
  - [`tests/unit/domain/indicators/test_ema.py`](../../tests/unit/domain/indicators/test_ema.py): Thêm 7 unit tests edge cases.
  - [`tests/unit/domain/indicators/test_rsi.py`](../../tests/unit/domain/indicators/test_rsi.py): Thêm 11 unit tests edge cases.
- **Verification**: `ci-local.ps1 -Full` exit 0 (1666 unit tests, 41 sanity tests, 82.52% coverage, 0 warnings/errors log scan).
