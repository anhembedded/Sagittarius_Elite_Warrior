# EPIC-012 — Hợp đồng tường minh (cấm duck-typing ngầm) & tách nốt Coordinator

**Trạng thái:** 🟡 Đang làm (1/7 task con xong)
**Loại:** Kiến trúc / luật + tái cấu trúc tầng Presentation
**Nguồn:** User chốt trực tiếp 2026-08-27 — *"updat rule code strickly no
duck-typed. use abstract or interface class"*, *"ko thay view runtime, cho load
view tu config luc bootstrap"*, và duyệt 4 đề xuất tách file đo được ở cuối
`EPIC-003E`.

---

## 1. Vì sao epic này tồn tại

`EPIC-003E` rút 6 Coordinator ra khỏi `BackTestPresenter` (2135 → 1861 dòng).
Việc đó **đúng theo Single Responsibility**, nhưng lúc đo lại kết quả thì lộ ra
hai thứ mà bản thân việc tách không sửa được:

1. **Hợp đồng Presenter ↔ View chưa bao giờ được khai báo.** Presenter + 6
   Coordinator gọi **15 thành viên** của `view` mà không có kiểu nào nói chúng
   tồn tại. `BasePresenter.__init__(self, view, container)` của Engine để `view`
   **không có annotation**. Engine *có* `IView`, nhưng nó khai đúng 1 method
   `bind()` — **không View nào trong cả hai repo implement**, và `src/` của repo
   này tham chiếu `IView` **0 lần**.
2. **Constructor phình vì truyền state qua callable.** 6 Coordinator nhận tổng
   **74 tham số**, trong đó **24 tham số là accessor đọc/ghi state của
   Presenter** (`get_symbol` xuất hiện ở 4 nơi, `get_current_raw_klines` ở 2,
   `get_active_strategy_lines` ở 2, …). Đây là vi phạm Interface Segregation
   **do cách truyền**, không phải do trách nhiệm sai.

Hai thứ này là **cùng một bệnh**: thứ đi qua ranh giới không có kiểu đại diện,
nên nó trôi mà không có gì vỡ ra — đúng cơ chế mà
[`architecture-rule.md`](../../../.agents/rules/architecture-rule.md) §7 đã đặt
tên (*"Code phải tự nói lên chính nó"*).

## 2. Số đo, ngày 2026-08-27

### 2.1 Hợp đồng View ngầm — 15 thành viên

```bash
grep -rhoE "(self\.)?_?view\.[a-zA-Z_]+" src/presentation/ui/screens/backtest/ \
  | sed -E 's/.*view\.//' | sort -u
```

`chart_cards`, `chart_controls`, `render_symbol_cards`, `resize`,
`set_view_model`, `set_chart_mode`, `set_chart_host_factory`,
`set_chart_dev_mode`, `set_chart_opengl_enabled`,
`set_chart_cached_interaction_enabled`, `set_display_timezone`,
`set_volume_visible`, `set_trade_flags_visible`, `on_preview_data_ready`,
`on_backtest_data_ready`.

Khai báo hiện có: **0**.

### 2.2 74 tham số constructor, 24 trong đó là accessor state

| Coordinator | Dòng | Tham số ctor | Trong đó là accessor state |
| :--- | ---: | ---: | ---: |
| `execution_coordinator.py` | 357 | 19 | 3 |
| `chart_render_coordinator.py` | 271 | 20 | 8 |
| `indicator_coordinator.py` | 256 | 12 | 5 |
| `strategy_config_coordinator.py` | 246 | 9 | 5 |
| `data_sync_coordinator.py` | 205 | 9 | 2 |
| `trade_log_coordinator.py` | 108 | 5 | 1 |
| **Tổng** | **1443** | **74** | **24** |

Gom 24 accessor đó về **một** value object `BacktestScreenState` (mỗi
Coordinator nhận đúng 1 tham số `state`) → **74 → 56**.

### 2.3 Hai Coordinator còn quá ngưỡng ISP

- `chart_render_coordinator.py`: 20 tham số / 9 method công khai. Nhánh
  **preview** sở hữu **10 dependency mà không ai khác dùng** (`is_busy`,
  `next_preview_id`, `get_active_preview_id`, `emit_preview_ready`,
  `run_preview_worker`, `get_current_config`, …) — nó là một Coordinator riêng
  đang trốn bên trong.
- `execution_coordinator.py`: 357 dòng / 19 tham số. Nhánh **chart data feed**
  (`emit_chart_data_ready`, `emit_strategy_indicator_lines`,
  `emit_strategy_trend_zones`, `get_chart_script_keys`,
  `get_chart_klines_fetch_limit`) tách được khỏi nhánh chạy backtest thật.

Cả hai đều **chưa** chạm ngưỡng cứng >400 dòng của
[`architecture-rule.md`](../../../.agents/rules/architecture-rule.md) §5.4,
nhưng §5 nói rõ *"chia nhỏ là mặc định, càng nhiều file càng tốt; tách thì không
cần xin phép"* — và user đã chốt lại đúng câu đó ngày 2026-08-27.

## 3. Hai quyết định của user, ghi nguyên văn để lần sau không đọc lệch

### 3.1 "Strictly no duck-typed" nghĩa là cấm **hợp đồng ngầm**, không phải cấm `Protocol`

Đọc theo nghĩa đen ("cấm structural typing") thì **mâu thuẫn với code đang
chạy** — đã nêu với user trước khi viết luật, và user chốt cách hiểu dưới đây:

| Bằng chứng chống lại cách đọc nghĩa đen | Đo được |
| :--- | :--- |
| `typing.Protocol` đang dùng thật | 9 ở `src/` repo này + 9 ở Engine |
| `LogModel`, `ITab`, `IStateContributor`, `IBacktestChartHost` | implementer đều là subclass `QObject`; `ABCMeta` xung đột metaclass với Shiboken → **không thể** thành ABC |
| `kit/style.py` module docstring | *"PySide6/Shiboken forbids a class inheriting two QObject-derived bases"* — chính lý do `apply_role()` là composition |
| `architecture-rule.md` §2 | đã cấm sẵn multiple inheritance |
| Engine `.agents/rules/architecture.md` | cả hệ extension xây trên narrow context Protocol (`IExtension[ILoggerContext]`) |

Luật đã viết: [`architecture-rule.md`](../../../.agents/rules/architecture-rule.md)
**§2.1** — *ABC là mặc định; `Protocol` chỉ khi kế thừa bất khả thi (QObject /
multiple-inheritance / class bên thứ ba), và docstring phải ghi lý do thuộc
nhóm nào.*

### 3.2 View chọn lúc bootstrap từ config, **không** thay lúc runtime

Presenter **không** phải chịu được việc bị tráo View giữa chừng. Điều này
**không** làm hợp đồng bớt cần tường minh — lý do khai `IBacktestView` là để
consumer lập trình vào được và `mypy` kiểm được.

Hệ quả cấm: Coordinator/Presenter **không được cache widget con** rồi giả định
nó bất biến — [`BUG-013`](../../bug_report/completed/BUG-013.md) đã cho thấy một chart
card cached trở thành C++ object đã `deleteLater()` sau khi host dựng lại. Bất
biến ở đây là *danh tính View*, không phải *widget bên trong nó*.

## 4. Task con

| ID | Việc | Trạng thái |
| :--- | :--- | :---: |
| [`EPIC-012A`](completed/EPIC-012A_rule_hop_dong_tuong_minh.md) | Viết luật §2.1 vào `architecture-rule.md` + dòng trỏ ở `CLAUDE.md` | ✅ Xong |
| [`EPIC-012B`](incomplete/EPIC-012B_ibacktestview_contract.md) | Khai `IBacktestView` — 15 thành viên, annotate Presenter + 6 Coordinator | ⬜ Chưa |
| [`EPIC-012C`](incomplete/EPIC-012C_backtest_screen_state.md) | `BacktestScreenState` — gom 24 accessor về 1 tham số, 74 → 56 | ⬜ Chưa |
| [`EPIC-012D`](incomplete/EPIC-012D_tach_chart_preview_coordinator.md) | Tách `ChartPreviewCoordinator` khỏi `chart_render` (10 dep độc quyền) | ⬜ Chưa |
| [`EPIC-012E`](incomplete/EPIC-012E_tach_chart_feed_coordinator.md) | Tách `ChartFeedCoordinator` khỏi `execution` (357 → ~250 dòng) | ⬜ Chưa |
| [`EPIC-012F`](incomplete/EPIC-012F_view_tu_config_luc_bootstrap.md) | Chọn View từ config lúc bootstrap, có kiểu đại diện | ⬜ Chưa |
| [`EPIC-012G`](incomplete/EPIC-012G_timeframe_fallback_attributeerror.md) | Sửa `TimeFrame.M1` — chính nhánh fallback đang ném `AttributeError` | ⬜ Chưa |

Thứ tự bắt buộc: **`B` và `C` trước `D`/`E`** — tách tiếp khi chưa có kiểu đại
diện là nhân bản thêm tham số ngầm. `G` độc lập, làm lúc nào cũng được.

## 5. Điều kiện nghiệm thu (user chốt)

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`, **cộng**
tuân thủ [`commit-rule.md`](../../../.agents/rules/commit-rule.md).
**Không** phụ thuộc GitHub Actions.

Riêng epic này thêm một điều kiện nữa, vì nó là epic về hợp đồng: mỗi task tách
file phải **chứng minh test bắt được lỗi** — bơm lỗi vào đúng chỗ vừa tách, xác
nhận đúng test đỏ, rồi mới gỡ. `EPIC-003E` đã bắt 4 lần lỗi early-binding
(capture thuộc tính Presenter lúc dựng Coordinator, trong khi test thay nó
*sau đó*) đúng bằng cách này — không lần nào phát hiện được bằng mắt.
