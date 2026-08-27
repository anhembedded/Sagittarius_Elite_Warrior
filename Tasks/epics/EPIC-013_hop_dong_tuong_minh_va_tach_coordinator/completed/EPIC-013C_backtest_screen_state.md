# EPIC-013C — `IBacktestScreenState`: gom 17 accessor về 1 tham số

**Trạng thái:** ✅ Xong 2026-08-27
**Repo:** Elite
**Phụ thuộc:** `A`, `B`

## Kết quả đo

| | Trước | Sau |
| :--- | ---: | ---: |
| Tổng tham số ctor của 6 Coordinator | **74** | **63** |
| Lambda getter/setter dựng trong `factory.py` | 17 | 0 |

| Coordinator | Trước | Sau |
| :--- | ---: | ---: |
| `execution_coordinator.py` | 19 | 17 |
| `chart_render_coordinator.py` | 20 | 16 |
| `indicator_coordinator.py` | 12 | 10 |
| `strategy_config_coordinator.py` | 9 | 6 |
| `data_sync_coordinator.py` | 9 | 9 |
| `trade_log_coordinator.py` | 5 | 5 |

Hai cái cuối không đổi **số** vì mỗi cái chỉ bỏ đúng 1 accessor và nhận lại
`state` — nhưng vẫn đúng hướng: tham số mất tên mơ hồ (`get_symbol`) và có
kiểu.

> README của epic ước tính **56** dựa trên 24 accessor. Đo lại từng tham số
> thì chỉ **17** trong số đó là state thật; 7 cái còn lại (`get_first_chart_card`,
> `next_preview_id`, `get_current_config`, `is_busy`, `effective_data_interval`,
> `get_market_metadata`, `get_chart_mode`) **không phải giá trị màn hình đang
> giữ** — xem dưới. Con số đúng là **63**, và ước tính cũ đã sửa ở README.

## Cái gì KHÔNG vào `IBacktestScreenState` — và vì sao

| Bị loại | Lý do |
| :--- | :--- |
| `get_first_chart_card` | Phải giữ là **lời gọi**. `BUG-013`: card cached thành C++ object đã `deleteLater()` sau khi host dựng lại |
| `next_preview_id` | Là **hành động** — tăng counter rồi trả về, không phải đọc giá trị |
| `get_current_config` | **Tính** từ ViewModel mỗi lần gọi |
| `is_busy` | Tính từ FSM |
| `effective_data_interval` | Tính |
| `get_market_metadata` | Tra cache, **nhận tham số** |
| `get_chart_mode` | State của **View**, không phải của Presenter — đã vào `IBacktestView` ở commit trước |

Ranh giới này chính là thứ giữ cho port không phình thành "chỗ để mọi callable".

## ABC, không phải Protocol — và lần này nó bắt lỗi thật

`IBacktestScreenState` là `abc.ABC` theo đúng thứ tự chọn của §2.1: không có
gì ở đây chạm Qt, nên không rơi vào ngoại lệ nào cho phép `Protocol`.

Nó **trả công ngay trong lúc làm task này**. Bản `InMemoryScreenState` đầu tiên
trong `conftest.py` chỉ có annotation (`symbol: str`) mà không gán giá trị. Kết
quả:

```
TypeError: Can't instantiate abstract class InMemoryScreenState without an
implementation for abstract methods 'active_preview_id',
'active_strategy_lines', 'all_trades', ...
```

`abc` tìm một **binding** trong class namespace; annotation không tạo binding
nào. Một `Protocol` sẽ **im lặng chấp nhận** cái class đó, và ở tầng
`presentation/` — nơi `mypy` không chạy — sẽ không có gì báo. Đây đúng cảnh báo
"Protocol không phải lối thoát khỏi tính đầy đủ" của §2.1, gặp trong thực tế
sau chưa đầy một ngày.

## Đọc muộn — verify bằng bơm lỗi

`PresenterBackedScreenState` đọc thẳng presenter **tại thời điểm truy cập**,
không chụp lúc `__init__`. `EPIC-003E` đã dính lỗi ngược lại 4 lần.

**Bơm lỗi:** cho `all_trades` chụp giá trị trong `__init__`
(`self._captured_all_trades = presenter._all_trades`) →
**10 test đỏ** trong `test_backtest_presenter.py` +
`test_backtest_timezone_presenter.py`. Khôi phục → **164/164 xanh**.

## Một `InMemoryScreenState` dùng chung, không phải 6 fake

`tests/.../coordinators/conftest.py` giữ **một** implementation cho cả 6 file
test. Lý do là luật ABC-completeness ở §2: một test double tự chế cho mỗi file
sẽ **tụt lại phía sau** khi port đổi, và tụt lặng lẽ. Với ABC + một chỗ duy
nhất thì port đổi là `TypeError` ngay ở test đầu tiên, và chỉ có một chỗ để sửa.

`_State` của `test_strategy_config_coordinator.py` giờ **kế thừa** nó và chỉ
thêm hai thứ *không phải* state màn hình (`metadata` tra theo symbol,
`config_changed` đếm thông báo) — ranh giới ở trên, áp vào test.

## Nghiệm thu

- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`, log quét
  sạch `FAILED|ERROR|Traceback|ResourceWarning`.
- Bơm lỗi early-binding → 10 test đỏ, khôi phục → xanh.
- `ruff` bắt thêm một lỗi thật lúc làm: `RUF012` mutable class attribute — 3 list
  mặc định ở cấp class sẽ **dùng chung giữa mọi instance**, tức kline của test
  này lọt sang test sau. Đã đổi placeholder sang `None`.
