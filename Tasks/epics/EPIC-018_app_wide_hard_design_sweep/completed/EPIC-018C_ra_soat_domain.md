# EPIC-018C — Rà soát Hard Design: `src/domain/`

**Thuộc Epic:** [`EPIC-018`](../README.md)
**Trạng thái:** ✅ Hoàn thành — 2026-08-30
**Phụ thuộc:** Không.
**Nguồn:** [`DECISION_2026-08-30_module_scoped_audits_round2.md`](../DECISION_2026-08-30_module_scoped_audits_round2.md) §2 mục `018C`.

---

## Kết quả rà soát

Đọc hết 58 file `.py` trong `src/domain/`. 3 finding, verify độc lập:

- **C1** — `IStrategy`/`IIndicator` là `Protocol` không lý do (không khớp 1
  trong 3 lý do luật cho phép), mọi implementer đều kế thừa danh nghĩa,
  không consumer nào cần structural typing → đổi sang `ABC`.
- **C2** — `IStoppablePosition` cũng là `Protocol` không lý do hình thức.
  ADR ban đầu định giữ `Protocol` (lý do "tránh lộ `_OpenPosition` private
  qua ranh giới policy") — **sửa lại lúc code**: kiểm tra thật thì
  `_OpenPosition` chỉ là `@dataclass` thường, không base class nào khác,
  không `QObject`, không third-party — **không khớp bất kỳ 1 trong 3 lý
  do luật cho phép**, và `paper_exchange.py` đã import từ
  `order_matching_policy.py` sẵn (không rủi ro circular import) → **đổi
  sang `ABC`** giống C1, không giữ `Protocol`.
- **C3** — `paper_exchange.py` 451 dòng, vượt ngưỡng 400 → **từ chối tách
  thêm** (method count 12 chưa vượt 15, cắt tiếp không rõ ràng, đã tách
  Policy ở `EPIC-003C` rồi).

`base_indicator_script.py` (ADR D7 cũ) re-verify lại: đọc cả 9 script con
kế thừa, xác nhận DSL surface được dùng thật, không API chết — **giữ
nguyên quyết định từ chối tách**.

## Việc cần làm

1. `src/domain/strategies/i_strategy.py`: `IStrategy(Protocol)` →
   `IStrategy(ABC)`. Kiểm tra `BaseStrategy` đã implement `evaluate()` —
   không cần đổi gì ở implementer, chỉ đổi base của interface.
2. `src/domain/indicators/i_indicator.py`: `IIndicator(Protocol[T_co])` →
   `IIndicator(ABC, Generic[T_co])`. Kiểm tra `EMA`/`MACD`/`RSI`/`WMA`/
   `SupportResistance` đã kế thừa danh nghĩa — không đổi gì ở chúng.
3. `src/domain/backtesting/policies/order_matching_policy.py`:
   `IStoppablePosition(Protocol)` → `IStoppablePosition(ABC)`. Đổi
   `_OpenPosition` (`paper_exchange.py`) kế thừa `IStoppablePosition`
   tường minh.

## Tiêu chí xong

- `IStrategy`/`IIndicator`/`IStoppablePosition` là `ABC`, mọi implementer
  hiện có vẫn pass không cần sửa (kế thừa danh nghĩa sẵn có).
- Test hiện có của `strategies/`, `indicators/`, `backtesting/` xanh không
  đổi assertion.
- `paper_exchange.py` **không** tách thêm dòng nào ngoài việc đổi base
  class của `_OpenPosition` (quyết định từ chối tách thêm đã ghi ở ADR).

## Kết quả

- `i_strategy.py`: `IStrategy(Protocol)` → `IStrategy(ABC)`.
  `base_strategy.py`: `BaseStrategy(ABC)` → `BaseStrategy(IStrategy)` (giờ
  kế thừa tường minh thay vì chỉ khớp cấu trúc).
- `i_indicator.py`: `IIndicator(Protocol[T_co])` → `IIndicator(ABC, Generic[T_co])`.
  5 implementer (`EMA`/`MACD`/`RSI`/`WMA`/`SupportResistance`) đã kế thừa
  `IIndicator[...]` tường minh từ trước — không cần đổi gì ở chúng.
- **Lệch khỏi kế hoạch ban đầu, sửa ngay lúc code (ghi nhận trung thực):**
  `order_matching_policy.py`: `IStoppablePosition(Protocol)` →
  `IStoppablePosition(ABC)` (không giữ `Protocol` như ADR ban đầu định —
  kiểm tra thật thấy `_OpenPosition` không khớp bất kỳ lý do nào trong 3
  lý do luật cho phép). `paper_exchange.py`: `_OpenPosition` kế thừa
  `IStoppablePosition` tường minh — verify thực nghiệm dataclass field có
  default value thoả mãn `@property @abstractmethod` (không cần override
  bằng property thật).
- `390 test xanh` (`tests/unit/domain/` + `test_strategy_engine.py`), 0
  fail. `mypy` sạch trên cả 6 file liên quan
  (`i_strategy.py`/`base_strategy.py`/`i_indicator.py`/
  `order_matching_policy.py`/`paper_exchange.py`/`strategy_engine.py`).
- **Bug không liên quan, phát hiện khi chạy full suite để đối chiếu trước/
  sau (`bug-fix-rule.md`):** `scripts/shutdown_database_sync_probe.py` và
  `scripts/shutdown_sync_probe.py` vẫn gọi `MainWindow(engine)` — chữ ký
  cũ trước `EPIC-016` (Screen Registry Pattern). `EPIC-016` đã đổi
  `MainWindow.__init__` sang bắt buộc `screen_registry`/`sidebar_factory`
  nhưng 2 script này (không phải test, không nằm trong `tests/`, nên
  không được sửa cùng đợt `EPIC-016` cập nhật mọi call site trong
  `tests/`) bị bỏ sót — 4 test integration
  (`test_shutdown_database_sync_process.py` x3,
  `test_shutdown_sync_process.py` x1) fail với
  `TypeError: MainWindow.__init__() missing 2 required positional arguments`.
  Sửa cả 2 script theo đúng pattern `app_bootstrapper.py` (dựng
  `ScreenRegistry`, đăng ký 4 module, `sidebar_factory=Sidebar`) — 4 test
  xanh trở lại. `mypy` trên 2 script này không đổi (1 lỗi pre-existing
  không liên quan, `QCoreApplication.setQuitOnLastWindowClosed`, xác nhận
  bằng `git stash` trước/sau).
