# BOT-098 — Benchmark sau khi native renderer bị revert

**Ngày:** 2026-09-24
**Phạm vi:** đo lại trạng thái thật của Backtest chart (Python/PyQtGraph, chỉ
lựa chọn còn hợp lệ sau ADR D20–D22 cấm QML) sau khi toàn bộ nhánh
`BOT-098F`/`F1`–`F6F` (custom Qt Quick Scene Graph renderer) đã bị xoá
(`36f3a9f9`, 2026-08-24) — không đo lại native vì native không còn tồn tại
trong cây mã nguồn.

## Kết luận

`BOT-098` vẫn mở, chưa có lời giải. Full profile hiện tại (6.420 nến + volume +
5 indicator + 1.112 marker + crosshair) đạt median **83,867 ms** / p95
**99,142 ms**, khoảng 5× mục tiêu median 16,7 ms của tiêu chí #2. Đây là số đo
trên container offscreen (không phải máy tham chiếu của user trong §2 của task
gốc), nên độ lớn tuyệt đối chỉ mang tính định hướng, không phải bằng chứng
gate — nhưng khoảng cách 5× là đủ lớn để không phụ thuộc vào khác biệt máy.

Marker virtualization (`BOT-098A`) vẫn hoạt động đúng thiết kế: bật 1.112
marker chỉ tăng median từ 80,733 → 84,08 ms (~4%), nằm trong ngân sách 25% của
tiêu chí #3. Chi phí chính nằm ở chính pipeline vẽ candle+volume cơ bản (đã
73,8 ms median chỉ với riêng nến, chưa marker/indicator) — đúng kết luận cũ của
`BOT-098E`: LOD/cached-frame không sửa được CPU scene-graph ceiling ở viewport
150 nến. Không có "bước kế tiếp" đã biết trong khuôn khổ QtWidgets-only hiện
tại.

## Sửa harness trước khi đo được

`scripts/benchmarking/backtest_chart_interaction.py` (harness gốc của
`BOT-098`) đã bit-rot theo đợt tái cấu trúc theme (không liên quan
performance): `ChartCard` → `Surface.__init__` → `apply_role()` gọi
`get_theme_bridge()` mà chưa được seed, ném `ValueError`. Hai probe chị em
(`backtest_cached_interaction_hybrid_probe.py`,
`backtest_hybrid_opengl_probe.py`) đã có `seed_app_theme()`
(`src/support/ui_kit/theme_bootstrap.py`) từ trước; harness chính thì chưa.
Vá bằng đúng lời gọi đó, không có logic mới.

## Evidence

| Profile | median (ms) | p95 (ms) | marker overhead |
| :--- | ---: | ---: | :--- |
| candles | 73,799 | 86,546 | — |
| candles+volume | 73,977 | 86,211 | — |
| candles+volume+5-indicators | 80,733 | 96,116 | baseline (0 marker) |
| +1.112 markers | 84,080 | 98,381 | +4,1% vs baseline |
| +crosshair | 83,867 | 99,142 | ~cùng mức với có marker |

Full raw JSON (environment, mọi field) nằm trong log chạy lệnh dưới đây; không
copy lại toàn bộ ở đây để tránh một bản sao có thể lệch khỏi lần chạy thật kế
tiếp (`CONSTITUTION.md` P3).

## Reproduce

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=.. \
  .venv/bin/python -m Sagittarius_Elite_Warrior.scripts.benchmarking.backtest_chart_interaction --profile all
```

## Ngoài phạm vi báo cáo này

Không đề xuất hướng fix mới — đó là việc của bất kỳ ai nhận `BOT-098` tiếp
theo, trong ràng buộc không-QML. Báo cáo này chỉ xác lập bằng chứng hiện trạng
để `BOT-098` không bị đóng nhầm là "đã giải quyết" hay bị bỏ quên vì note cũ
trỏ tới một hướng đã bị xoá.
