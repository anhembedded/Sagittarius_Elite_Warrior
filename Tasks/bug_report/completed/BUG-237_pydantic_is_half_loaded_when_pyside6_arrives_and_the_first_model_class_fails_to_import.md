# BUG-237 — A pydantic model module fails to import with `partially initialized module 'pydantic._internal._validators'` once PySide6 has been loaded after the composition root

- **Reported:** 2026-10-20 (the BOT-190 author, via the delivery coordinator; found on `master-warrior` at `32c67a3`)
- **Severity:** 🟡 P2 — a latent flake: the architecture guard `test_every_deferred_literal_resolves` fails in a run that holds a bots integration journey; CI's gate parts do not group tests that way today. The same import order is the production one (`src/main.py` imports `composition_root` before the GUI imports PySide6).
- **Status:** ✅ Fixed (2026-10-20)
- **Board:** The deferred-literal guard failed with `cannot import name 'import_string' from partially initialized module 'pydantic._internal._validators'` whenever a bots integration journey was in the run. Cause: `composition_root` imports the engine's pydantic middleware, which leaves pydantic half-loaded, and PySide6's import hook, installed afterwards, re-enters `_validators` while it is being imported. Fixed: `composition_root` finishes loading pydantic (`pydantic.fields`) before anything can import PySide6.
- **Context:** Guard `tests/unit/architecture/test_every_deferred_literal_resolves.py` → `src/shell/composition_root.py` (`shell`) → engine `sagittarius_engine.middleware.pydantic_validation_middleware` + PySide6 import hook
- **Environment:** Linux, Python 3.12.3, pydantic 2.13.5, PySide6 6.11.1, pytest-xdist 3.8.0 (`-n 4`), engine at `engine.ref`; `master-warrior` at `0ccc921`.

## Reproduction
Failing run (2 of 2 attempts under `-n 4`; green serially, because xdist runs the bots `conftest.py` in the worker's initial-conftest phase in a different order of imports):

`pytest tests/unit/architecture tests/unit/modules/alerting tests/unit/modules/bots/application/kinds tests/integration/modules/alerting tests/integration/modules/bots/test_a_bot_tells_discord_about_every_fill_cycle_and_exit_on_the_fake_exchange.py -n 4`

Deterministic, without pytest (before the fix):
```
import Sagittarius_Elite_Warrior.src.shell.composition_root
import PySide6.QtCore
from Sagittarius_Elite_Warrior.src.modules.market_data.cli import sync_cmd   # ImportError
```

## Symptom
```
src/modules/market_data/application/sync/sync_market_data/command.py:4: from pydantic import BaseModel, Field, field_validator
pydantic/__init__.py:446 -> pydantic/fields.py:23 (from . import types) -> pydantic/__init__.py:437 -> _migration.py wrapper
pydantic/_internal/_validators.py:25: from pydantic.errors import PydanticSchemaGenerationError
shibokensupport/signature/loader.py:71: feature_imported -> feature.py:158 _mod_uses_pyside -> inspect.getsource -> unwrap -> hasattr(module, '__wrapped__')
pydantic/_migration.py:280: from ._internal._validators import import_string
ImportError: cannot import name 'import_string' from partially initialized module 'pydantic._internal._validators'
```

## Root cause
Established by an import-order trace in the failing worker (a meta-path finder recording the first import of `pydantic`, `PySide6`, `pydantic._internal._validators`, `pydantic.fields`) and reproduced in a plain interpreter, at `0ccc921`:

1. `tests/integration/modules/bots/conftest.py:24` → `grid_fake_exchange.py:94` → `src/shell/composition_root.py:143` → `sagittarius_engine/middleware/pydantic_validation_middleware.py:11` (`from pydantic import BaseModel, ValidationError`). pydantic 2.13 loads lazily: this loads `pydantic.errors` and `BaseModel` but not `pydantic.fields` or `pydantic._internal._validators`. In `src/main.py` the same import (`composition_root`, line 48) precedes the GUI's PySide6 import.
2. pytest-qt imports PySide6 in `pytest_configure` (`qt_compat.py:66`), installing the `shibokensupport.feature` import hook.
3. The first model class defined afterwards (`sync_market_data/command.py:4`) loads `pydantic._internal._validators`. Its line 25, `from pydantic.errors import ...`, hands the hook a module it has not seen (`pydantic.errors` was imported before the hook existed). The hook calls `inspect.getsource`, which does `hasattr(module, '__wrapped__')`; `pydantic.errors`' migration `__getattr__` then imports `_validators` again, which is partially initialised → `ImportError` (not `AttributeError`, so `hasattr` does not absorb it).

When another module already forced `_validators` or touched `pydantic.errors` after PySide6, the run passes; that is why the failure depends on which tests share a worker. No net was silent that a case study would close: the guard itself caught it, in an order CI does not use.

## Fix
`src/shell/composition_root.py`: `import_module("pydantic.fields")` directly after the imports. That import loads `_validators` (verified: `import pydantic.fields`, `import pydantic._internal._validators` and `from pydantic import Field, field_validator` each make the reproduction pass), before any PySide6 import. It sits at the one place the application imports the engine's middleware (`grep` over `src/` and `tests/`: only `composition_root.py:143`), so every route into the half-loaded state goes through it, and it is an import statement's worth of cost, not a workaround in the test. The engine is a separate repository and was not touched.

## Regression test
`tests/unit/shell/test_pydantic_is_whole_before_pyside_loads.py::test_a_model_class_defines_after_the_composition_root_then_pyside6_loaded` — a fresh interpreter imports `composition_root`, then PySide6, then two modules that define pydantic models. Before the fix it failed with the `ImportError` above (`import_string ... partially initialized module`); after, it passes. It runs the real modules, with no double.

## Verification
- Test red before the fix (same `ImportError`), green after: `1 passed`.
- The failing run above, three times in a row after the fix: `1482 passed` each (before the fix: `1 failed, 1481 passed`, twice).
- Positive proof the new mechanism ran: with the fix, `pydantic.fields` is in `sys.modules` straight after `import composition_root` (the regression test's child process imports the model modules without error).
- Commit tier and the PR's `ci-local.ps1 -Full` run: see the pull request.

Sequence diagrams: on the fix's pull request (`fix-bug-rule.md` §6.1).
