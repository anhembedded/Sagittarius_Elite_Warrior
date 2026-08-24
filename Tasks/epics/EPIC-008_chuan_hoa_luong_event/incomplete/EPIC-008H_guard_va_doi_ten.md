# EPIC-008H — Elite: 5 guard máy kiểm được + đổi tên nói đúng sự thật

**Thuộc:** [`EPIC-008`](../README.md) · **Repo:** `Sagittarius_Elite_Warrior` · **Trạng thái:** 🔵 Chưa làm
**Phụ thuộc:** `008F`, `008G`

---

## 1. Năm guard

Mọi luật của epic này phải máy kiểm được, không phải lời hứa. Mẫu tham chiếu: Engine đã dùng
`import_boundary.SANCTIONED_DEEP_IMPORTS` cho đúng kiểu việc này.

| # | Luật | Cách đo |
| :-: | :--- | :--- |
| 1 | Định danh sự kiện bằng **lớp**, không bằng chuỗi | Cấm `event_bus.on("...")` và `on(X.event_name, ...)` trong `src/`. Ngoại lệ có ghi lý do: 13 sự kiện engine chỉ có tên chuỗi |
| 2 | Domain/Application không chạm engine, trừ Shared Kernel | Danh sách trắng đúng 2 ký hiệu (`008F`) |
| 3 | Mọi lớp trong `EventRegistry` phải có ≥1 subscriber | hoặc nằm trong danh sách "cố ý chưa nghe" **có ghi lý do** |
| 4 | `EVENT_CATALOG.md` khớp registry | test so khớp (`008B`) |
| 5 | Presenter không khai báo `Signal` chỉ để nhảy luồng | không `Signal` nào được `emit()` từ trong một handler của event bus |

Guard 3 là thứ chặn tái diễn nguyên nhân gốc mà user đã chỉ ra: *"chắc do design kiểu gì mà
khi AI code, design không hình dung được điều đó"* — `safe_ui_action` phát sự kiện và **giả
định** sẽ có người nghe, nhưng không có gì bắt buộc. Guard 3 biến giả định đó thành ràng buộc.

## 2. Đổi tên `RunRealtimeBacktestCommand`

Tên hiện tại **nói dối về tính năng**. `backtest_fsm_matrix.py:83-86` ghi rõ: `HISTORICAL_TICK`
chỉ replay dữ liệu **lịch sử** ở độ phân giải tick, còn *"real-time bar tick (live trading, not
backtest) are separate, not-yet-built modes"*. Backtest **không có** tính năng dữ liệu live.

Cái tên này đã suýt gây một lỗi thật trong chính lần rà soát này: nó làm việc định tuyến
`MarketTickEvent` sang Backtest trông hợp lý. User bắt được.

Đổi:

| Cũ | Mới |
| :--- | :--- |
| `RunRealtimeBacktestCommand` | `RunHistoricalTickBacktestCommand` |
| `RunRealtimeBacktestCommandHandler` | `RunHistoricalTickBacktestCommandHandler` |
| `application/use_cases/backtest/run_realtime_backtest/` | `.../run_historical_tick_backtest/` |

`git mv` để giữ lịch sử. Rà mọi call-site (`binance_bot_module.py:28,220`,
`backtest_presenter.py:25,2258,2276,2282`, `backtest_view_model.py:523`,
`backtest_fsm_matrix.py:83`) — kể cả trong comment và docstring (`doc-code-sync.md`).

## Bằng chứng phải nộp

- Mỗi guard chạy thật: cố tình vi phạm → CI đỏ. Dán output cho **cả 5**.
- `grep -rn "RunRealtimeBacktest" src/ tests/` → rỗng.
- `pwsh -NoProfile -File scripts/ci-local.ps1` — `RESULT: PASS`, số test không đổi.

## Rủi ro

Guard 5 là cái khó đo nhất — "signal chỉ để nhảy luồng" không có dấu hiệu cú pháp tuyệt đối.
Nếu không viết được phép đo tin cậy, **thà bỏ guard 5 và ghi lý do** còn hơn ship một guard
báo sai: một guard hay false-positive sẽ bị người ta tắt đi, và khi đó nó tệ hơn không có.
