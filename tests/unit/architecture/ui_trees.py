"""The directories that hold this application's UI, in one place.

**Why this file exists, on the third occasion.** `EPIC-025` is moving the UI out
of `src/presentation/ui/` into `support/` one package per pull request, and
five guards scan "the UI" by path: the colour guard, the three widget guards,
the card-layer guard, the `QQuickWidget`/theme-seeding guard, and the engine-port
guard. Each move made every one of them read a smaller tree than the UI actually
occupies, and a path-scanning guard that has lost part of its subject does not
fail — it passes, faster.

That happened three times and cost three separate repairs:

1. **PR 1.6a** — `assets/` moved and took `palette.py`, the colour guard's own
   exempt file, out of the scan. The guard stayed green on what was left, and
   `test_ui_root_is_where_we_think_it_is` is what noticed.
2. **PR 1.6b** — the `kit/` move revealed that the surface host had been
   unguarded by all three widget guards since PR 1.4b-1, and the card-layer
   guard was one move away from inspecting nothing (the legacy tree was down to
   a single `Card`).
3. **PR 1.6f** — `chart_card` moved to `support/charting`, `_CachedFrameOverlay`
   left the scanned set, and the bare-Qt-base ratchet read 1 instead of 2. A
   *ratchet going down* looks like progress, which is the most expensive way for
   this failure to present.

Three repairs of the same shape is the point at which the shape is the bug. So
the roots live here, the guards import them, and the next move edits one tuple
instead of five files — and if it forgets, every guard fails at once rather than
quietly narrowing.

**A fourth occasion, and the first one this file caught rather than suffered.**
`EPIC-025` PR 2.1e moved eleven files into `modules/strategy/ui/` — the first UI
a bounded context owns beyond `trading`'s one probe — and the tuple did not
mention `modules/*/ui` at all. `modules/trading/ui` had in fact been outside
every one of these guards since PR 1.4c-4 contributed the session probe, which
is the same silence as the three repairs above, just never noticed because that
package holds one small factory. Both are rows now, and the hole was real:
planting a duplicate `Palette` hex in `modules/strategy/ui/strategy_display.py`
leaves `test_palette_is_the_only_color_source.py` **green** without the row and
red with it. Measured, not assumed — that probe is what this note rests on.

`architecture-rule.md` §7.2.1's distinction applies to this file: it is a
**seam**, not a variant. It does not decide what any guard checks, only where
the UI is.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: Every tree that holds UI code today, legacy first.
#:
#: `src/presentation/ui` shrinks with each pull request of `EPIC-025` Phase
#: 1/4 and is deleted in Phase 4; the `support/` and `modules/*/ui` entries
#: grow. A guard that means "the application's UI" reads this tuple rather than
#: naming a directory, so the sentence stays true as the tree moves under it.
#:
#: `modules/*/ui` is where the UI is *going*: every screen ends up owned by the
#: context whose subject it shows (ADR D22, HLD §4), so a new module's `ui/`
#: needs a row here on the pull request that creates it, not later.
UI_TREES: tuple[Path, ...] = (
    _REPO_ROOT / "src" / "presentation" / "ui",
    _REPO_ROOT / "src" / "support" / "ui_kit",
    _REPO_ROOT / "src" / "support" / "charting",
    _REPO_ROOT / "src" / "modules" / "trading" / "ui",
    _REPO_ROOT / "src" / "modules" / "strategy" / "ui",
)

#: The same list as repository-relative POSIX strings, for
#: `scanned_roots_registry.py` rows and for assertion messages.
UI_TREE_PATHS: tuple[str, ...] = tuple(
    tree.relative_to(_REPO_ROOT).as_posix() for tree in UI_TREES
)


def existing_ui_trees() -> tuple[Path, ...]:
    """`UI_TREES` minus anything not on disk yet.

    Phase 4 deletes `presentation/ui`, and a support package does not exist
    until the pull request that creates it. A guard iterating this never has to
    ask; a guard that wants to *assert* a tree is present reads `UI_TREES` and
    checks it, which is what the landmark tests do.
    """
    return tuple(tree for tree in UI_TREES if tree.is_dir())
