# BOT-098B — Cache & coalesce chart range updates

**Parent:** `BOT-098`
**Ưu tiên:** P1
**Trạng thái:** Completed

## Vấn đề

Sau `BOT-098A`, profile không marker vẫn chỉ đạt khoảng 23–28 updates/s.
`sigXRangeChanged` hiện gọi đồng bộ `VolumeItem.setOpts()` và mọi indicator
`setData()` cho từng signal, kể cả burst cùng event cycle hoặc khi binary-search
vẫn trả đúng visible slice cũ.

## Phạm vi

1. Cache visible `(lo, hi)` của volume và từng indicator; bỏ update scene khi
   slice và data revision không đổi.
2. Data/live update trong cùng viewport vẫn phải render, không được cache nhầm.
3. Coalesce burst range signals theo UI frame; luôn apply final range.
4. Cleanup timer/pending callback an toàn khi chart bị huỷ.
5. Mở rộng benchmark để ghi số range signal so với số renderer apply.

## Acceptance criteria

- Regression test chứng minh duplicate slice không gọi `setOpts`/`setData`.
- Regression test chứng minh data mới cùng slice vẫn được apply.
- Event burst chỉ apply final range một lần; dispose không chạy pending work.
- Final marker/candle/volume/indicator viewport đúng.
- `scripts/ci-local.ps1 -Full` xanh.

## Evidence

- Focused chart/component suite: 208 tests pass.
- Full CI sau khi hợp nhất BOT-074: Ruff sạch; 944 primary + 25 sanity pass.
- Benchmark: 140 raw range callbacks được coalesce còn 70–71 renderer applies;
  5 indicators thực hiện 350 thay vì 700 `setData` calls.
- Báo cáo: [`BOT-098B range update benchmark`](../reports/BOT-098B_range_update_benchmark.md).
