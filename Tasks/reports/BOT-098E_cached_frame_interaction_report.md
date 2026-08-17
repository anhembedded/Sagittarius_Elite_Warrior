# BOT-098E — Báo cáo cached-frame interaction

**Ngày:** 2026-08-17
**Phạm vi:** renderer native Qt/PyQtGraph; không dùng TradingView Lightweight
Charts, WebEngine hoặc JavaScript bridge.

## Kết luận

Cached-frame giải quyết đúng phần latency người dùng cảm nhận trong lúc kéo và
zoom: mỗi preview chỉ khoảng 0,656 ms median, thay vì repaint toàn chart khoảng
43 ms. Khi gesture kết thúc, hệ thống vẫn render lại từ dữ liệu thật nên không
đánh đổi business correctness lấy ảnh cache.

Nó chưa đóng được toàn bộ `BOT-098E`: final exact-data commit vẫn khoảng 28,692
ms, cao hơn frame budget 16,7 ms. Bước tiếp theo vẫn là OHLC/volume LOD và cache
geometry; nếu bước đó không qua gate thì mới tách dependency custom Qt Quick
Scene Graph.

## Evidence

| Probe | Kết quả |
| :--- | :--- |
| CPU full repaint baseline | ~43,2 ms median |
| Cached preview | 0,656 ms median; 1,239 ms p95 |
| Preview throughput | ~1.355 update/s |
| Final exact-data commit | 28,692 ms |
| Final range | Khớp range tính từ gesture |
| Hybrid mouse/wheel event | Pass pan + zoom lifecycle |
| Hybrid render warnings | Không có warning bị cấm |
| Focused regression | 200 passed |
| Full CI | 967 primary + 25 sanity; coverage 94,46% |

## Reproduce

```powershell
# Từ workspace Sagittarius-Engine
.\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m Sagittarius_Elite_Warrior.scripts.benchmarking.backtest_cached_frame_probe
.\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m Sagittarius_Elite_Warrior.scripts.benchmarking.backtest_cached_interaction_hybrid_probe
```

## Trade-off đã chấp nhận

- Preview dùng pixel frame vừa render nên label/grid cũng bị transform tạm thời.
- Pan lớn có thể lộ vùng ngoài frame cache cho tới final commit.
- Source candle, indicator, marker, tooltip và range cuối không bị thay đổi hoặc
  downsample bởi milestone này.
