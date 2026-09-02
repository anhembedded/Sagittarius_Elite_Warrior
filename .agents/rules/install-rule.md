---
trigger: always_on
---

# Sagittarius Engine & Dependency Installation Guidelines

All developers and AI assistants working on this repository MUST follow these installation
options and guidelines when setting up the environment or resolving `sagittarius_engine`.

## 1. Sagittarius Engine Installation Options

**Option 1 — GitHub** (production / shared / CI / fresh environments), repo
[Sagittarius_Engine](https://github.com/anhembedded/Sagittarius_Engine); **Option 2 —
local editable**, when developing/debugging engine and bot together.

```bash
# Option 1
pip install git+https://github.com/anhembedded/Sagittarius_Engine.git
pip install --upgrade --force-reinstall git+https://github.com/anhembedded/Sagittarius_Engine.git
# Option 2 (from workspace root)
pip install -e Sagittarius_Engine
```

## 1b. Python version — floor 3.12, and develop *on* it

`pyproject.toml` declares `requires-python = ">=3.12"`. **Create the venv with Python 3.12
and run CI on it**, even though 3.13 also works.

- **Floor, not preference:** the engine uses PEP 695 generics (`class Foo[T]:`) in
  `extensions/persistence/repository.py`, `extensions/fsm/state_machine.py`,
  `extensions/fsm/declarative_state_machine.py`; Python ≤3.11 **cannot parse them at all**.
  3.12 and 3.13 are both green; on `3.14.0rc2` the pinned `pydantic` fails
  (`typing._eval_type() got an unexpected keyword argument 'prefer_fwd_module'`).
- Do **not** pass `--ignore-requires-python`. If it is ever needed again the engine's
  constraint has regressed — that is a bug report, not a command line.
- **CI must run *on* the floor, not merely declare it:** a developer on 3.13 can use
  3.13-only syntax, watch every test pass locally, and leave `requires-python = ">=3.12"`
  silently false — breaking only for whoever installs on the floor.
  `tests/sanity/test_python_floor.py` guards the syntax half interpreter-independently
  (reads the floor from `pyproject.toml`, re-parses every first-party module via
  `ast.parse(feature_version=...)`, names the offending file/line); running CI on 3.12
  covers the standard library, which no syntax check can reach.

### When an Engine API "doesn't exist", suspect the installed build first

Current and outdated engine builds both report version `2.3.0`, so `pip show` proves
nothing. The trap has bitten twice:
[`BUG-044`](../../Tasks/bug_report/completed/BUG-044_published_engine_has_python2_except_syntax.md)
(published engine unimportable), then
[`BUG-054`](../../Tasks/bug_report/completed/BUG-054_settings_screen_crashes_on_missing_stylerole_members.md)
/ [`BUG-055`](../../Tasks/bug_report/completed/BUG-055_data_row_action_stretch_not_in_installed_engine.md)
(2026-08-26) — `StyleRole has no attribute 'HEADING'` and
`DataRow.__init__() got an unexpected keyword argument 'action_stretch'`, both **initially
misdiagnosed** as "app code references a non-existent API" when both APIs **do exist**
upstream and only the installed build was old. Check the real signature, and the install
**source** (BUG-055's stale build came from an old local `file:///...` checkout, not
GitHub):

```bash
.venv/bin/python -c "import inspect; from sagittarius_engine.extensions.pyside_mvc.widgets import DataRow; print(inspect.signature(DataRow.__init__))"
uv pip list --python .venv/bin/python | grep sagittarius
```

Any environment created before 2026-08-25 must reinstall rather than trust the version.

## 2. Full Environment Bootstrap

For [Sagittarius_Elite_Warrior](https://github.com/anhembedded/Sagittarius_Elite_Warrior):
`pip install -r requirements.txt`, then the engine per §1. Or the automated scripts —
**Windows (PowerShell):** `.\scripts\run.ps1` / `.\scripts\run-ui.ps1`;
**Verification:** `.\scripts\ci-local.ps1 -Full`.

### 2b. On Linux: install PowerShell first, or the mandatory gate cannot run

`ci-rule.md` §1 makes `scripts/ci-local.ps1` the **single source of truth** for verification,
and it is a `.ps1` file. A clean Linux machine has no `pwsh`, so the mandatory gate **cannot
run**; running each command by hand is **not equivalent** — you lose the final log-scan step
and the parallel Sanity run. Use the tarball (no GPG key or apt source needed, just one
directory plus one symlink):

```bash
V=7.5.0
curl -fsSL -o /tmp/pwsh.tar.gz \
  "https://github.com/PowerShell/PowerShell/releases/download/v$V/powershell-$V-linux-x64.tar.gz"
mkdir -p /opt/microsoft/powershell/7
tar -xzf /tmp/pwsh.tar.gz -C /opt/microsoft/powershell/7
chmod +x /opt/microsoft/powershell/7/pwsh
ln -sf /opt/microsoft/powershell/7/pwsh /usr/bin/pwsh
pwsh --version        # PowerShell 7.5.0
pwsh -NoProfile -File scripts/ci-local.ps1 -Full
```

**Do not raise `-Workers` without measuring:** on a 4-core container, 6 (the default) and 12
workers gave the same pytest time (~147s vs 150.5s) — workers beyond the core count only add
contention. Check `nproc` first; every timing figure is specific to the machine it came from.

## 3. Environment setup is the agent's job — install what verification needs

**Added 2026-08-31 (user request).** Reporting "cannot verify — missing X" without first
trying to install X is stopping one command early, not hitting a wall. Missing tooling, a
missing system library, or a dependency the project **already declares** but this
environment hasn't installed yet is something to install, not a reason to skip the gate:

- System packages the app's own GUI stack needs to boot under `QT_QPA_PLATFORM=offscreen`
  (Qt's EGL/GL/font/D-Bus loaders) — install with
  `apt-get update && apt-get install -y <package>`. On one clean container this took
  `libegl1` (which pulled in `libegl-mesa0`), `libgl1`, `libxkbcommon0`, `libfontconfig1`,
  `libdbus-1-3`; the exact list can drift with the base image, so let the actual
  `ImportError` / `cannot open shared object file` name the missing `.so` rather than
  trusting this list.
- `pwsh` itself — §2b above.
- `sagittarius_engine` — §1/§2 above. It is a genuinely separate repo, but still something
  to `pip install`, not a reason to stop.
- Any package already pinned in `requirements.txt` / `pyproject.toml` that simply isn't
  installed yet in *this* environment (`pip install PySide6==<pinned version>`, matching
  the pin).

This is **not** the same permission as adding a new dependency to the project. Installing
an already-declared or environment-only tool into the current sandbox is setup; editing
`requirements.txt` / `pyproject.toml` to add something the project has never depended on is
a design decision and still requires asking first (`.agents/Skills/README.md` §6,
`architecture-rule.md`). The test: does the install change a manifest file committed to the
repo? If yes, ask first. If it only changes what's present on disk in this environment,
install it and move on.

Only report "cannot verify" once an install attempt itself fails for a reason outside your
control — no network, a registry/proxy blocking the package, or missing credentials/access
to a private repo you were never given. Say plainly which install failed and why, rather
than working around the gap by skipping the gate.

## 4. Mandatory Rules for AI Agents & Automated Tools

1. **Never attempt a plain PyPI install for the Engine.** Always the GitHub URL or the
   local editable path above — never plain `pip install sagittarius-engine` /
   `pip install sagittarius_engine` without the git URL.
2. **Keep the submodule tree clean.** With Option 2, no build artifacts, `.egg-info` or
   `__pycache__` may leave `Sagittarius_Engine` `(dirty)`. In automated agent runs prefer
   Option 1, or clean with `git -C Sagittarius_Engine clean -fdx`.
