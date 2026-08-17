# BOT-098C — Crosshair & paint-path benchmark

**Ngày đo:** 2026-08-17
**Máy tham chiếu:** Windows 11, Python 3.14.6, PySide 6.11.1,
pyqtgraph 0.14.0, viewport 1600×900

## CPU renderer mặc định

| Profile | Median tổng | p95 tổng | Median sync | Median paint |
| :--- | ---: | ---: | ---: | ---: |
| Candles | 30,841 ms | 38,005 ms | 0,689 ms | 30,079 ms |
| + Volume + 5 indicators | 40,889 ms | 62,213 ms | 0,708 ms | 40,119 ms |
| + 1.112 markers | 42,487 ms | 50,870 ms | 0,660 ms | 41,847 ms |
| + Crosshair | 42,871 ms | 50,631 ms | 1,820 ms | 41,232 ms |

Crosshair làm synchronous cost tăng khoảng 1,16 ms nhưng không phải root cause
của stutter. Khoảng 96% full-frame median nằm trong Qt paint/processEvents.
Crosshair cache vẫn có giá trị vì bỏ HTML rebuild và static anchor churn, đồng
thời giữ final mouse position đúng sau burst.

## A/B antialias

Tắt global antialias đưa candles median từ khoảng 30,8 xuống 28,4 ms và full
profile không crosshair từ 42,5 xuống 40,1 ms. Cải thiện nhỏ, không đủ bù visual
quality trade-off và crosshair run có variance cao; không chọn làm production fix.

## A/B OpenGL

Experiment `useOpenGL=True` trên cùng harness:

| Profile | Median tổng | p95 tổng | Median paint |
| :--- | ---: | ---: | ---: |
| Candles | 20,277 ms | 23,538 ms | 19,609 ms |
| + Volume + 5 indicators | 20,208 ms | 38,962 ms | 19,600 ms |
| + 1.112 markers | 22,856 ms | 27,539 ms | 22,180 ms |
| + Crosshair | 22,935 ms | 27,101 ms | 21,000 ms |

OpenGL gần gấp đôi throughput (~23 → ~44 updates/s full profile) và là hướng có
evidence, nhưng vẫn chưa đạt median 16,7 ms. Không bật global ở `BOT-098C`: cần
subtask riêng kiểm tra visual text/grid/marker, hybrid QQuickWidget warnings,
offscreen fallback và shutdown lifecycle trước khi bật riêng Backtest.

## Kết luận

Python range/crosshair không còn bottleneck chính. `BOT-098D` nên triển khai
OpenGL có scope/fallback/probe rõ ràng; parent `BOT-098` chỉ được đóng khi desktop
hybrid probe sạch và người dùng xác nhận interaction thực tế đủ mượt.
