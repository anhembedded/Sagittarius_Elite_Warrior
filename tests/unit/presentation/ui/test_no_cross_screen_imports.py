"""
Không gói `screens/<A>/` nào được import từ `screens/<B>/`.

**Vì sao cần guard này.** `EPIC-007` §1 đo được `data_management_widgets.py`
(1.156 dòng) đã **vô tình trở thành thư viện widget của cả app**: ba file ở
hai màn khác import chéo vào lấy `LogPanelWidget`/`AppProgressBarWidget`
(nay là `components/app_log_panel.py` và `components/app_progress_bar.py`).
Không ai quyết định như vậy — nó chỉ là nơi widget đó tình cờ được viết ra
trước, và mỗi lần dùng lại làm quan hệ ấy chặt thêm.

Điều đó khiến hai màn dính nhau theo cách không ai đọc tên file mà thấy được:
sửa `data_management_widgets.py` có thể làm hỏng màn Backtest, và ngược lại
xoá màn Data Management sẽ làm gãy hai màn khác.

`EPIC-007E` đã cắt cả ba bằng cách chuyển sang widget của engine. File này
giữ cho chúng không mọc lại — mà chúng sẽ mọc lại, vì cách chúng xuất hiện
lần đầu (viết widget ở màn đang làm, màn sau import sang) là cách tự nhiên
nhất khi đang vội.

## Chỗ đúng để đặt một widget dùng chung

- Không nghiệp vụ, hình dạng thuần → `sagittarius_engine...widgets` (Engine).
- Có tên/hành vi nghiệp vụ, ≥2 màn dùng → `presentation/ui/components/`.
- Một màn dùng → để yên trong `screens/<màn>/`.

Import từ `components/` hay từ engine đều **không** bị guard này chặn. Nó chỉ
chặn `screens/A` → `screens/B`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_SCREENS_ROOT = (
    Path(__file__).resolve().parents[4] / "src" / "presentation" / "ui" / "screens"
)

_SCREEN_IMPORT_RE = re.compile(r"presentation\.ui\.screens\.([a-z_]+)")

#: Import chéo được phép tồn tại tạm, mỗi cái một lý do và một task để đóng.
#:
#: Ba cái này **không phải widget** — chúng là logic chỉ báo và ánh xạ nến mà
#: màn Backtest mượn của Dashboard chỉ vì Dashboard viết ra trước. Chúng nằm
#: ngoài phạm vi `EPIC-007` (epic đó về card và widget), nên được ghi ra đây
#: thay vì nới guard trong im lặng.
#:
#: Đóng chúng là việc của `Tasks/backlog/BOT-120_backtest_depends_on_dashboard_for_non_ui_logic.md`.
#: Khi task đó xong, xoá cả ba dòng dưới đây.
_ALLOWED: frozenset[tuple[str, str]] = frozenset(
    {
        ("backtest_presenter.py", "dashboard"),
        ("backtest_view_model.py", "dashboard"),
    }
)


def _cross_screen_imports() -> list[tuple[str, int, str, str, str]]:
    """Mọi import từ gói màn này sang gói màn khác, kể cả cái được miễn trừ."""
    found = []
    for package_dir in sorted(p for p in _SCREENS_ROOT.iterdir() if p.is_dir()):
        if package_dir.name.startswith("_"):
            continue
        for py_file in sorted(package_dir.rglob("*.py")):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    module = node.module
                elif isinstance(node, ast.Import):
                    module = node.names[0].name
                else:
                    continue
                match = _SCREEN_IMPORT_RE.search(module)
                if match is None or match.group(1) == package_dir.name:
                    continue
                found.append(
                    (
                        py_file.name,
                        node.lineno,
                        package_dir.name,
                        match.group(1),
                        ", ".join(alias.name for alias in node.names),
                    )
                )
    return found


def test_screens_root_is_where_we_think_it_is() -> None:
    """`parents[4]` là đường dẫn tính tay. Sai một bậc thì test dưới quét thư
    mục rỗng và xanh vì không tìm thấy gì — đúng kiểu cổng giả."""
    assert _SCREENS_ROOT.is_dir(), f"không thấy cây screens ở {_SCREENS_ROOT}"
    assert len([p for p in _SCREENS_ROOT.iterdir() if p.is_dir()]) >= 4


def test_no_widget_import_crosses_a_screen_boundary() -> None:
    violations = [
        entry
        for entry in _cross_screen_imports()
        if (entry[0], entry[3]) not in _ALLOWED
    ]

    rendered = "\n".join(
        f"  {name}:{line}  {src} -> {dst}  [{names}]"
        for name, line, src, dst, names in violations
    )
    assert violations == [], (
        "một gói screens đang import từ gói screens khác.\n"
        "Widget dùng chung thuộc về `components/` (có nghiệp vụ) hoặc engine's\n"
        "`widgets` (không nghiệp vụ) — xem docstring module.\n\n" + rendered
    )


def test_the_allow_list_has_not_gone_stale() -> None:
    """Một danh sách miễn trừ sống lâu hơn thứ nó miễn trừ sẽ ngừng là bản ghi
    quyết định và trở thành chỗ để giấu. Khi `BOT-120` xong, test này đỏ và
    buộc phải xoá dòng tương ứng."""
    actual = {(entry[0], entry[3]) for entry in _cross_screen_imports()}
    unused = sorted(_ALLOWED - actual)

    assert unused == [], (
        f"danh sách miễn trừ nhắc tới import không còn tồn tại: {unused}. "
        f"Xoá chúng khỏi `_ALLOWED` (và đóng `BOT-120` nếu hết sạch)."
    )
