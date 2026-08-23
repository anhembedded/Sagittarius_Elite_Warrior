# BUG-036 — Gate "Chart Benchmark Contract" flaky: synthetic hover ghi đè crosshair mà benchmark vừa đặt

**Reported:** 2026-08-23 — user báo bước gate `Chart Benchmark Contract —
Python vs Native` (`scripts/ci-local.ps1`, ~dòng 269) lúc PASS lúc FAIL trên
**cây làm việc giống hệt nhau từng byte** (đã xác nhận `git diff --stat` rỗng
giữa các lần chạy).
**Severity:** 🟡 P2 — không phải lỗi sản phẩm; nhưng một bước gate không đáng
tin còn tệ hơn một bước gate thành thật là non-blocking: nó dạy người đọc
quen với việc "chạy lại là hết", và đúng lúc contract bắt được divergence
Python-vs-native thật thì không ai còn tin nữa.
**Status:** ✅ **Fixed 2026-08-23** — root-caused bằng event-filter probe,
tái hiện được **5/40 lần dưới tải** trên code chưa sửa, **0/40 sau khi sửa**,
regression test ở tầng Sanity đã xác nhận FAIL đúng lý do trước khi sửa.

---

## Symptom

Ba lần chạy liên tiếp cùng ngày, cùng cây code:

| Log | Kết quả |
| :--- | :--- |
| `logs/ci-local-20260823-192837.log` | PASSED |
| `logs/ci-local-20260823-193910.log` | **FAILED** |
| `logs/ci-local-20260823-194123.log` | PASSED |

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ▶  Chart Benchmark Contract — Python vs Native
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Benchmark contract violation: native final crosshair candle truth violated
Benchmark contract violation: native final crosshair candle truth violated
  ❌  Chart Benchmark Contract FAILED
```

Lần FAIL rơi đúng vào lúc máy đang tải nặng (nhiều gate `-Full` và package
build chạy nối nhau) — giả thuyết ban đầu của user, và hoá ra đúng.

Chú ý: thông báo **không có một con số nào**. Không biết nó lệch bao nhiêu,
lệch về đâu. Đây chính là lý do phải điều tra từ đầu thay vì đọc log ra ngay
(xem phần Fix — thông báo đã được sửa để mang số).

---

## Root cause

Không phải timing của render thread, không phải `grabWindow()`, không phải
kích thước cửa sổ. **`crosshairCandleIndex` có hai người ghi, và benchmark
đọc nó ở thời điểm mà người ghi thứ hai có thể đã chen vào.**

### Người ghi thứ nhất — chủ đích

`scripts/benchmarking/chart_migration_benchmark.py` quét crosshair bằng
chương trình, không bằng chuột thật:

```python
for fraction in (0.1, 0.25, 0.5, 0.75, 0.9):
    chart.setCrosshairPosition(float(actual_width) * fraction, ...)
    app.processEvents()
    view.grabWindow()
...
crosshair_final_candle_index=int(chart.property("crosshairCandleIndex")),
expected_crosshair_candle_index=final_start + int(_VISIBLE_CANDLES * 0.9),
```

`NativeChartItem::setCrosshairPosition()`
([`native/chart_renderer/native_chart_item.cpp:1034`](../../../native/chart_renderer/native_chart_item.cpp))
tính và ghi `crosshairCandleIndex_` **đồng bộ, ngay trong thân hàm**, trước
khi return — không có cross-thread hop nào. Ánh xạ là hàm thuần tuý của
`(x, width(), viewportStart_, viewportEnd_)`.

### Người ghi thứ hai — Qt tự sinh

`NativeChartItem` bật `setAcceptHoverEvents(true)`
([`native_chart_item.cpp:484`](../../../native/chart_renderer/native_chart_item.cpp))
và có:

```cpp
void NativeChartItem::hoverMoveEvent(QHoverEvent* event) {
    setCrosshairPosition(event->position().x(), event->position().y());
    event->accept();
}
```

Qt Quick **tự sinh** hover event và gửi tới item trong lúc flush
frame-synchronous event (`QQuickDeliveryAgent`), đặt tại vị trí con trỏ của
chính platform. Dưới `QT_QPA_PLATFORM=offscreen` **không có con trỏ thật**,
platform báo một vị trí ma cố định là **(8, 8)**.

Vậy là: giữa lần `setCrosshairPosition()` cuối cùng và lệnh đọc property,
benchmark có gọi `app.processEvents()` và `view.grabWindow()` — đúng cái cửa
sổ mà hover ma có thể được giao. Khi nó rơi vào đó:

```
x = 8  →  floor(5143 + 8/1600 × 150) = 5143   (nến đầu tiên đang hiển thị)
thay vì   floor(5143 + 0.9 × 150)    = 5278
```

**Hover ma rơi vào cửa sổ đó hay không hoàn toàn do frame scheduling quyết
định** — nên cùng một cây code, lúc PASS lúc FAIL, và chỉ FAIL khi máy tải
nặng.

### Bằng chứng trực tiếp

Cài `QObject` event filter lên chart item rồi in kèm giá trị property trước
và sau mỗi `grabWindow()` (`bug-fix-rule.md` §2 — instrument nhiều tầng, ở
đây là tầng event delivery và tầng property):

```
[probe]   f=0.5 x=800.0 itemw=1600.0 idx=5218
[probe]     !! HoverMove pos=8.0,8.0             ← Qt tự sinh, không ai gọi
[probe]   after-grab f=0.5 itemw=1600.0 idx=5143 ← bị ghi đè
```

Bốn lần chạy liên tiếp cho thấy nó rơi vào **vị trí khác nhau mỗi lần** (sau
`f=0.5`, không xuất hiện, không xuất hiện, sau `f=0.25`) — đúng đặc trưng
nondeterministic. Khi nó rơi sau `f=0.9` thì gate FAIL.

Loại trừ rõ ràng các nghi phạm khác: `item=(1600.0x900.0)` và
`vp=(5143.0,5293.0)` **giống hệt nhau ở mọi lần chạy** — kích thước cửa sổ và
viewport không hề dao động.

### Tái hiện định lượng

Cùng `.so` native, cùng fixture, 16 vòng lặp bận trên máy 8 nhân:

| Code | Số lần chạy | Số lần sai |
| :--- | :---: | :---: |
| Chưa sửa | 40 | **5** — tất cả đều `got=5143 expected=5278` |
| Đã sửa | 40 | **0** |

`5143` khớp chính xác con số mà con trỏ ma tại x=8 phân giải ra.

---

## Fix

### 1. Đọc ở thời điểm duy nhất không ai chen vào được

`setCrosshairPosition()` là hàm đồng bộ và thuần tuý, nên **đọc property ngay
sau khi nó return, trước khi bơm bất kỳ event nào**. Giữa hai câu lệnh Python
liên tiếp không có vòng lặp event nào chạy — không hover ma, không
`HoverLeave`, không gì cả. Đây là điểm đọc *duy nhất* bất biến, chứ không
phải "chờ cho ổn định" (không có trạng thái ổn định để chờ: hover ma là sự
kiện bất đồng bộ không có thời hạn trên).

Tách thành `drive_programmatic_crosshair_sweep()` trả về
`CrosshairSweepOutcome(authored_candle_index, flushed_candle_index)`.

**Đã cân nhắc và loại bỏ:** tạm tắt `setAcceptHoverEvents(False)` trong lúc
quét. Đo thực tế cho thấy cách này *tệ hơn* — delivery agent lập tức gửi
`HoverLeave`, `hoverLeaveEvent()` gọi `clearCrosshair()`, và index thành
`-1`. Đổi một người ghi ma này lấy một người ghi ma khác:

```
suspend_hover=False expected=150 got=101 OVERWRITTEN
suspend_hover=True  expected=150 got=-1  OVERWRITTEN
```

### 2. Không giấu flake — ghi nhận nó

Contract vẫn dùng `authored_candle_index` (giá trị đúng, tất định), nhưng giá
trị sau khi flush vẫn được đo và:

- đưa vào report tại `renderer_diagnostics.crosshair_candle_index_after_flush`;
- log ở mức **WARNING** với tag `[bench-crosshair]` khi hai giá trị lệch nhau.

Nghĩa là hover ma vẫn hiện ra trong log gate, chỉ là **không còn quyết định
kết quả gate** nữa. Contract không hề bị nới lỏng — nó vẫn so sánh đúng phép
so sánh cũ, chỉ đọc ở đúng chỗ.

### 3. Logging nhiều tầng (theo `logging-rule.md`, user yêu cầu trực tiếp)

Script trước đây không log gì cả; đó là lý do một câu báo lỗi trống rỗng phải
đổi bằng cả một cuộc điều tra. Đã bổ sung, dùng logger `App.ChartBenchmark`
với handler gắn ngay trong script (script chạy độc lập, ngoài bootstrapper —
đây là ngoại lệ mà §1 cho phép), format khớp `StdLogger` để lọc được y hệt log
app:

| Tag | Mức | Nội dung |
| :--- | :--- | :--- |
| `[bench-env]` | INFO | Một dòng duy nhất: platform, PySide/Qt, ABI, DPR, kích thước **yêu cầu vs được cấp**, kích thước item (§3) |
| `[bench-env]` | WARNING | Compositor cấp kích thước khác yêu cầu |
| `[bench-crosshair]` | INFO | Mở/đóng lần quét: item size, viewport, authored vs flushed, `perturbed=` |
| `[bench-crosshair]` | DEBUG | Một dòng mỗi lần dời con trỏ (per-event → DEBUG, §4/§6) |
| `[bench-crosshair]` | WARNING | Hover ma đã ghi đè sau lần dời cuối |
| `[bench-contract]` | INFO/ERROR | Kết luận contract |

Thêm `--log-level`; log ra **stderr** vì stdout đang chở JSON report.

### 4. Thông báo vi phạm mang số

```
native final crosshair candle truth violated: got 5143, expected 5278
(index after event flush: 5143)
```

### 5. Cùng lớp lỗi ở chỗ khác — đã sửa luôn

`tests/sanity/test_native_chart_qml_plugin_sanity.py:353` có **đúng cùng một
race**, và cũng nằm trong gate `-Full`:

```python
assert root.setCrosshairPosition(320.0, 180.0) is True
view.grabWindow()                                    # ← cửa sổ cho hover ma
_wait_for_property(qapp, root, "crosshairVisible", True)
assert root.property("crosshairCandleIndex") == 2
```

Với viewport `(1,4)` và width 640, con trỏ ma tại x=8 phân giải ra nến 1 chứ
không phải 2. Đã đổi sang đọc trước khi bơm event; không bỏ assertion nào.

---

## Regression test

`tests/sanity/test_bug036_benchmark_crosshair_hover_race.py` — **tầng Sanity,
chạy với plugin native thật**. Bắt buộc phải ở tầng này: chỗ ghi đè nằm bên
trong `NativeChartItem::hoverMoveEvent()`, nên một test double cho item sẽ
không bao giờ chạm tới đường lỗi (`bug-fix-rule.md` §3, bài học `BUG-013`).

Test bơm hover ma qua **đúng đường delivery thật** — gửi `QMouseEvent` tới
*window* để `QQuickDeliveryAgent` tự chuyển thành hover, chứ không gửi thẳng
`QHoverEvent` vào item (gửi thẳng sẽ đi vòng qua chính cơ chế đang cần chứng
minh). `QTimer.singleShot(0, ...)` bảo đảm nó nổ đúng trong
`processEvents()` của lần quét — tức đúng cửa sổ dễ tổn thương.

4 test:

1. `..._reports_the_candle_it_authored_despite_phantom_hover` — reproduction chính.
2. `..._records_a_phantom_hover_instead_of_hiding_it` — flake phải hiện ra ở `flushed_candle_index`.
3. `..._is_stable_without_any_phantom_hover` — không nhiễu thì hai giá trị bằng nhau (chống false positive cho diagnostic).
4. `..._rejects_an_empty_fraction_sequence` — sweep rỗng không được lặng lẽ trả sentinel `-1`.

**Xác nhận FAIL đúng lý do trước khi sửa:** tạm chuyển điểm đọc về sau
`processEvents()`/`grabWindow()` (đúng hình dạng code cũ) →

```
E       assert 101 == 190
E        +  where 101 = CrosshairSweepOutcome(authored_candle_index=101,
                                              flushed_candle_index=101).authored_candle_index
2 failed, 2 passed
```

`101` là nến của con trỏ ma, `190` là nến được đặt bằng chương trình — **cùng
hình dạng với `5143` vs `5278`** của lần FAIL thật. Khôi phục fix → `4 passed`.

---

## Ghi chú

- Thông báo bị **in hai lần** trong log là do cách `ci-local.ps1` gom
  stdout/stderr, không phải benchmark tự in hai lần. Chỉ là chuyện thẩm mỹ,
  không đụng tới trong lần sửa này.
- File `chart_migration_benchmark.py` nằm trong danh sách loại trừ `mypy`
  (`pyproject.toml` dòng 56) — nợ kỹ thuật đóng băng từ 2026-08-21. Thay đổi
  này đưa số lỗi từ 16 xuống 14, không thêm lỗi mới.
- `BUG-016` (`--desktop-contract` treo trên Windows) là **lỗi khác**, không
  liên quan: nó treo ở `view.grabWindow()`, không phải ở crosshair.
