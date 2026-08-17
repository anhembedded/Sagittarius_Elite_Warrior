# BOT-098A — Marker viewport benchmark

**Ngày đo:** 2026-08-17
**Harness:** `scripts/benchmarking/backtest_chart_interaction.py`
**Lưu ý:** timing là evidence trên máy tham chiếu, không phải hard CI gate.

## Environment

- Windows 11 `10.0.26200`, Python `3.14.6`
- PySide `6.11.1`, pyqtgraph `0.14.0`, Qt platform `windows`
- Chart viewport `1600x900`
- Dataset: 6.420 candles, volume, 5 indicators, 1.112 markers
- Visible window: 150 candles; 120 measured pan updates sau 20 warmups

## Kết quả sau BOT-098A

| Profile | Median | p95 | Updates/s | Marker stored/active |
| :--- | ---: | ---: | ---: | ---: |
| Candles | 34,381 ms | 43,628 ms | 28,04 | 0 / 0 |
| + Volume | 37,906 ms | 53,563 ms | 24,87 | 0 / 0 |
| + 5 indicators | 43,033 ms | 49,393 ms | 23,06 | 0 / 0 |
| + 1.112 markers | 47,491 ms | 55,096 ms | 21,06 | 1.112 / 31 |

Marker overhead trong cùng lượt đo là khoảng `+10,4%` median so với profile
volume + 5 indicators, nằm dưới budget `25%` của parent `BOT-098`. Chỉ 31 / 1.112
marker là scene items ở viewport cuối; full business history vẫn được giữ.

So với probe điều tra ban đầu (full 1.112 `TextItem`, khoảng 9 updates/s), lượt
đo mới đạt 21,06 updates/s. Hai harness không hoàn toàn đồng nhất nên con số này
chỉ là directional evidence; A/B đáng tin hơn là hai profile liền kề trong cùng
harness ở bảng trên.

## Kết luận

`BOT-098A` giải quyết root cause marker full-history và thêm FPS paint overlay
dev-only. Toàn parent `BOT-098` **chưa xong**: ngay cả profile không marker vẫn
chỉ 23–28 updates/s và chưa đạt 60 FPS. Pha kế tiếp phải cache/coalesce range
pipeline của Volume/Indicator trước khi đụng OpenGL.

## Cách chạy lại

Từ workspace root `Sagittarius-Engine`:

```powershell
.\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m Sagittarius_Elite_Warrior.scripts.benchmarking.backtest_chart_interaction
```

Để xem FPS trên app thật:

```powershell
.\Sagittarius_Elite_Warrior\scripts\run-ui.ps1 -Dev
```
