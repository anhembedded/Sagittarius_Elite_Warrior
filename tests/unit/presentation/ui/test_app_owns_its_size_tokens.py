"""
App phải tự cấp thang số của mình, và các role phải render ra đúng pixel app vẽ.

**Vì sao file này tồn tại.** Engine ship *default* cho spacing/radius/typography
và cho giá trị của app thắng khi trùng key
(`tokens.defaults.with_token_defaults`) — nhưng app **chưa bao giờ cấp cái nào**.
Nên mọi kích thước trong app đang do thang engine tự phát minh quyết định:
`radiusLg` 10px, `fontSizeMd` 13px, `fontSizeLg` 16px — trong đó **16px không
xuất hiện một lần nào** trong `src/presentation/ui`.

Đó là nguồn của mọi thay đổi thị giác ở `EPIC-007F`: mỗi lần một màn hình lên
widget của engine là nó bị đổi da lặng lẽ (card 8px→6px, field 6px→4px, nhãn
12px→13px, tiêu đề 14px→13px).

Ranh giới chốt lại: **engine sở hữu từ vựng** (role nào đọc token nào),
**app sở hữu nghĩa** (token đó bằng bao nhiêu px). Màu vốn đã đúng như vậy —
token màu bắt buộc không có default ở engine, cố ý.

File này khoá cả hai chiều: app có cấp đủ số không, và số đó có ra đúng pixel
app vẫn vẽ bằng tay không.
"""

from __future__ import annotations

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from sagittarius_engine.extensions.pyside_mvc.tokens import get_theme_bridge
from sagittarius_engine.extensions.pyside_mvc.widgets import StyleRole, apply_role

#: Token số app phải tự cấp. Thiếu một cái là rơi về default của engine —
#: im lặng, không lỗi, chỉ sai pixel.
_REQUIRED_SIZE_TOKENS = (
    "radiusSm",
    "radiusMd",
    "radiusLg",
    "fontSizeSm",
    "fontSizeMd",
    "fontSizeLg",
)

#: (role, thuộc tính QSS, giá trị app vẽ tay TRƯỚC `EPIC-007F`).
#:
#: Đây là hợp đồng thật của bài migrate: yêu cầu 2 của `EPIC-007F` nói mọi
#: khác biệt thị giác là regression. Số bên dưới đo từ chính code cũ —
#: `settings_view.py` (card 8px, field 6px, nhãn 12px, tiêu đề 14px) và
#: `dev_board_panel.py` (`_card_style` 8px).
_ROLE_RENDERS = (
    (StyleRole.SURFACE, "border-radius", "8px"),
    (StyleRole.FIELD, "border-radius", "6px"),
    (StyleRole.BODY_LABEL, "font-size", "12px"),
    (StyleRole.HEADING, "font-size", "14px"),
    (StyleRole.CAPTION, "font-size", "11px"),
)


def test_the_app_supplies_every_size_token() -> None:
    """Không cấp thì engine lấp bằng default của nó — đúng cái đã gây ra
    `EPIC-007F`."""
    supplied = Palette.as_ui_dict()
    missing = [name for name in _REQUIRED_SIZE_TOKENS if name not in supplied]

    assert missing == [], (
        f"app không cấp token số: {missing}. Thiếu cái nào thì engine lấp "
        f"bằng thang của nó và pixel đổi mà không ai báo."
    )


def test_the_supplied_sizes_are_numbers_not_css_strings() -> None:
    """`_px()` của engine nối `px` vào giá trị. Cấp `"8px"` sẽ ra `8pxpx` —
    QSS hỏng, Qt bỏ qua im lặng."""
    supplied = Palette.as_ui_dict()

    bad = {
        name: supplied[name]
        for name in _REQUIRED_SIZE_TOKENS
        if not isinstance(supplied[name], int | float)
    }

    assert bad == {}, f"token số phải là số, không phải chuỗi CSS: {bad}"


@pytest.mark.parametrize(("role", "prop", "expected"), _ROLE_RENDERS)
def test_role_renders_the_pixel_value_this_app_already_drew(
    qtbot, role: StyleRole, prop: str, expected: str
) -> None:
    """Widget engine phải vẽ ra đúng thứ app vẽ tay trước `EPIC-007F`.

    Đỏ ở đây nghĩa là: hoặc app đổi thang số, hoặc engine đổi role đọc token
    nào. Cả hai đều đổi diện mạo app — không nhất thiết sai, nhưng phải là
    quyết định có chủ đích chứ không phải hệ quả phụ.
    """
    get_theme_bridge(Palette.as_ui_dict())
    widget = QWidget()
    qtbot.addWidget(widget)

    apply_role(widget, role)

    match = re.search(rf"{prop}: ([^;]+);", widget.styleSheet())
    assert match, f"{role} không render `{prop}` nào:\n{widget.styleSheet()}"
    assert match.group(1) == expected, (
        f"{role.name} render `{prop}: {match.group(1)}`, app vốn vẽ `{expected}`."
    )


def test_body_label_and_heading_are_separately_sizable() -> None:
    """Hai role này từng bị ghim chung `fontSizeMd`, khiến app không thể vừa
    có nhãn 12px vừa có tiêu đề 14px. Đã sửa ở Engine; test này ở phía app
    vì chính app là bên chịu hậu quả."""
    assert Palette.FONT_SIZE_MD != Palette.FONT_SIZE_LG

    body, heading = QWidget(), QWidget()
    get_theme_bridge(Palette.as_ui_dict())
    apply_role(body, StyleRole.BODY_LABEL)
    apply_role(heading, StyleRole.HEADING)

    assert "12px" in body.styleSheet()
    assert "14px" in heading.styleSheet()
