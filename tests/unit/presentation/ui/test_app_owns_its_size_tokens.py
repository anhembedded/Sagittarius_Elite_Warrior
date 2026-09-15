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
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui import kit
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import StyleRole, apply_role
from Sagittarius_Elite_Warrior.src.presentation.ui.theme_bootstrap import (
    seed_app_theme,
)

#: `style.py` is the only place a role turns a token name into pixels, so
#: it is also the only place that can read a token nobody supplies.
_STYLE_SOURCE = Path(kit.__file__).parent / "style.py"

#: Every `_px('...')` in that file — i.e. every numeric token the app's own
#: roles actually consume, discovered by reading the source rather than by
#: remembering to update a list. This is the completeness half: the old
#: hand-written tuple named six tokens and `style.py` read nine, so
#: `fontSizeXl`, `spaceXs`, `spaceSm` and `spaceMd` were being answered by
#: the engine's invented scale with nothing to say so.
_TOKENS_READ_BY_ROLES = tuple(
    sorted(
        set(
            re.findall(
                r"_px\(['\"]([A-Za-z]+)['\"]\)",
                _STYLE_SOURCE.read_text(encoding="utf-8"),
            )
        )
    )
)

#: Token số app phải tự cấp. Thiếu một cái là rơi về default của engine —
#: im lặng, không lỗi, chỉ sai pixel. **Không viết tay nữa**: lấy thẳng từ
#: `style.py`, nên thêm một `_px('...')` mới mà quên cấp giá trị là đỏ ngay.
_REQUIRED_SIZE_TOKENS = _TOKENS_READ_BY_ROLES

#: Thuộc tính QSS nào là "kích thước". Padding/margin không nằm đây: chúng
#: nhận `spaceXs/Sm/Md`, và các token đó đã bị khoá bởi
#: `_TOKENS_READ_BY_ROLES` ở trên — ghim thêm từng con số padding sẽ biến
#: file này thành ảnh chụp toàn bộ QSS, thứ sẽ đỏ vì mọi chỉnh sửa layout.
_SIZE_PROPERTIES = ("border-radius", "font-size")

#: **Mọi** `StyleRole`, và đúng những giá trị kích thước nó render hôm nay.
#:
#: Năm dòng đầu là hợp đồng gốc của `EPIC-007F` — đo từ code cũ:
#: `settings_view.py` (card 8px, field 6px, nhãn 12px, tiêu đề 14px) và
#: `dev_board_panel.py` (`_card_style` 8px). Phần còn lại ghim hiện trạng
#: 2026-09-07: không phải "số app từng vẽ tay", mà là "số app đang vẽ", để
#: một thay đổi phải là quyết định chứ không phải hệ quả phụ.
#:
#: Dict rỗng nghĩa là role đó **không** render kích thước nào — cũng là một
#: khẳng định: nếu mai nó bắt đầu render, guard bên dưới đỏ.
_ROLE_RENDERS: dict[StyleRole, dict[str, str]] = {
    # --- hợp đồng gốc EPIC-007F --- #
    StyleRole.SURFACE: {"border-radius": "8px"},
    StyleRole.FIELD: {"border-radius": "6px"},
    StyleRole.BODY_LABEL: {"font-size": "12px"},
    StyleRole.HEADING: {"font-size": "14px"},
    StyleRole.CAPTION: {"font-size": "11px"},
    # --- phần còn lại, ghim 2026-09-07 --- #
    StyleRole.SELECTABLE_CARD: {"border-radius": "8px"},
    StyleRole.PRIMARY_BUTTON: {"border-radius": "6px"},
    StyleRole.SECONDARY_BUTTON: {"border-radius": "6px"},
    StyleRole.DANGER_BUTTON: {"border-radius": "6px"},
    StyleRole.CHECKBOX: {},
    StyleRole.BADGE: {"border-radius": "6px"},
    StyleRole.BANNER_INFO: {"border-radius": "8px"},
    StyleRole.BANNER_WARN: {"border-radius": "8px"},
    StyleRole.BANNER_DANGER: {"border-radius": "8px"},
    StyleRole.BANNER_SUCCESS: {"border-radius": "8px"},
    StyleRole.SECTION_LABEL: {"font-size": "11px"},
    StyleRole.SECTION_LABEL_TICKED: {"font-size": "11px"},
    StyleRole.TABLE_HEADER: {"border-radius": "6px"},
    StyleRole.PROGRESS: {"border-radius": "6px"},
    #: 20px, và cho tới 2026-09-07 con số đó là của **engine**, không phải
    #: của app: `STAT_VALUE` đọc `fontSizeXl` mà app chưa từng cấp. Giá trị
    #: giữ nguyên, chủ sở hữu thì đổi — xem `Palette.FONT_SIZE_XL`.
    StyleRole.STAT_VALUE: {"font-size": "20px"},
    StyleRole.STAT_CARD: {"border-radius": "8px"},
    StyleRole.TABLE_CELL: {"font-size": "11px"},
    StyleRole.TABLE_CELL_STRONG: {"font-size": "11px"},
    StyleRole.GHOST_BUTTON: {"border-radius": "6px", "font-size": "11px"},
    StyleRole.LIST_SURFACE: {},
}


def _rendered_sizes(role: StyleRole, qtbot) -> dict[str, str]:
    """Kích thước thật một role render, đọc từ QSS nó sinh ra."""
    seed_app_theme()  # the real palette, through the one entry point (BOT-133)
    widget = QWidget()
    qtbot.addWidget(widget)
    apply_role(widget, role)
    qss = widget.styleSheet()

    rendered: dict[str, str] = {}
    for prop in _SIZE_PROPERTIES:
        # `(?<![\w-])` để `border-radius` không khớp nhầm
        # `border-top-left-radius`.
        values = {
            match.group(1) for match in re.finditer(rf"(?<![\w-]){prop}: ([^;]+);", qss)
        }
        if not values:
            continue
        assert len(values) == 1, (
            f"{role.name} render `{prop}` với {len(values)} giá trị khác "
            f"nhau ({sorted(values)}). Bảng dưới chỉ ghim được một; hoặc "
            f"role này đã tách làm hai, hoặc QSS của nó tự mâu thuẫn."
        )
        rendered[prop] = values.pop()
    return rendered


def test_the_app_supplies_every_size_token() -> None:
    """Không cấp thì engine lấp bằng default của nó — đúng cái đã gây ra
    `EPIC-007F`.

    Danh sách token lấy từ chính `style.py`, không viết tay: bản viết tay
    trước đây nêu 6 token trong khi `style.py` đọc 9, nên `fontSizeXl`,
    `spaceXs`, `spaceSm`, `spaceMd` bị engine quyết định suốt mà test vẫn
    xanh — đúng kiểu allowlist chỉ bắt được xoá, mù với thêm.
    """
    supplied = Palette.as_ui_dict()
    missing = [name for name in _REQUIRED_SIZE_TOKENS if name not in supplied]

    assert _REQUIRED_SIZE_TOKENS, (
        "không quét được `_px('...')` nào trong style.py — regex hỏng hoặc "
        "file đã đổi cách đọc token; guard này đang không gác gì cả."
    )
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
        if not isinstance(supplied.get(name), int | float)
    }

    assert bad == {}, f"token số phải là số, không phải chuỗi CSS: {bad}"


def test_every_style_role_is_pinned() -> None:
    """Nửa completeness của bảng trên.

    Allowlist chỉ bắt được **xoá** một role; cái thực sự xảy ra là **thêm**
    một role mà không ai ghim pixel cho nó (`test-health` C6). Ở đây role
    mới sẽ đỏ ngay khi được thêm vào enum.
    """
    unpinned = [role.name for role in StyleRole if role not in _ROLE_RENDERS]
    stale = [role.name for role in _ROLE_RENDERS if role not in set(StyleRole)]

    assert unpinned == [], (
        f"role chưa ghim kích thước: {unpinned}. Thêm dòng vào "
        f"`_ROLE_RENDERS` — dict rỗng nếu role đó không render kích thước "
        f"nào, đó vẫn là một khẳng định."
    )
    assert stale == [], f"ghim role không còn tồn tại: {stale}"


@pytest.mark.parametrize("role", list(_ROLE_RENDERS), ids=lambda r: r.name)
def test_role_renders_the_pixel_value_this_app_already_drew(
    qtbot, role: StyleRole
) -> None:
    """Widget engine phải vẽ ra đúng thứ app vẽ.

    Đỏ ở đây nghĩa là: hoặc app đổi thang số, hoặc engine đổi role đọc token
    nào. Cả hai đều đổi diện mạo app — không nhất thiết sai, nhưng phải là
    quyết định có chủ đích chứ không phải hệ quả phụ.
    """
    assert _rendered_sizes(role, qtbot) == _ROLE_RENDERS[role]


def test_body_label_and_heading_are_separately_sizable() -> None:
    """Hai role này từng bị ghim chung `fontSizeMd`, khiến app không thể vừa
    có nhãn 12px vừa có tiêu đề 14px. Đã sửa ở Engine; test này ở phía app
    vì chính app là bên chịu hậu quả."""
    assert Palette.FONT_SIZE_MD != Palette.FONT_SIZE_LG

    body, heading = QWidget(), QWidget()
    seed_app_theme()  # the real palette, through the one entry point (BOT-133)
    apply_role(body, StyleRole.BODY_LABEL)
    apply_role(heading, StyleRole.HEADING)

    assert "12px" in body.styleSheet()
    assert "14px" in heading.styleSheet()
