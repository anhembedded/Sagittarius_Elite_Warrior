"""Guard tests cho `EPIC-008` — biến luật của epic thành thứ CI ép được.

Lý do tồn tại, nói thẳng: mọi lỗi mà `EPIC-008` sửa đều **không phải** do ai đó
không biết luật. `UiActionFailedEvent` có docstring bảo người đọc hãy subscribe
nó; `HealthUpdatedEvent` có ba bản định dạng dù nguyên tắc "một nơi xử lý" đã
được viết ra. Luật đúng mà không có phép đo thì không ai theo — nên mỗi luật ở
đây phải có một test **đỏ được**.

Luật đầy đủ: `.claude/rules/architecture-rule.md` §6.
"""

from __future__ import annotations

import ast
from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.architecture.screen_files import (
    screen_owner,
    screen_roots,
)

_SRC = Path(__file__).resolve().parents[2] / "src"


def _python_files() -> list[Path]:
    return [p for p in _SRC.rglob("*.py") if "__pycache__" not in p.parts]


def _subscription_calls(tree: ast.AST) -> list[ast.Call]:
    """Mọi lời gọi `<gì đó>.on(...)` — cả `event_bus.on` lẫn `self._events.on`
    của `QtEventBridge`."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "on"
        and node.args
    ]


def test_events_are_addressed_by_class_not_by_string() -> None:
    """Guard 1 — đăng ký sự kiện phải dùng **lớp**, không dùng chuỗi hay
    `X.event_name`.

    Chuỗi không có gì nối nó với định nghĩa: đổi tên lớp, sửa `event_name`, hay
    gõ sai một ký tự đều không ai phát hiện, và subscriber im lặng không bao giờ
    chạy — đúng kiểu hỏng `EPIC-008` §1 phải đi sửa. Dùng lớp thì `mypy`, IDE
    và `grep` đều lần ra được.

    `X.event_name` cũng bị cấm dù nó *có* tham chiếu tới lớp: nó lấy ra chuỗi
    rồi vứt bỏ kiểu, nên `bus.on()` không còn cách nào phân biệt với một chuỗi
    gõ tay. Bus tự suy ra khoá từ lớp (`_get_event_key`), nên truyền thẳng lớp
    là tương đương về hành vi và hơn hẳn về khả năng lần dấu.
    """
    offenders: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in _subscription_calls(tree):
            first = call.args[0]
            where = f"{path.relative_to(_SRC.parent)}:{first.lineno}"
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                offenders.append(f"{where} -> chuỗi {first.value!r}")
            elif isinstance(first, ast.Attribute) and first.attr == "event_name":
                offenders.append(f"{where} -> .event_name thay vì lớp")

    assert offenders == [], (
        "đăng ký sự kiện phải dùng lớp, không dùng chuỗi:\n  " + "\n  ".join(offenders)
    )


def test_the_guard_can_actually_fail() -> None:
    """Một guard chưa từng đỏ là một guard chưa biết có chạy hay không.

    `EPIC-008` sinh ra vì một cơ chế được **giả định** là hoạt động mà không ai
    kiểm; lặp lại đúng sai lầm đó với chính guard này thì vô nghĩa. Ở đây cho nó
    ăn mã vi phạm và bắt buộc nó phải nhận ra.
    """
    violating = ast.parse(
        "bus.on('health.updated', handler)\n"
        "bus.on(HealthUpdatedEvent.event_name, handler)\n"
    )
    calls = _subscription_calls(violating)

    assert len(calls) == 2
    first_args = [call.args[0] for call in calls]
    assert isinstance(first_args[0], ast.Constant)
    assert isinstance(first_args[1], ast.Attribute)
    assert first_args[1].attr == "event_name"

    compliant = ast.parse("bus.on(HealthUpdatedEvent, handler)\n")
    good = _subscription_calls(compliant)[0].args[0]
    assert not isinstance(good, ast.Constant)
    assert not (isinstance(good, ast.Attribute) and good.attr == "event_name")


def test_one_event_is_not_subscribed_by_two_presenters() -> None:
    """Guard 3 — không sự kiện nào được hai màn cùng nghe trực tiếp.

    Đây là lỗi `EPIC-008G` vừa phải đi sửa: `HealthUpdatedEvent` bị hai
    presenter cùng `event_bus.on(...)`, mỗi màn tự chuẩn hoá, và hai bản trôi xa
    tới mức bản của Backtest **bỏ mất `Container`** mà không ai biết trong bao
    lâu. Nhiều màn cần cùng một sự thật thì đó là việc của một Feed, không
    phải của mỗi màn.

    **Retargeted (`BOT-141`).** `EPIC-025` Phase 4 xoá hẳn
    `src/presentation/ui/screens/` (`trading`/`dashboard` ở PR 4.4c,
    `backtest` ở PR 4.4d, `settings` ở PR 4.4e), nên guard này đã "tạm ngưng
    hoạt động" từ đó — `.rglob()` trên một cây không còn tồn tại luôn trả về
    rỗng, guard xanh mà không kiểm tra gì. Nay quét lại đúng chỗ màn hình
    thật sự sống: mỗi `ui/` mà một module sở hữu, và `shell/`
    (`screen_files.screen_roots()`). "Màn hình" được suy ra từ chính quy ước
    `<tên>_screen.py` xây `ScreenContribution(...)` — không đoán theo tên thư
    mục, vì tên thư mục và route không khớp nhau (`database_screen.py`'s
    route là `"data_management"`).

    Một file nằm ngoài mọi màn trong `ui/` của module nó (`screen_owner()`
    trả `None`) là Feed dùng chung — địa chỉ mới của `presentation/ui/
    common/` cũ (`support/ui_kit/health_feed.py` cho `HealthUpdatedEvent`, hay
    một Feed cấp module như `modules/trading/ui/equity_feed.py` phục vụ cả
    `trading/` lẫn `dashboard/`) — **được phép** là nơi duy nhất đăng ký nên bị
    loại khỏi nhóm so sánh."""
    by_event: dict[str, list[str]] = {}

    for root in screen_roots():
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            owner = screen_owner(path)
            if owner is None:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for call in _subscription_calls(tree):
                first = call.args[0]
                name = getattr(first, "id", None) or getattr(first, "attr", None)
                if name is None:
                    continue
                owner_id = owner.relative_to(_SRC.parent).as_posix()
                owners = by_event.setdefault(name, [])
                if owner_id not in owners:
                    owners.append(owner_id)

    shared = {event: owners for event, owners in by_event.items() if len(owners) > 1}
    assert shared == {}, (
        "sự kiện bị nhiều màn cùng nghe — hãy dựng một Feed thay vì nhân bản "
        f"logic: {shared}"
    )
