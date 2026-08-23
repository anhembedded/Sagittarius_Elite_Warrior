# BUG-037 — Native chart bị bỏ ở MỌI lần chạy Backtest vì payload trend-zone RỖNG

**Reported:** 2026-08-23 — user chất vấn kết luận "chart đang chạy Python" trong
lúc điều tra [`BUG-036`](BUG-036_benchmark_crosshair_contract_synthetic_hover_race.md):
*"ủa sao Python mà nó mượt vậy, bạn chắc không đó"* và *"tui nghĩ nó đã
implement background color API rồi mà ta"*. Chính hai câu hỏi đó dẫn thẳng
tới bug này — kết luận cũ đúng, nhưng **lý do thì sai**.
**Severity:** 🔴 **P1** — vô hiệu hoá toàn bộ đường native chart
(`BOT-098F`, một epic nhiều task) ở runtime, trong khi log khởi động vẫn báo
`backend 'native'`. Không crash, không thông báo, không ai biết.
**Status:** 🔴 Open

---

## Symptom

Màn Backtest luôn khởi tạo native host, rồi **luôn** rơi về Python ngay ở lần
chạy đầu tiên. Trích `logs/debug-20260823-142417.log` (chạy `--debug`, strategy
`ema_crossover`):

```
dòng   29  21:24:35,228  App.BacktestChartHostFactory  INFO
             Backtest chart host initialized ... with backend 'native' (requested: 'auto').

dòng 4914  21:25:05,672  App.BackTestPresenter         WARNING
             Native Backtest chart does not support strategy trend zones;
             rebuilding with the Python host.

dòng 4915  21:25:05,672  App.BacktestChartHostFactory  INFO
             Backtest chart host initialized ... with backend 'python' (requested: 'python').

dòng 4917  21:25:05,710  App.ChartCard                 INFO
             [chart-env] ChartCard(BTCUSDT): render backend=cpu (opengl requested=False) | ...
```

Cả file **chỉ có đúng 2 dòng khởi tạo host** — không bao giờ quay lại native.

**Điểm mấu chốt:** `ema_crossover` **không** override `classify_trend_zone()`.
Trong toàn bộ `src/domain/strategies/`, chỉ `long_term_trend_zone_strategy.py`
override nó. Nghĩa là lần chạy này có **0 vùng trend zone để vẽ** — vậy mà vẫn
bị đá khỏi native.

---

## Root cause

`crosshair`-style "hai người ghi" của `BUG-036` thì đây là "**từ chối việc mình
không hề được giao**".

### Tầng 1 — Presenter phát tín hiệu vô điều kiện

[`backtest_presenter.py:2667`](../../../src/presentation/ui/screens/backtest/backtest_presenter.py):

```python
spans = compute_strategy_trend_zones(strategy, raw_klines)
self._chartStrategyRegionSignal.emit(action_id, spans)   # emit cả khi spans == []
```

Docstring của chính hàm này (dòng 2658-2661) tự lý giải là an toàn:

> *"A strategy that never overrides `classify_trend_zone()` (every strategy
> predating BOT-113) computes an empty span list — **one no-op signal emit**,
> no zones drawn, chart looks exactly as it did before this feature existed."*

Lập luận đó **đúng với `PythonBacktestChartHost`** — set 0 region đúng là no-op.

### Tầng 2 — Adapter native raise mà không nhìn payload

[`native_backtest_chart_host_adapter.py:198`](../../../src/presentation/ui/screens/backtest/logic/native_backtest_chart_host_adapter.py):

```python
def set_script_regions(self, key, spans):
    raise NativeUnsupportedFeatureError("native script regions are not supported")
```

Không hề đọc `spans`. Với native, "no-op emit" **không phải no-op** — nó ném lỗi.
`set_script_info` (dòng 206) y hệt.

### Tầng 3 — Presenter bắt lỗi và đập host đi dựng lại

`_on_chart_strategy_region` bắt `NativeUnsupportedFeatureError` →
`_fallback_to_python_after_unsupported_native_feature()` →
`view.set_chart_backend("python")` + `render_symbol_cards()`.

**Chuỗi hoàn chỉnh:** mọi lần chạy backtest → emit spans rỗng → adapter raise →
native host bị vứt → dựng lại bằng Python. Với **mọi strategy**, kể cả strategy
không liên quan gì tới trend zone.

### Vì sao native *thật sự* không có background region

Xác nhận bằng cách liệt kê toàn bộ bề mặt API C++ — `native_chart_item.h` có
đúng **6 `Q_INVOKABLE`**: `submitSnapshot`, `submitIndicatorSnapshot`,
`submitMarkerSnapshot`, `setViewport`, `setCrosshairPosition`, `clearCrosshair`.
`grep -niE "background|region|zone|shade"` trên cả `native_chart_item.h` và
`snapshot_abi.h` → **0 kết quả**.

Nên giới hạn là **có thật** (đúng phạm vi `BOT-032`) — bug nằm ở chỗ giới hạn đó
được áp cả khi không có gì để vẽ.

### Vì sao bug sống sót lâu — test đã đóng băng chính hành vi sai

[`test_native_backtest_chart_host_adapter.py:168`](../../../tests/unit/presentation/ui/screens/test_native_backtest_chart_host_adapter.py)
(trước khi sửa):

```python
def test_script_regions_and_info_are_rejected(adapter):
    with pytest.raises(NativeUnsupportedFeatureError, match="regions"):
        adapter.set_script_regions("k", [])      # ← payload RỖNG
    with pytest.raises(NativeUnsupportedFeatureError, match="info"):
        adapter.set_script_info("k", [])         # ← payload RỖNG
```

`[]` được dùng như một giá trị cho có, nhưng nó **khẳng định rằng gọi rỗng phải
raise** — tức là biến đúng cái defect thành hợp đồng được test bảo vệ. Đây là
biến thể của bẫy #4 trong `ONBOARDING.md` (assert vào thứ không phải điều test
thật sự quan tâm).

---

## Fix

Sửa ở adapter, không ở presenter: hợp đồng đúng của một renderer là **chỉ từ
chối thứ nó thật sự được yêu cầu vẽ**. Được giao "không có gì" thì mọi renderer
đều làm được — và đó đã là hành vi sẵn có của `clear_script_regions()` /
`clear_script_info()` ngay bên dưới.

```python
def set_script_regions(self, key, spans):
    if not spans:
        return
    raise NativeUnsupportedFeatureError("native script regions are not supported")

def set_script_info(self, key, fields):
    if not fields:
        return
    raise NativeUnsupportedFeatureError("native script info is not supported")
```

**Vì sao không sửa ở presenter** (chặn emit khi rỗng): sẽ chỉ vá đúng một call
site. `set_script_regions()` còn được gọi từ đường indicator script
(`shade()`, `BOT-032`) qua `IndicatorScriptRunner.draw_region()`. Sửa ở adapter
bịt cả hai, và đặt đúng trách nhiệm ở nơi định nghĩa "cái gì không hỗ trợ".

**Giới hạn thật được giữ nguyên:** span/field **không rỗng** vẫn raise như cũ,
nên trend zone thật vẫn fallback sang Python thay vì bị âm thầm bỏ vẽ — đúng
yêu cầu "no silent visual omission" của `BOT-098F6`.

### Đã sửa test cũ, không phải nới lỏng nó

`test_script_regions_and_info_are_rejected` giờ truyền **nội dung thật** thay vì
`[]`. Assertion không mất đi — nó chuyển từ chỗ sai sang chỗ đúng: khẳng định
giới hạn thật (không có ABI background-region) thay vì khẳng định lời từ chối
với một lời gọi rỗng.

---

## Regression test

`tests/unit/presentation/ui/screens/test_bug037_native_empty_region_keeps_native_host.py`
— tầng Unit là đủ và đúng: lỗi nằm gọn trong logic thuần Python của adapter,
`NativeBacktestChartHost` được mock, không cần plugin native build sẵn.

6 test, phủ **cả hai nửa** của hợp đồng:

| Test | Khẳng định |
| :--- | :--- |
| `test_empty_spans_do_not_raise` | Đúng lời gọi mà mọi strategy không-trend-zone thực hiện mỗi lần chạy |
| `test_empty_info_fields_do_not_raise` | Tương tự cho `set_script_info` |
| `test_non_empty_spans_are_still_rejected` | **Giới hạn thật phải sống sót** |
| `test_non_empty_info_fields_are_still_rejected` | Tương tự |
| `test_an_empty_payload_draws_nothing_on_the_native_host` | "No-op" phải là no-op thật — không lén submit snapshot rỗng làm cháy generation token |
| `test_empty_payload_leaves_the_adapter_usable_for_real_work` | Sau lời gọi rỗng, dữ liệu chart thật vẫn lên được native — đúng thứ đã ngừng hoạt động |

**Xác nhận FAIL đúng lý do trước khi sửa** (`git stash` đúng file fix rồi chạy
lại):

```
E  NativeUnsupportedFeatureError: native script regions are not supported
E  NativeUnsupportedFeatureError: native script info is not supported
E  NativeUnsupportedFeatureError: native script regions are not supported
E  NativeUnsupportedFeatureError: native script regions are not supported
4 failed, 2 passed
```

4 fail đều là nhánh payload-rỗng; 2 test "vẫn phải từ chối" xanh sẵn từ đầu —
chứng minh test không chỉ đỏ, mà đỏ **đúng chỗ**. Sau khi khôi phục fix:
`6 passed`.

### Thêm 2 test ở tầng Presenter — bằng chứng end-to-end thật

Test unit ở trên chứng minh adapter, nhưng câu hỏi thật của bug là *"native
host có sống sót qua một lần chạy không"*. Hai test mới trong
[`test_backtest_presenter.py`](../../../tests/unit/presentation/ui/screens/test_backtest_presenter.py)
chạy với **`NativeBacktestChartHostAdapter` thật** (chỉ fake
`NativeBacktestChartHost` tầng dưới), rồi kiểm tra **kiểu thật của
`view.chart_cards[0]` sau thao tác** — kết quả quan sát được, không phải niềm
tin của người viết test:

| Test | Khẳng định |
| :--- | :--- |
| `test_empty_strategy_trend_zones_keep_the_native_host` | `_on_chart_strategy_region([])` → vẫn là `NativeBacktestChartHostAdapter` |
| `test_real_strategy_trend_zones_still_fall_back_to_python` | `_on_chart_strategy_region([span])` → thành `PythonBacktestChartHost` |

**Cố ý không dùng `Mock` card với `side_effect`** như test `BOT-113` sẵn có: một
mock như vậy chỉ khẳng định lại đúng cái niềm tin "adapter raise khi nào" của
người viết — mà chính niềm tin đó mới là thứ sai. Đây là bẫy `Mock` mà
`bug-fix-rule.md` §3 và `BUG-013` đã cảnh báo.

**Xác nhận đỏ đúng lý do** (`git checkout HEAD~1 -- <file adapter>`):

```
FAILED ... ::test_empty_strategy_trend_zones_keep_the_native_host
1 failed, 1 passed
```

Đúng hình dạng cần có: bảo đảm **mới** thì đỏ, bảo đảm **cũ** (fallback khi có
zone thật) vẫn xanh — fix không hề nới lỏng giới hạn thật. Khôi phục fix:
`175 passed`.

> **Ghi chú về quy trình:** lần đầu tôi thử revert bằng `git stash push <file>`
> sau khi đã commit fix — không có thay đổi chưa commit nên **không stash gì
> cả**, test "pass" và suýt bị đọc nhầm thành "test không tái hiện được bug".
> Phải dùng `git checkout HEAD~1 -- <file>` mới revert thật. Đây đúng là kiểu
> bẫy `bug-fix-rule.md` §3 nói tới: một test pass trước khi sửa **không chứng
> minh điều gì**, và lý do nó pass có thể chỉ là thao tác revert đã thất bại.

---

## Ghi chú

- Bug này lộ ra **chỉ vì user không tin kết luận trước đó** và bắt kiểm chứng
  lại. Kết luận "chart đang chạy Python" là đúng, nhưng lý do tôi đưa ra ban
  đầu ("strategy của bạn có trend zone") **sai** — strategy đó không hề có
  trend zone nào.
- Câu hỏi thứ hai của user cũng đúng một nửa: `BaseIndicatorScript.shade()`
  (`BOT-032`, docstring ghi *"Pine's `bgcolor`"*) **là** một background color
  API có thật và chạy được — nhưng chỉ trên đường Python. Native chưa từng có.
- **Chưa làm, cố ý:** không bổ sung ABI background-region cho native. Đó là mở
  rộng tính năng (`BOT-032` scope), không phải sửa lỗi — nên tách thành task
  riêng nếu muốn trend zone chạy được trên native.
