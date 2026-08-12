# Nhiệm vụ: Chiến lược Multi-EMA Trend Follower

> Thuộc [BOT-043](BOT-043_named_strategy_library.md) (chỉ mục 4 chiến lược),
> Epic [BOT-040](BOT-040_backtest_screen_full_feature_epic.md).
> Phụ thuộc `BOT-026` ✅, [`BOT-046`](../completed/BOT-046_strategy_param_plumbing.md).
> **Độ khó: thấp** — nên làm đầu tiên trong nhóm, vừa có giá trị vừa là bài
> kiểm chứng cho cơ chế input của `BOT-046`.

## 1. Mục tiêu

Chiến lược theo xu hướng dùng nhiều đường EMA xếp tầng: vào lệnh khi các EMA
xếp đúng thứ tự (vd fast > mid > slow = xu hướng tăng đã xác lập), thoát khi
thứ tự bị phá.

## 2. Vì sao dễ

`EmaCrossoverStrategy` (`BOT-026`) đã làm sẵn phần khó: khuôn `BaseStrategy`,
`build_indicators()`, `Series` + `crossed_above`/`crossed_below`,
`is_above`/`is_below` (`domain/scripting/`). Task này chủ yếu là mở rộng từ 2
đường lên N đường và đổi điều kiện.

## 3. Cần chốt trước khi code

- Bao nhiêu đường EMA và period mặc định? (spec chỉ ghi "Multi-EMA")
- Điều kiện vào lệnh: **xếp tầng đầy đủ** (fast > mid > slow) hay **cắt** đường
  chậm nhất? Hai cái cho kết quả rất khác nhau.
- Điều kiện thoát: phá thứ tự hoàn toàn, hay chỉ cần fast cắt xuống mid?

## 4. Các bước thực hiện (Action Items)

- [ ] Chốt định nghĩa ở mục 3 với user.
- [ ] `MultiEmaTrendFollowerStrategy(BaseStrategy)`: khai báo N period làm
  input ([`BOT-046`](../completed/BOT-046_strategy_param_plumbing.md)), `build_indicators()`
  trả N `EMA`, `decide()` kiểm tra thứ tự xếp tầng.
- [ ] Dùng lại `is_above`/`is_below` từ `domain/scripting/` — **không** viết
  lại so sánh None-safe.
- [ ] Gắn metadata (vd "số đường EMA thuận xu hướng") vào `Signal` cho bảng
  Trade Logs ([`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md)).
- [ ] Đăng ký vào `StrategyRegistry` trong `binance_bot_module.py`.
- [ ] Test golden signal list: chuỗi giá tính tay, so khớp danh sách action
  từng bar (theo đúng cách `test_ema_crossover_strategy.py` đã làm — chạy code
  thật để lấy golden, không đoán).
- [ ] Test batch ≡ incremental (bất biến bắt buộc của mọi strategy).

## 5. Phụ thuộc

- `BOT-026` ✅ — `BaseStrategy`, `EmaCrossoverStrategy` (mẫu tham khảo).
- [`BOT-046`](../completed/BOT-046_strategy_param_plumbing.md) — để period là input.
