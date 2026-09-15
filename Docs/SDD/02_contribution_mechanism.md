# SDD §2 — The contribution mechanism

> Part of the SDD, split out of the single `README.md` this document used to be
> (2026-09-15, user decision). Every `###` heading below is **verbatim** from that
> file, so a reference written as *"SDD, 'Threading contract'"* still resolves.
> [`README.md`](README.md) is the index.

The descriptor's shape, when it is validated, and what each surface accepts.
These three change together: a new field on the descriptor is a new thing to
validate and a new thing a surface may or may not accept.

## Design rules the diagrams encode (the text a reviewer checks the code against)

### The contribution descriptor — one shape for every place (answers O1)

```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:                       # core/ is Qt-free at runtime; the guard ignores TYPE_CHECKING blocks
    from PySide6.QtWidgets import QWidget
    from sagittarius_engine.extensions.pyside_mvc import QtEventBridge

class Place(Enum):            # canonical list: Docs/VOCABULARY/README.md §2 — adding a member is an HLD change
    SCREEN = "screen"; HEADER = "header"; CONTEXT_BAR = "context_bar"; WORKSPACE = "workspace"
    RAIL = "rail"; CONSOLE = "console"; MODAL = "modal"
    SETTINGS_SECTION = "settings_section"; STATUS_TILE = "status_tile"; DEV_PROBE = "dev_probe"

class SizeHint(Enum): COMPACT = "compact"; REGULAR = "regular"; TALL = "tall"

@dataclass(frozen=True, slots=True)
class ContributionDescriptor:
    contributor_id: str        # a module_id, or "shell" for the shell's own surfaces — nothing else
    surface_id: str            # "welcome", "trading", "dev_board", "settings", "backtest", "data_management"
    place: Place
    order: int                 # sort key within (surface_id, place); collisions are allowed (see rule 2)
    size_hint: SizeHint
    factory: Callable[[IContainer], QWidget]   # the ONLY Qt-typed field; never called at contribute time
    title: str | None = None   # shown by RAIL, SETTINGS_SECTION, MODAL, DEV_PROBE; ignored elsewhere
```

`ScreenContribution` is the one exception with its own fields, because navigation metadata
(`route`, `title`, `icon`, `section_key`, `section_sequence`, `item_sequence`, `location`,
`is_default`, `is_navigable`) already exists in `ScreenRegistry`'s `NavMetadata` and is reused
unchanged; its factory returns `(View, Presenter)`.

**Who may contribute.** Only a `BoundedContextModule` (through `contribute()`) and the shell
(directly, for `welcome`, `settings` and its own screens). A **support package never contributes**:
the module that needs a support widget contributes it under its own `contributor_id` — `trading`
contributes the chart panel it wants on the trading workspace, `market_data` contributes the
indicator checklist it wants on Dev Board. So `contributor_id` keeps one meaning and the two-way
module-list guard stays exact.

**Lazy factories.** `factory` is a plain function defined in the module's `ui/` package whose
**body** imports the widget module; `contribute()` therefore imports no Qt widget code. Guard: after
every module's `contribute()` has run, no module under `modules/*/ui/panels/` is present in
`sys.modules`. This keeps `PresenterManager`'s laziness (`abstract_screen_module.py:22-30`), which
the app relies on so that boot does not load every screen's dependency tree.

### Registry validation — at `contribute()` time, not at render time (pluggy's rule, HLD §7.3)

1. `surface_id` must be one of the surfaces the shell **knows** (declared for this run, or declared
   but gated off); an unknown id is a typo and raises `ContributionError` naming contributor,
   surface and place. `place` must be in the surface's `accepts`; otherwise `ContributionError`.
2. `order` is a sort key, not a uniqueness key. Rendering order is the stable sort by
   `(order, contributor_id, factory.__qualname__)`, so two independently authored modules that both
   pick `order = 10` render deterministically instead of refusing to boot. The **uniqueness key** is
   `(surface_id, place, contributor_id, factory.__qualname__)`; registering it twice raises.
3. A contribution to a surface that is **declared but gated off for this run** (`dev_board` when
   `dev.mode` is false) is **dropped with one log line**, whatever its place. That is the normal
   user run: the twelve mirrored panels, the manual-order panel, the checklist and the probes are all
   dropped together, and the app boots.
4. `factory` is never invoked during `contribute()`; a guard runs every module's `contribute()`
   against a registry that raises on any factory call.
5. `contribute()` runs after `boot()`, in the module list's order, and **may `resolve()`** — so the
   list order is observable at contribute time. That is why the list, not the Engine's sort, is the
   source of truth (boot step 3).

### Surfaces and what each accepts

| Surface | Owner | `accepts` |
| :--- | :--- | :--- |
| `welcome` | shell | `HEADER`, `WORKSPACE` |
| `trading` | shell | `HEADER`, `CONTEXT_BAR`, `WORKSPACE`, `RAIL`, `CONSOLE`, `MODAL`, `STATUS_TILE` |
| `dev_board` (gated) | shell | the same plus `DEV_PROBE`; system controls are a `HEADER` contribution at `order = 20` |
| `settings` | shell | `SETTINGS_SECTION` |
| `backtest` | `backtesting` | `RAIL`, `MODAL` (its own widgets are not contributions) |
| `data_management` | `market_data` | `RAIL`, `MODAL` |

