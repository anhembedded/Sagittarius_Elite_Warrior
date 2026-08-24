# EPIC-008G — Elite: 3 Feed dùng chung, xoá 48 signal cầu nối

**Thuộc:** [`EPIC-008`](../README.md) · **Repo:** `Sagittarius_Elite_Warrior` · **Trạng thái:** 🔵 Chưa làm
**Phụ thuộc:** `008C`, `008D`, `008E`, `008F`

---

## Phạm vi

Đây là task hiện thực nguyên tắc nền của epic: **một sự kiện có đúng MỘT nơi xử lý, nhiều nơi
hiển thị.**

### 1. Ba Feed, mỗi cái một file trong `presentation/ui/common/`

| Feed | Nghe | Ai hiển thị | Thay cho |
| :--- | :--- | :--- | :--- |
| `SystemErrorFeed` | `UiActionFailedEvent`, `runtime.tasks.failed` | mọi màn | **không ai** — hiện 0 subscriber, lỗi chảy vào hư không |
| `HealthFeed` | `HealthUpdatedEvent` | Backtest + Dashboard | 2 bản `_trigger_initial_health_check()` + 3 bản định dạng |
| `SyncProgressFeed` | `SingleSyncProgressEvent` | Backtest + DataMgmt | 2 handler độc lập |

`SystemErrorFeed` là thứ user yêu cầu *"phải hoạt động trở lại"*. `safe_ui_action` phát một sự
kiện có cấu trúc kèm traceback đầy đủ và docstring của nó còn ghi rõ *"subscribe via
`event_bus.on(UiActionFailedEvent, handler)`"* — nhưng không có gì trong thiết kế **bắt buộc**
điều đó, nên chưa ai làm. Guard ở `008H` là thứ chặn tái diễn.

### 2. Xoá 48 signal cầu nối

| Presenter | Số `Signal` | Quy ước |
| :--- | ---: | :--- |
| `backtest_presenter.py` | 22 | `_camelCaseSignal` |
| `data_management_presenter.py` | 14 | `ui_snake_case_signal` |
| `dashboard_presenter.py` | 12 | `ui_snake_case_signal` |

Handler đăng ký qua `QtEventBridge` (`008D`) đã ở main thread ⇒ cầu nối không còn lý do tồn tại.

**Ranh giới phải giữ:** chỉ xoá signal **cầu nối luồng**. Signal mang **ngữ nghĩa UI thật**
(`view_model → view`) giữ nguyên — hai loại này đang bị trộn lẫn, tách chúng ra là một phần
việc của task này. Tiêu chí phân biệt: một signal chỉ tồn tại để chuyển luồng thì nơi
`emit()` nó là một handler của event bus (hoặc một callback worker), và slot nhận không làm gì
ngoài chuyển tiếp.

### 3. Payload thành dataclass

| Hiện tại | Sau |
| :--- | :--- |
| `ui_status_table_signal = Signal(str, str, str, str, str, str)` | `Signal(object)` mang `StatusRowUpdate` |
| `ui_gap_inspector_signal = Signal(str, str, int, int, float, list, list)` | `Signal(object)` mang `GapInspectorPayload` |
| `_backtestProgressSignal = Signal(int, str, int, int, float)` | `Signal(object)` mang `BacktestProgress` |

Đặt ở `<screen>_signal_payloads.py` cạnh presenter. `@dataclass(frozen=True)`. `code-rule.md`
§1 yêu cầu dataclass thay cấu trúc thô — 6 chuỗi vị trí còn tệ hơn dict: hoán nhầm 2 cột là lỗi
thầm lặng mà mypy không bắt được.

### 4. `main.py` dựng bus có logger thật

Sau `008C`, `MemoryEventBus` nhận logger tường minh thay vì `None`.

## Bằng chứng phải nộp

- Đếm `Signal` trong 3 presenter trước/sau. Với **mỗi** signal bị xoá, một dòng nói nó là cầu
  nối luồng (không phải ngữ nghĩa UI).
- Test: gây một lỗi trong slot UI → `SystemErrorFeed` nhận được và log panel hiện ra. Đây là
  bằng chứng cho yêu cầu "phải hoạt động trở lại".
- Log 2 màn cho thấy chuỗi health giống hệt nhau, và `grep _trigger_initial_health_check` → rỗng.
- `pwsh -NoProfile -File scripts/ci-local.ps1` — `RESULT: PASS`.

## Rủi ro

Đây là task lớn nhất epic và đụng vào cả 3 presenter cùng lúc. **Chia commit theo presenter**,
không gộp. Nếu số signal xoá được ít hơn hẳn dự kiến (ví dụ < 30/48), dừng lại và ghi lý do —
nhiều khả năng ranh giới "cầu nối vs ngữ nghĩa" ở §2 chưa đúng, chứ không phải phải cố xoá cho
đủ số.
