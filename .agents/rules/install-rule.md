---
trigger: always_on
---

# Sagittarius Engine & Dependency Installation Guidelines

All developers and AI assistants working on this repository MUST strictly follow these installation options and guidelines when setting up the environment or resolving `sagittarius_engine` dependencies.

---

## 1. Sagittarius Engine Installation Options

### Option 1: Install from GitHub Repository (Production / Shared / CI)
When installing in fresh environments, CI pipelines, or when sharing builds, install `sagittarius_engine` directly from the official GitHub repository ([Sagittarius_Engine](https://github.com/anhembedded/Sagittarius_Engine)):

```bash
pip install git+https://github.com/anhembedded/Sagittarius_Engine.git
```

For editable / upgrade mode from GitHub:
```bash
pip install --upgrade --force-reinstall git+https://github.com/anhembedded/Sagittarius_Engine.git
```

---

### Option 2: Local Editable Installation (Development & Debugging)
When actively developing or debugging both the engine and the bot concurrently in a local monorepo / multi-repo setup:

```bash
# From workspace root
pip install -e Sagittarius_Engine
```

---

## 1b. Python version — floor 3.12, and develop on it

`pyproject.toml` declares `requires-python = ">=3.12"`. **Create the virtual
environment with Python 3.12 and run CI on it**, even though 3.13 also works.

### Why 3.12 is the floor, not a preference

`sagittarius_engine` uses PEP 695 generic syntax (`class Foo[T]:`) in three
modules — `extensions/persistence/repository.py`,
`extensions/fsm/state_machine.py`,
`extensions/fsm/declarative_state_machine.py`. Python 3.11 **cannot parse them
at all**, so nothing below 3.12 can run this project.

### Why not newer

| Version | Status |
| :--- | :--- |
| 3.11 and below | ❌ Cannot parse the engine (PEP 695) |
| **3.12** | ✅ Verified 2026-08-25 — 1,702 unit + 38 integration + 21 sanity, all green |
| 3.13 | ✅ Equally green; supported, but not what CI should run |
| 3.14 | ❌ No stable CPython 3.14 was reachable, and on `3.14.0rc2` the pinned `pydantic` fails with `typing._eval_type() got an unexpected keyword argument 'prefer_fwd_module'` |

The engine currently declares `requires-python >= 3.14`, which is higher than
anything it actually needs and makes its wheel refuse to install on
interpreters it demonstrably runs on. Until that is corrected upstream, install
it with `--ignore-requires-python`; the constraint is wrong, not the interpreter.

### Why CI must run *on* the floor, not merely declare it

A developer on 3.13 can use 3.13-only syntax, watch every test pass locally, and
leave `requires-python = ">=3.12"` silently false — which only breaks for
whoever installs on the floor. That is the same shape as `BUG-044`, where a
published package could not be imported while its own CI reported green.

`tests/sanity/test_python_floor.py` closes the gap without depending on which
interpreter is in use: it reads the floor from `pyproject.toml` and re-parses
every first-party module at that version via `ast.parse(feature_version=...)`.
Verified in both directions — it passes on 3.12 and 3.13, and rejects 3.13-only
syntax with the offending file and line even while running on 3.13. Running CI
on 3.12 as well makes the guarantee cover the standard library too, which a
syntax check cannot reach.

Raising the floor is a deliberate act: change `requires-python`, and the guard
follows automatically.

---

## 2. Full Environment Bootstrap

To install all application dependencies and tools for [Sagittarius_Elite_Warrior](https://github.com/anhembedded/Sagittarius_Elite_Warrior):

```bash
# 1. Base requirements
pip install -r requirements.txt

# 2. Sagittarius Engine (GitHub)
pip install git+https://github.com/anhembedded/Sagittarius_Engine.git
```

Or run the automated setup scripts:
- **Windows (PowerShell):** `.\scripts\run.ps1` or `.\scripts\run-ui.ps1`
- **Verification:** `.\scripts\ci-local.ps1 -Full`

---

## 3. Mandatory Rules for AI Agents & Automated Tools

1. **Never Attempt Plain PyPI Install for Engine:**
   - Always install via GitHub repository URL or local editable path as defined above.
   - Do NOT run plain `pip install sagittarius-engine` or `pip install sagittarius_engine` without the git URL prefix.

2. **Clean Submodule Tree Preservation:**
   - If using Option 2 (local editable installation), ensure no temporary build artifacts, `.egg-info`, or `__pycache__` leave `Sagittarius_Engine` in a `(dirty)` git state.
   - In automated agent runs, prefer Option 1 or clean with `git -C Sagittarius_Engine clean -fdx`.
