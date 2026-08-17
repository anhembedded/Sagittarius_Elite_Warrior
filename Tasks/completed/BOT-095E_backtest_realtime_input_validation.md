# Nhiệm vụ: BOT-095E — Khung Kiểm định Đầu vào Mở rộng (Pre-Backtest Assertion Pipeline) & Parameter Stepper

> Thuộc Epic [`BOT-095`](BOT-095_backtest_signals_fsm_lifecycle_epic.md).
> **Trọng tâm**: Thiết kế một **Khung Kiểm định Đầu vào Mở Rộng (Extensible Input Assertion Pipeline)** tuân thủ nguyên lý **OCP (Open/Closed Principle)** cho phép dễ dàng bổ sung các luật kiểm tra đầu vào mới (Min Capital / Binance Minimum Lot Size, Date format, Leverage bounds, Parameter ranges) mà không sửa đổi Presenter, kết hợp tính năng **Parameter Stepper with Hotkeys** để tăng tốc tinh chỉnh thông số trong modal.

---

## 1. Vấn đề Hiện tại

1. **Thiếu cơ chế Assertion Framework mở rộng (Hardcoded Checks):**
   - Hiện tại, việc kiểm tra vốn hay ngày tháng bị viết rải rác bằng các câu lệnh `if/else` thủ công.
   - Khi muốn thêm các luật mới (như: *Vốn phải lớn hơn Minimum Notional 5 USDT của Binance*, *Đòn bẩy không vượt quá 50x*, *Stop Loss không được lớn hơn 20%*), code Presenter sẽ nhanh chóng phình to (God Method).
2. **Thiếu phản hồi trực quan tại chỗ:**
   - Người dùng gõ sai thông số không thấy viền đỏ cảnh báo ngay lúc nhập.
3. **Thao tác tinh chỉnh số liệu chậm:**
   - Trong `BotParamsDialog`, muốn đổi EMA từ 12 sang 13 phải bôi đen gõ lại bàn phím, không có phím tắt tăng/giảm nhanh.

---

## 2. Thiết kế Kỹ thuật (Technical Design)

### 2.1. Khung Kiểm định Đầu vào Mở rộng (Extensible Input Assertion Pipeline)
Được xây dựng theo mô hình Chain / Strategy trong `src/presentation/ui/screens/backtest/logic/assertions/`:

```python
from abc import ABC, abstractmethod
from typing import NamedTuple, List, Optional

class AssertionResult(NamedTuple):
    is_valid: bool
    field_name: str
    error_message: str

class IInputAssertionRule(ABC):
    """
    Interface cho mọi luật kiểm tra đầu vào trước khi chạy Backtest.
    Tuân thủ OCP: Thêm luật mới chỉ cần tạo class kế thừa IInputAssertionRule.
    """
    @abstractmethod
    def validate(self, context: dict) -> AssertionResult:
        pass

class PositiveCapitalRule(IInputAssertionRule):
    """Kiểm tra Vốn ban đầu phải là số thực > 0."""
    def validate(self, context: dict) -> AssertionResult:
        capital_str = context.get("initial_capital", "")
        try:
            val = float(capital_str)
            if val <= 0:
                return AssertionResult(False, "initialCapital", "Vốn ban đầu phải lớn hơn 0.")
            return AssertionResult(True, "initialCapital", "")
        except ValueError:
            return AssertionResult(False, "initialCapital", "Vốn ban đầu phải là một số hợp lệ.")

class BinanceMinNotionalRule(IInputAssertionRule):
    """Kiểm tra notional của lệnh theo filter metadata của đúng symbol/market."""

    def validate(self, context: dict) -> AssertionResult:
        try:
            val = float(context.get("initial_capital", 0))
            currency = context.get("currency", "USDT")
            # Không hard-code 5 USDT: MIN_NOTIONAL/NOTIONAL là filter theo
            # symbol và notional = quantity * price, không phải initial capital.
            if currency == "USDT" and val < context["symbol_min_notional"]:
                return AssertionResult(
                    False, "orderNotional", "Giá trị lệnh chưa đạt minimum notional của symbol."
                )
            return AssertionResult(True, "initialCapital", "")
        except ValueError:
            return AssertionResult(True, "initialCapital", "")

class DateRangeChronologyRule(IInputAssertionRule):
    """Kiểm tra Ngày bắt đầu phải nhỏ hơn Ngày kết thúc."""
    def validate(self, context: dict) -> AssertionResult:
        start = context.get("custom_start")
        end = context.get("custom_end")
        if start and end and start >= end:
            return AssertionResult(False, "dateRange", "Ngày bắt đầu phải trước ngày kết thúc.")
        return AssertionResult(True, "dateRange", "")

class PreBacktestAssertionPipeline:
    """
    Pipeline thực thi toàn bộ các luật kiểm tra đầu vào.
    """
    def __init__(self, rules: Optional[List[IInputAssertionRule]] = None):
        self._rules = rules or [
            PositiveCapitalRule(),
            BinanceMinNotionalRule(),
            DateRangeChronologyRule(),
        ]

    def add_rule(self, rule: IInputAssertionRule) -> None:
        self._rules.append(rule)

    def validate_all(self, context: dict) -> List[AssertionResult]:
        return [rule.validate(context) for rule in self._rules]
```

---

### 2.2. Parameter Stepper with Hotkeys trong `BotParamsDialog`
1. Hỗ trợ phím mũi tên `Up` / `Down` hoặc con lăn chuột trên các trường số (`input_int`, `input_float`) để tăng/giảm theo bước nhảy (`step = 1` cho int, `step = 0.1` cho float).
2. Hỗ trợ phím tắt `Ctrl + Enter` trong dialog để kích hoạt ngay: *"Lưu & Chạy lại"* mà không cần di chuột bấm nút.

---

## 3. Danh sách File Cần Chỉnh sửa & Tạo mới

- 🆕 `src/presentation/ui/screens/backtest/logic/assertions/`: Chứa `IInputAssertionRule`, `PreBacktestAssertionPipeline` và các rules.
- ✏️ `src/presentation/ui/screens/backtest/backtest_view_model.py`: Kết nối kết quả từ Assertion Pipeline với các property validation trên QML.
- ✏️ `src/presentation/ui/components/CapitalDialog.qml`: Hiển thị viền đỏ và text cảnh báo sàn giao dịch.
- ✏️ `src/presentation/ui/components/BotParamsDialog.qml`: Bổ sung phím tắt `Ctrl + Enter` và con lăn stepper cho input số.
- ✏️ `tests/unit/presentation/ui/screens/test_backtest_assertion_pipeline.py`: Viết unit tests kiểm tra từng Rule độc lập.

---

## 4. Tiêu chuẩn Nghiệm thu (Acceptance Criteria)

1. **Khung Assertion Mở rộng hoàn hảo**:
   - Dễ dàng gắn thêm Rule mới mà không làm vỡ code cũ.
   - Validation local (format/range) chạy tức thì. Market-rule validation dùng exchange metadata cache theo symbol; metadata không có/đã cũ phải hiển thị “chưa xác minh”, không hard-code $5.
2. **Stepper & Phím tắt mượt mà**:
   - Dùng phím `Up`/`Down` hoặc lăn chuột trên `BotParamsDialog` thay đổi giá trị mượt mà; `Ctrl + Enter` kích hoạt chạy lại tức thì.
3. **Local CI Verification**:
   - Chạy `.\scripts\ci-local.ps1 -Full` đạt 100% Passed, gồm lint, format,
     primary test, sanity và coverage.

4. **Input safety**:
   - Stepper tôn trọng `min`/`max`/`step` từ param schema, không đổi giá trị khi cuộn chỉ để đọc dialog, và hotkey không bypass validation.

---

## Hoàn thành (2026-08-17)

- `PreBacktestAssertionPipeline` kiểm tra capital hữu hạn/dương và chronology
  custom range trước dispatch; thông báo lỗi được bind tức thì vào
  `CapitalDialog`.
- `ScriptInput.step` là metadata schema cho Strategy và Indicator Script;
  Python là nguồn sự thật cho normalisation/clamp khi người dùng dùng
  Up/Down/Wheel, QML không còn tự tính step/bounds.
- Backtest live dùng watermark một nến đã publish; sau sync phải probe coverage
  lại trước khi thông báo có thể auto-run. Điều này giữ lại regression cho log
  "Đồng bộ dữ liệu thành công" nhưng vẫn thiếu nến.
- QML interaction test mở popup thật, focus field và gửi Qt `↑` để xác nhận
  hiển thị đổi `20 → 21`; Full CI: 928 primary + 25 sanity, coverage 93.94%.
- Market metadata/order-rule validation được tách minh bạch sang `BOT-095E1`;
  simulation không hứa đã pass Binance filter khi thiếu facts.
