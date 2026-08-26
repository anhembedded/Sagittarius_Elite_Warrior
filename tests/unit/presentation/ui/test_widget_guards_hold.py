"""
Chạy hai guard của engine lên `src/presentation/ui` và khoá kết quả.

**Vì sao file này tồn tại.** Hai guard `find_inline_stylesheets` và
`find_bare_qt_base_widgets` đã có từ `EPIC-006B`, được mở rộng ở `EPIC-007A`,
và cho tới `EPIC-007D` **chưa từng được trỏ vào một cây nguồn thật nào** —
chúng chỉ chạy qua fixture `tmp_path` trong test của engine. `EPIC-007D` kéo
`find_inline_stylesheets` từ 130 finding về 0; không có file này thì con số đó
là ảnh chụp một khoảnh khắc, và lần `setStyleSheet("#1a1b22")` tiếp theo đưa
nó về 1 mà không ai biết.

Guard mạnh mà không ai chạy thì không bảo vệ gì cả.

## Hai ngưỡng, hai cách đối xử khác nhau

`find_inline_stylesheets` khoá ở **0 tuyệt đối**. Không có "cho phép thêm vài
cái"; muốn một literal thì viết `# token-exempt: <lý do>` ngay tại dòng đó, và
lý do ấy đi qua review.

`find_bare_qt_base_widgets` khoá bằng **trần chỉ được giảm**. Nó còn 21 finding
— đó là công việc của `EPIC-007E`/`007F`, chưa làm được hôm nay. Trần ngăn con
số tăng, và test sẽ **báo đỏ khi bạn làm nó giảm** mà quên hạ trần theo, nên
trần không thể phình ra rồi nằm đó mãi.

## Bẫy đã thật sự xảy ra, đừng lặp lại

`ruff format` và marker `token-exempt` đánh nhau: marker phải nằm **cùng dòng**
với hex vì guard đọc theo dòng, nhưng thêm nó vào thường làm dòng vượt 88 cột,
formatter ngắt dòng, và marker rơi xuống dòng dưới — nơi guard không thấy.
Trong `EPIC-007D` việc này làm con số nhảy 0 → 8 → 3 → 0. **Luôn chạy format
trước, guard sau.** File này chạy trong CI nên nó bắt được, nhưng biết trước
thì đỡ mất một vòng.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.presentation.ui.kit.guards import (
    find_bare_qt_base_widgets,
    find_inline_stylesheets,
    find_unscoped_container_stylesheets,
    format_bare_qt_base_findings,
    format_inline_stylesheet_findings,
    format_unscoped_container_findings,
)

_UI_ROOT = Path(__file__).resolve().parents[4] / "src" / "presentation" / "ui"

#: File định nghĩa màu của app — tương đương `style.py` của engine. Không có
#: nó thì `palette.py` bị báo 15 lần vì *chứa* token, và 0 là bất khả thi.
_COLOUR_SOURCES = ("palette.py",)

#: Số lớp còn kế thừa thẳng `QFrame`/`QDialog`/`QWidget`. `007F` sẽ kéo tiếp
#: xuống khi migrate 4 màn sang `Card`/`Panel`/`Overlay`.
#: Chỉ được phép giảm — xem docstring module.
#:
#: 21 lúc `EPIC-007D` đóng → 17 sau `EPIC-007E`, qua bốn lần xoá:
#: `LogPanelWidget` và `AppProgressBarWidget` (thay bằng
#: `components/app_log_panel.py` và `components/app_progress_bar.py`, cái sau
#: mang `base-exempt` vì nó là một cột caption + bar, không phải surface), và
#: `BaseCard` — bản trùng lặp `Card` của engine, `ChartCard` giờ kế thừa
#: thẳng engine; và `SymbolPickerDialog`, thay bằng
#: `components/symbol_picker_overlay.py` trên `PickerOverlay`.
#:
#: Ratchet báo đỏ **ba lần** trong task đó, mỗi lần đúng lúc con số giảm mà
#: trần chưa hạ theo. Đó là việc nó sinh ra để làm — và nó cũng là thứ duy
#: nhất buộc người ta phải ghi lại tiến độ, thay vì để khoảng hở tích lại.
#: 17 → 16 ở `EPIC-007F` bước 4: `DevBoardPanel` mang `base-exempt` — nó là
#: vùng màn hình vẽ trên nền app (`Palette.BG`), không viền, tức là chỗ các
#: card *nằm lên*, không phải một card. Kế thừa `Panel` sẽ cho nó `BG_CARD`
#: cộng một viền, thành card thứ tư bọc quanh ba card kia.
#:
#: 16 → 15: `MetricCardWidget` bị xoá hẳn, 2 call site chuyển sang `StatCard`
#: của Engine. Đi kèm là `StatCardData` bỏ chuỗi hex, mang `Tone` — đúng thứ
#: `Tone` sinh ra để làm.
#:
#: 15 → 14: `DynamicTabBarWidget` (+ `_TabButton` riêng của nó) xoá, dùng
#: `TabBar` của Engine. Trước đó phải sửa `TabBar` bên Engine: nó là `Panel`
#: nên vẽ nền card + viền, trong khi thanh tab của app trong suốt — mà chính
#: `_TabButton` của Engine đã ghi `base-exempt: a tab is a button, not a
#: surface`, nên một hàng nút cũng không phải surface.
#: 14 → 7 across one stretch of `007F` on Backtest and Data Management,
#: recorded here rather than as one unexplained drop:
#:   · 4 Backtest widgets `base-exempt` — three screen regions painted on
#:     the app background, one label stacked over a field
#:   · `_CoverageSegmentWidget` and `TimeRangeCardWidget` `base-exempt` —
#:     a coloured bar segment and a form group
#:   · `ConfirmDialog` deleted, both call sites on the engine's
#:     `ConfirmOverlay`
#:
#: 7 → 6: `_StatusRowWidget` now derives `DataRow`. That needed the engine
#: first (PRs #199/#200): `DataRow` was a `Panel`, so every row drew a card
#: frame, and it had no vocabulary for table text, outlined row actions or a
#: per-record status colour. Fourth time in this epic that a widget shipped
#: without a consumer turned out to be broken.
#: 6 → 2, and `screens/` is now at **0** — requirement 1 of `007F` met.
#: `_KLineRowWidget`/`_GapRowWidget` derive `DataRow`, both inspector
#: dialogs derive `Overlay`. What is left sits in `components/`, outside
#: what that requirement asked for: `_CachedFrameOverlay` (a paint surface
#: for a cached chart frame) and `CriticalErrorDialog` (the last-resort box
#: shown when the app cannot start — it must not depend on a theme bridge
#: that may be exactly what failed).
_BARE_QT_BASE_CEILING = 2


def test_ui_root_is_where_we_think_it_is() -> None:
    """Đường dẫn tính bằng `parents[4]`; nếu ai đó di chuyển file test này,
    hai test dưới sẽ quét một thư mục rỗng và xanh vì không có gì để tìm.
    Đây là thứ chặn cái đó."""
    assert _UI_ROOT.is_dir(), f"không thấy cây UI ở {_UI_ROOT}"
    assert (_UI_ROOT / "assets" / "palette.py").is_file()


def test_no_hardcoded_colour_outside_palette() -> None:
    findings = find_inline_stylesheets(_UI_ROOT, colour_source_names=_COLOUR_SOURCES)

    assert findings == [], (
        "EPIC-007D đưa con số này về 0 và nó phải ở đó.\n"
        "Dùng token trong `Palette`, hoặc nếu literal là có chủ đích thì viết\n"
        "`# token-exempt: <lý do>` NGAY TRÊN DÒNG chứa nó.\n\n"
        + format_inline_stylesheet_findings(findings)
    )


def test_bare_qt_base_classes_do_not_grow() -> None:
    findings = find_bare_qt_base_widgets(_UI_ROOT)

    assert len(findings) <= _BARE_QT_BASE_CEILING, (
        f"số lớp kế thừa thẳng base của Qt tăng từ {_BARE_QT_BASE_CEILING} "
        f"lên {len(findings)}. Kế thừa `Card`/`Panel`/`Overlay` của engine, "
        f"hoặc `# base-exempt: <lý do>` nếu nó thật sự không phải surface.\n\n"
        + format_bare_qt_base_findings(findings)
    )


def test_the_ceiling_is_not_stale() -> None:
    """Trần chỉ hữu ích khi nó bám sát thực tế. Khi `007E`/`007F` kéo con số
    xuống, test này đỏ và buộc phải hạ trần theo — nếu không, khoảng hở tích
    lại và guard lặng lẽ ngừng có ý nghĩa."""
    findings = find_bare_qt_base_widgets(_UI_ROOT)

    assert len(findings) == _BARE_QT_BASE_CEILING, (
        f"tốt — còn {len(findings)}, ít hơn trần {_BARE_QT_BASE_CEILING}. "
        f"Hạ `_BARE_QT_BASE_CEILING` xuống {len(findings)} để khoá lại."
    )


def test_no_container_leaks_its_chrome_onto_its_children() -> None:
    """Locked at 0 absolutely, like the colour guard — not on a ratchet.

    `BUG-008` has come back five times because nothing ran this check. A
    property list with no selector is Qt's universal selector: on a widget
    with children it hands them its border and its background. The worst
    single instance was `MainWindow`'s `QStackedWidget`, which holds every
    screen — `Palette.BG` was being repainted onto every label in the app
    that had no rule of its own, which is what a user finally reported as
    "too many borders" (`BUG-052`).

    A deliberate exception is `# cascade-exempt: <reason>` on the same line,
    and that reason goes through review.
    """
    findings = find_unscoped_container_stylesheets(_UI_ROOT)

    assert findings == [], (
        "a widget that owns children is styled with a bare property list, "
        "which Qt reads as the universal selector.\n"
        "Scope it — `apply_role()` for a shape the engine already has, or "
        "`Selector { ... }` for one it does not.\n\n"
        + format_unscoped_container_findings(findings)
    )
