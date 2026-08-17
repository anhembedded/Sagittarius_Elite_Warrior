# BOT-098B — Range update pipeline benchmark

**Ngày đo:** 2026-08-17
**Harness:** `scripts/benchmarking/backtest_chart_interaction.py`

## Kết quả

Dataset giữ nguyên 6.420 candles, volume, 5 indicators, 1.112 markers, viewport
150 candles và 140 raw range callbacks (20 warmup + 120 measured updates).

| Profile | Median | p95 | Raw callbacks | Coalesced applies |
| :--- | ---: | ---: | ---: | ---: |
| Candles | 33,984 ms | 38,852 ms | 140 | 71 |
| + Volume | 32,787 ms | 38,343 ms | 140 | 71 |
| + 5 indicators | 40,149 ms | 45,321 ms | 140 | 70 |
| + 1.112 markers | 45,670 ms | 55,022 ms | 140 | 70 |

Trong probe này scheduler giảm khoảng 50% lượt apply range. Profile 5 indicators
thực hiện 350 `setData` tương ứng 70 final range × 5 lines, thay vì 700 lần nếu
apply mọi callback. Volume thực hiện 70 lần. Cache `(lo, hi, data_revision)` còn
loại riêng các callback khác range nhưng vẫn rơi vào cùng binary-search slice.

Median full profile giảm directional từ `47,491 ms` ở lượt BOT-098A xuống
`45,670 ms`, nhưng hai lượt benchmark có noise hệ thống nên không dùng chênh
lệch này làm claim cứng. Bằng chứng deterministic của fix là callback/apply count
và regression mock call count.

## Kết luận

Range pipeline không còn replay mọi signal, nhưng chart vẫn chưa đạt 60 FPS.
Profile candles-only khoảng 34 ms cho thấy nút thắt tiếp theo nằm ở paint/event
path cơ bản và crosshair, không còn chủ yếu ở marker hay duplicate `setData`.
Không có bằng chứng để bật OpenGL hoặc hạ chất lượng dữ liệu một cách mù quáng.
