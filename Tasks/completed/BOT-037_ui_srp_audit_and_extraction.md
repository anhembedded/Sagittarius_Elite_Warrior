# Nhiệm vụ: SOLID/SRP audit cho `src/presentation/ui` — TRẠNG THÁI: HOÀN THÀNH (Phase 1 & Phase 2)

> **Đã hoàn thành ngày 10/08/2026.** Cả Phase 1 (tách SignalLogHandler + kline_mapping) và Phase 2 (tách StreamLifecycleController) đã được thực hiện, test suite xanh 100%, pass ruff check & ruff format.

## 1. Mục tiêu (Objective)

Yêu cầu gốc: `src/presentation/ui` không theo SOLID, cần tách nhiều file hơn. Sau khi audit thật,
hoá ra phần lớn codebase **đã** theo đúng SRP (xem §2). Mục tiêu thật của task này là tách **2 phần
còn sót, rủi ro thấp, không đụng code có bug đang theo dõi**:

1. `SignalLogHandler` (hiện là 1 class lồng trong `data_management_presenter.py`) → file riêng.
2. `_map_klines`/`_map_volume` (hiện là 2 `@staticmethod` trong `dashboard_presenter.py`) → module
   hàm thuần riêng.

Và tài liệu hoá quyết định "không tách" các phần còn lại (§3, §7) để không ai vô tình đề xuất lại.

## 2. Hiện trạng đã verify (đọc code thật 10/8/2026, không suy đoán)

### 2.1. `screens/dashboard/` — phần lớn ĐÃ tách rồi

File phẳng, không subfolder:

| File | Dòng | Trách nhiệm |
|---|---|---|
| `dashboard_presenter.py` | 1001 | Presenter — FSM, composition root, stream lifecycle (xem §2.3), background workers. |
| `indicator_script_runner.py` | 294 | Chạy custom indicator script cho 1 chart — SRP docstring tự giải thích tại sao tách. |
| `history_pagination_controller.py` | 125 | Debounce/cooldown cho load-more-on-scroll (BOT-035). SRP docstring tự giải thích. |
| `indicator_script_list_model.py` | 117 | `QAbstractListModel` cho checklist "CUSTOM SCRIPTS". |
| `autostart_controller.py` | 91 | Auto Start Live khi mở Dev Board (BOT-034). SRP docstring tự giải thích. |
| `dashboard_view_model.py` | 135 | ViewModel QML — state/signal thuần. |
| `dashboard_view.py` | 111 | View — hybrid QSplitter, không logic. |
| `script_region_tracker.py` | 61 | Sub-collaborator của `indicator_script_runner.py`. |

`autostart_controller.py`/`history_pagination_controller.py`/`indicator_script_runner.py` **chính
là** 3 collaborator mà đề xuất "services/" ban đầu định tách — đã tồn tại, đã có test, đã qua
production (2 trong số đó vừa được dùng để fix 1 bug crash thật + 1 bug vòng lặp vô hạn thật trong
phiên làm việc hôm nay). Tách lại vào 1 folder `services/` chỉ là dọn cosmetic — di chuyển file đã
chạy tốt, đổi import path ở mọi nơi gọi tới (production + test), rủi ro thật, lợi ích 0.

### 2.2. `components/*` — đã là ví dụ SOLID tốt, không cần đụng

`chart_card/` có **17 file `.py`**, mỗi file 1 trách nhiệm rõ (layout, candlestick paint, indicator,
volume, crosshair, viewport-follow, zoom UI, edge-scroll-detection, price-line, toolbar, theme, pure
transform...). `chart_card.py` (333 dòng) tự nhận trong docstring là "a thin orchestrator instead of
a God Object" — đúng nghĩa đen những gì task ban đầu yêu cầu. `sidebar/` cũng đã tách gọn 3 file.
Không có component nào hành xử như "mini-screen" (không có `*Presenter`, không FSM, không
background thread, không router awareness) — khớp đúng quy tắc trong `ui_architecture.md` §4/§9:
1 component chỉ "graduate" lên View/ViewModel/Presenter đầy đủ khi nó là **routed screen**, không
phải theo kích thước file. `Sidebar`/`ChartCard` bị loại tường minh khỏi bảng đó trong chính doc.

Ghi chú phụ (không thuộc scope refactor này): `components/chart_view/` chỉ còn `__pycache__/` rỗng
(toàn `.pyc`, không có `.py`, không có git history — tàn dư 1 thử nghiệm local bị bỏ dở, có vẻ từng
thử tách `ChartCard` thành `chart_presenter.py`/`chart_state.py` rồi không commit). An toàn để xoá,
nhưng đây là dọn rác, không phải SRP fix — không nằm trong scope task này, có thể xoá riêng bất cứ
lúc nào (`git status` xác nhận untracked).

### 2.3. `dashboard_presenter.py` (1001 dòng) — phần còn lại sau khi trừ 3 collaborator trên

| Phần | ~Dòng | Ghi chú |
|---|---|---|
| Import/const + `_tick_to_candle` | ~129 | Helper module-level, không phải method. |
| `__init__` (FSM table, composition root dựng 3 collaborator, WS badge init) | ~174 | Đúng vai trò presenter — composition root. |
| FSM wiring / WS badge | ~14 | Nhỏ, không cần tách. |
| Chart-card lifecycle (`_ensure_chart_cards`) | ~21 | Nhỏ, không cần tách. |
| Indicator orchestration glue (gọi vào `IndicatorScriptRunner`) | ~40 | Đã mỏng, không phải logic trùng lặp. |
| **Stream lifecycle Qt slots** (`_on_load_history`/`_on_start_stream`/`_on_stream_start_success`/`_on_stream_start_failed`/`_on_stop_stream`/`_on_timeframe_changed`) | ~180 | **Phần dồn cục nhất còn lại — xem §7, HOÃN.** |
| Background→main-thread signal slots (dispatch mỏng) | ~81 | Mỏng, không cần tách riêng. |
| Engine event bridge / live tick | ~68 | Gắn chặt FSM + autostart, không tách được mà không kéo theo cả 2. |
| **Background workers** (`_run_load_history`/`_run_load_more_history`/`_run_sync_and_start`) | ~222 | **Cùng nhóm với Stream lifecycle — HOÃN.** |
| `_map_klines`/`_map_volume` (`@staticmethod`) | ~31 | **An toàn, tách ngay — §5.2.** |

### 2.4. `data_management_presenter.py` (467 dòng) — vừa phải, 1 concern gọn

Chưa tách collaborator nào. Có 1 class lồng `SignalLogHandler(logging.Handler)` (dòng 41-70) — pure,
0 phụ thuộc state của presenter, constructor chỉ nhận `Signal` + tên logger → **an toàn tách ngay**
(§5.1). Phần còn lại (scan/sync/clear) là 1 concern tương đối đồng nhất (đều "thao tác DB"), 467
dòng chưa gây đau — **không nằm trong scope task này**, có thể xem xét sau nếu team muốn đồng bộ với
dashboard, không cấp bách.

### 2.5. `settings_presenter.py` (118 dòng) — đã tối giản, ngoài scope

6 method, không collaborator, không background thread phức tạp. Không cần đụng.

## 3. Quyết định đã chốt — KHÔNG re-litigate

1. **KHÔNG tạo `services/` subfolder ở bất kỳ screen nào.** Quy ước ĐANG chạy thật trong codebase là
   file phẳng, đặt tên theo trách nhiệm, ngay trong thư mục screen (`autostart_controller.py`,
   `history_pagination_controller.py`) — đã có SRP docstring riêng giải thích lý do tách. Thêm 1 lớp
   folder `services/` bọc ngoài không đổi gì về SOLID, chỉ đổi đường dẫn import + rủi ro conflict với
   `git blame`/lịch sử của 2 file vừa dùng để fix bug thật hôm nay.
2. **KHÔNG tạo `views/`/`view_models/`/`presenters/` subfolder trong bất kỳ screen nào.**
   `ui_architecture.md` không hề ghi quy ước này; quy tắc graduation duy nhất trong doc là "có phải
   routed screen hay không", không phải "mỗi layer 1 thư mục".
3. **KHÔNG đụng `components/*`.** Đã là ví dụ SOLID tốt sẵn (17 file trong `chart_card/`), không
   component nào hành xử như mini-screen theo đúng định nghĩa trong `ui_architecture.md`.
4. **KHÔNG đụng `settings/`.** Đã tối giản.
5. **HOÃN** tách "stream lifecycle" khỏi `dashboard_presenter.py` (điều kiện mở khoá ở §7) — dù đây
   là phần dồn cục nhất, code đang có race condition chưa fix (`BOT-027`) và 60+ dòng test white-box
   đang gate đúng phần này. Thiết kế đầy đủ vẫn được ghi lại ở §7 để làm sẵn khi được mở khoá — không
   cần thiết kế lại từ đầu lúc đó.
6. **CHỈ làm 2 việc an toàn ở §5** trong Phase 1 của task này: `SignalLogHandler` và
   `_map_klines`/`_map_volume`. Cả 2 đều 0 dependency vào state nhạy cảm, 0 liên quan `BOT-027`.

## 4. RULES — bắt buộc tuân thủ (quy ước dự án)

| # | Rule | Nguồn |
|---|---|---|
| **R1** | 1 concern = 1 file, đặt tên theo trách nhiệm, file phẳng ngay trong thư mục screen — KHÔNG bọc thêm folder `services/`/`views/`/`presenters/`. | §3 quyết định trên, khớp `autostart_controller.py`/`history_pagination_controller.py` |
| **R2** | Mỗi file/class tách ra PHẢI có docstring nêu rõ lý do tách (SRP) — theo đúng mẫu 3 file đã có (`autostart_controller.py`, `history_pagination_controller.py`, `indicator_script_runner.py`). | Quy ước dự án, đã verify trong 3 file trên |
| **R3** | Threading contract: worker nền chỉ `emit()`, mutation UI chỉ trong `@Slot` main-thread. Task này (Phase 1) KHÔNG đụng luồng thread nào — cả 2 phần tách đều là code thuần/logging, không có background-thread call. | `ui_architecture.md` §8 |
| **R4** | Dùng `../.venv/Scripts/python.exe` (từ repo root: `./.venv/Scripts/python.exe`), KHÔNG dùng `python` trần. | `BOT-032` §3 R9 |
| **R5** | Đừng chạy cả thư mục `tests/integration/presentation/ui/` bằng 1 lệnh — có crash pre-existing sau ~26 test/fixture cycle. Chạy theo nhóm file. Phase 1 của task này không chạm integration test nào cả (chỉ unit), nhưng nếu Phase 2 sau này được mở khoá thì áp dụng rule này. | `BOT-035` §6, `BOT-034` §9 |
| **R6** | `ruff check` và `ruff format --check` sạch trên mọi file đã sửa. | CI |
| **R7** | Giữ nguyên comment/docstring cũ nếu vẫn đúng sau khi sửa — không xoá, sửa cho khớp. | Quy ước dự án |
| **R8** | KHÔNG dùng lambda cho việc binding callback có state/dài hạn trong code production — dùng `functools.partial` hoặc method đặt tên rõ. (Không áp dụng cho lambda ngắn trong test.) | Quy ước dự án, đã áp dụng trong `history_pagination_controller.py` hôm nay |

## 5. Phase 1 — thiết kế chi tiết (làm ngay)

### 5.1. `SignalLogHandler` → file riêng

**File mới:** `src/presentation/ui/screens/data_management/signal_log_handler.py`

Copy nguyên class từ `data_management_presenter.py` dòng 41-70 — KHÔNG đổi logic, chỉ đổi vị trí:

```python
from __future__ import annotations

import logging

from PySide6.QtCore import Signal


class SignalLogHandler(logging.Handler):
    """
    @brief Bridges standard Python logging to a Qt Signal for UI display.

    @details
    Handlers attached to the app-wide "App" logger outlive the screen that
    installed them, so once that screen's C++ object is deleted the bound
    signal raises RuntimeError — and because every `App.*` logger propagates
    here, a single dead screen would break logging for the WHOLE app
    (originally surfaced as unrelated icon-loading tests failing, since
    IconLoader logs a warning through `App.IconLoader`).

    Detaching on the first such failure keeps that blast radius at zero.
    """

    def __init__(self, signal: Signal, logger_name: str = "App") -> None:
        super().__init__()
        self.signal = signal
        self._logger_name = logger_name
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.signal.emit(self.format(record))
        except RuntimeError:
            self.detach()

    def detach(self) -> None:
        """Removes this handler from its logger. Safe to call twice."""
        logging.getLogger(self._logger_name).removeHandler(self)
```

**`data_management_presenter.py`:**
- Xoá class `SignalLogHandler` (dòng 41-70).
- Xoá `import logging` NẾU không còn chỗ nào khác trong file dùng `logging` trực tiếp (kiểm tra bằng
  `grep -n "logging\." src/presentation/ui/screens/data_management/data_management_presenter.py`
  trước khi xoá import — có thể còn dùng ở chỗ khác, đừng xoá mù).
- Thêm `from .signal_log_handler import SignalLogHandler` vào đầu file.
- KHÔNG đổi gì ở dòng 116-117 (chỗ khởi tạo `self._log_handler = SignalLogHandler(...)`) — chỉ đổi
  nguồn import, hành vi giữ nguyên 100%.

**Test:** `grep -rn "SignalLogHandler" tests/` — hiện chỉ có 1 dòng COMMENT nhắc tên trong
`tests/unit/presentation/ui/screens/test_data_management_presenter.py:286`, không import theo path
→ **không cần sửa test nào**. Chạy lại
`tests/unit/presentation/ui/screens/test_data_management_presenter.py` để xác nhận (đặc biệt test
ở dòng ~286, tên đại loại "regression test: SignalLogHandler is attached to the app-wide App logger"
— đọc kỹ trước khi chạm, đây là regression test cho đúng bug đã tả trong docstring ở trên).

### 5.2. `_map_klines`/`_map_volume` → module hàm thuần riêng

**File mới:** `src/presentation/ui/screens/dashboard/kline_mapping.py`

```python
from __future__ import annotations


def map_klines(klines: list) -> list:
    """
    @brief Converts a list of MarketData entities to the
    (t, o, h, l, c) tuple format expected by FastCandlestickItem.
    """
    return [
        (
            float(item.close_time.timestamp()),
            float(item.open_price),
            float(item.high_price),
            float(item.low_price),
            float(item.close_price),
        )
        for item in klines
    ]


def map_volume(klines: list) -> list:
    """
    @brief Converts a list of MarketData entities to the
    (t, volume, is_bullish) tuple format expected by VolumeItem.
    """
    return [
        (
            float(item.close_time.timestamp()),
            float(item.volume),
            item.close_price >= item.open_price,
        )
        for item in klines
    ]
```

Pure functions, không phải `@staticmethod` nữa (không có lý do giữ trong 1 class khi tách file
riêng) — đặt tên bỏ tiền tố `_` vì giờ là API công khai của module riêng.

**`dashboard_presenter.py`:**
- Xoá 2 `@staticmethod` `_map_klines`/`_map_volume` (dòng 970-1001).
- Thêm `from .kline_mapping import map_klines, map_volume` vào đầu file.
- Đổi **cả 3 call site** (dòng 817-818, 891-892, 943-944 — verify lại số dòng thật lúc code, có thể
  đã lệch do các sửa trước đó trong phiên) từ `self._map_klines(...)`/`self._map_volume(...)` thành
  `map_klines(...)`/`map_volume(...)` (bỏ `self.`).

**Test — BẮT BUỘC sửa, đây là điểm dễ quên nhất:**
`tests/unit/presentation/ui/screens/test_dashboard_presenter.py` dòng ~652-653 gọi
`presenter._map_klines(older)`/`presenter._map_volume(older)` — 2 method này SẼ KHÔNG CÒN TỒN TẠI
trên `presenter` sau khi tách. Sửa thành:
```python
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.kline_mapping import (
    map_klines,
    map_volume,
)

...
mapped = map_klines(older)
volume = map_volume(older)
```
(thêm import ở đầu file test, cạnh các import khác). Cũng sửa docstring của `_make_full_kline`
(dòng ~505-508, hiện viết "since those two are @staticmethod...") cho khớp — không còn là
`@staticmethod` nữa, là module-level function.

## 6. Test gate (Phase 1)

```bash
# Từ repo root (Sagittarius_ForkBoy)
PYTHONPATH=. ./.venv/Scripts/python.exe -m pytest \
  Sagittarius_Elite_Warrior/tests/unit/presentation/ui/screens/test_dashboard_presenter.py \
  Sagittarius_Elite_Warrior/tests/unit/presentation/ui/screens/test_data_management_presenter.py -q

./.venv/Scripts/python.exe -m ruff check \
  Sagittarius_Elite_Warrior/src/presentation/ui/screens/dashboard/dashboard_presenter.py \
  Sagittarius_Elite_Warrior/src/presentation/ui/screens/dashboard/kline_mapping.py \
  Sagittarius_Elite_Warrior/src/presentation/ui/screens/data_management/data_management_presenter.py \
  Sagittarius_Elite_Warrior/src/presentation/ui/screens/data_management/signal_log_handler.py \
  Sagittarius_Elite_Warrior/tests/unit/presentation/ui/screens/test_dashboard_presenter.py

./.venv/Scripts/python.exe -m ruff format --check <cùng list file trên>
```

Không cần chạy integration test cho Phase 1 — cả 2 thay đổi đều thuần logic/logging, không đụng
threading/signal timing. Nếu muốn chắc chắn tuyệt đối, chạy thêm
`tests/integration/presentation/ui/test_dashboard_integration.py` (nhóm nhỏ, nhanh) — không bắt buộc.

## 7. Phase 2 — StreamLifecycleController (HOÃN — chỉ làm khi được yêu cầu tường minh)

**Điều kiện mở khoá** (1 trong 2, phải có xác nhận rõ ràng từ người dùng trước khi bắt đầu):
- `BOT-027` (race condition trong `_run_load_history`/`IndicatorScriptRunner.feed_all` đọc
  `self._script_runner.active` tại thời điểm CALL chứ không phải SUBMIT — xem docstring đầu file
  `tests/integration/presentation/ui/test_dev_board_async_race_conditions.py`) đã được fix và có
  test xanh xác nhận, HOẶC
- Có nhu cầu thật thứ 2 xuất hiện (1 bug cụ thể cần tách file này mới sửa an toàn được, hoặc 2 người/
  2 task AI thật sự bị block vì cùng sửa `dashboard_presenter.py` cùng lúc) — không phải chỉ vì
  "file dài".

**Không tự ý bắt đầu Phase 2 khi làm Phase 1.** Nếu Phase 2 được mở khoá sau này, đây là thiết kế đã
chuẩn bị sẵn (không cần audit lại từ đầu):

- **Tên file/class:** `stream_lifecycle_controller.py` / `StreamLifecycleController`. KHÔNG đặt tên
  `StreamService`/`LiveStreamController` — trùng khái niệm domain-layer đã có sẵn
  (`ILiveStreamService`, `LiveStreamAdapter`, `StreamCliHandler` ở tầng application/infrastructure/cli
  khác hẳn tầng UI) → sẽ gây nhầm lẫn thật khi tìm kiếm code.
- **Method di chuyển:** `_on_load_history`, `_on_start_stream`, `_on_stream_start_success`,
  `_on_stream_start_failed`, `_on_stop_stream`, `_on_timeframe_changed`, `_run_load_history`,
  `_run_sync_and_start`, `_map_klines`/`_map_volume` (nếu Phase 1 chưa tách riêng thì gộp luôn vào
  đây), và **`_run_load_more_history`** — đặt CÙNG file này chứ KHÔNG đặt vào
  `history_pagination_controller.py`, vì chính docstring của `HistoryPaginationController` đã tự nêu
  rõ "does not know how to fetch or render anything" — giữ đúng ranh giới đó.
  `_on_near_left_edge`/`_recheck_edge`/`_fetch_older_history` giữ nguyên trong
  `DashboardPresenter` — đó là seam có sẵn của `HistoryPaginationController`, không đụng.
- **Constructor cần inject ~12-15 collaborator** (nhiều hơn hẳn 2 controller hiện có, vì state dùng
  chung với luồng live-tick không thể tách rời hoàn toàn): `thread_manager`, `dispatcher`, `config`,
  `fsm`, các callback tới `view_model` (`historyLoading`/`set_history_loading`/`log_model.append`),
  `script_runner`, dict `raw_klines_by_symbol` (reference dùng chung, KHÔNG copy), getter/setter cho
  `active_interval`, `ensure_chart_cards`, `rebuild_scripts`, `compute_fetch_limit`, cặp
  getter/reset cho cancellation token, và các callable `.emit` (không phải `Signal` object) cho
  `ui_history_reloaded_signal`/`ui_history_load_finished_signal`/`ui_stream_success_signal`/
  `ui_stream_failed_signal`/`ui_log_signal` — theo đúng mẫu `indicator_script_runner.py` đã dùng
  (truyền callable `.emit`, không truyền `Signal` object, để thứ tự connect trong
  `_connect_ui_signals()` không đổi).
- **Test cần giữ nguyên qua forwarder, KHÔNG viết lại:** `test_dashboard_presenter.py` có ≥10 dòng
  assert identity/gọi trực tiếp kiểu `assert submit_args[0] == presenter._run_load_history` hay
  `presenter._run_load_history(...)` gọi thẳng — để không phải viết lại toàn bộ (rủi ro đổi hành vi
  bug `BOT-027` đang được test này canh), `DashboardPresenter` phải giữ 1 attribute cùng tên
  (`self._run_load_history = self._stream.run_load_history` trong `__init__`, hoặc method forwarder
  1 dòng) cho MỖI method bị di chuyển mà có test identity-check kiểu này. Đọc kỹ
  `test_dashboard_presenter.py` (grep `_raw_klines_by_symbol`, `_cancellation_token`,
  `_active_interval`, `active_charts`, `_run_load_history`, `_run_sync_and_start`,
  `_run_load_more_history`) TRƯỚC khi di chuyển bất kỳ method nào.
- **Test gate khi Phase 2 chạy:** unit đầy đủ + CHẠY RIÊNG TỪNG FILE (không gộp, theo R5):
  `test_dashboard_integration.py`, `test_dashboard_live_stream.py`,
  `test_dev_board_async_race_conditions.py`, `test_dev_board_load_more.py`,
  `test_dev_board_known_gaps.py` — đặc biệt `test_dev_board_async_race_conditions.py` phải xanh
  TRƯỚC và SAU refactor với cùng seed/thứ tự, để chứng minh hành vi (kể cả hành vi bug, nếu
  `BOT-027` vẫn chưa fix) không đổi.

## 8. Ngoài phạm vi — đã cân nhắc và LOẠI (không tái đề xuất)

- `services/` subfolder trong bất kỳ screen nào — §3.1.
- `views/`/`view_models/`/`presenters/` subfolder trong bất kỳ screen nào — §3.2.
- Tách/restructure `components/*` — §3.3.
- Đụng `settings/` — §3.4.
- Tách "scan/sync/clear" trong `data_management_presenter.py` thành collaborator riêng — không cấp
  bách (467 dòng, 1 concern tương đối đồng nhất), có thể xem xét sau nếu cần đồng bộ pattern với
  dashboard, KHÔNG thuộc scope task này.
- Xoá `components/chart_view/__pycache__` — an toàn nhưng là dọn rác, không phải SRP fix, làm riêng
  bất cứ lúc nào không cần task này.

## 9. Phụ thuộc (Dependencies)

- `BOT-034` ✅, `BOT-035` ✅, `BOT-036` ✅ — 3 collaborator hiện có (`autostart_controller.py`,
  `history_pagination_controller.py`, `indicator_script_runner.py`) là sản phẩm của các task này,
  chính là bằng chứng cho §3.
- `BOT-027` (trạng thái: chưa fix, xem `test_dev_board_async_race_conditions.py`) — điều kiện mở
  khoá Phase 2, xem §7.
