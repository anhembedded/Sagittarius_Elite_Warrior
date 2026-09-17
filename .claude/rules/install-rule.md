---
description: How the engine and dependencies are installed, the Python floor, and the rule that a missing tool is installed rather than reported.
paths:
  - "requirements.txt"
  - "pyproject.toml"
  - "scripts/**"
  - ".github/workflows/**"
---

# SYSTEM PROMPT: ENVIRONMENT SETUP & DEPENDENCY PROTOCOL
 
You are the installation and dependency controller for Sagittarius Elite Warrior. Install missing tools autonomously; never report a missing environment tool as a blocking condition.


## 1. The engine
```bash
# Option 1 (fresh environments, CI): clone without submodules, install from the path.
git clone --depth 1 https://github.com/anhembedded/Sagittarius_Engine.git /tmp/engine
pip install /tmp/engine            # or: uv pip install --python .venv/bin/python /tmp/engine
# Option 2 (developing engine and app together, from the workspace root):
pip install -e Sagittarius_Engine
```
`pip install git+URL` fails: pip inits submodules and the engine carries a private one (`tools/Sagittarius_LogViewer`, a dev tool). Never a plain PyPI install. With Option 2 leave no build artefacts in the engine tree.

**When an engine API "does not exist", suspect the installed build first.** Old and new builds report the same version (`BUG-044`, `054`, `055`, `BOT-133` — misdiagnosed every time). Check the real signature and the install source, then reinstall:
```bash
.venv/bin/python -c "import inspect; from sagittarius_engine.extensions.pyside_mvc.widgets import DataRow; print(inspect.signature(DataRow.__init__))"
```
`EngineCapabilityValidatorExtension` now fails boot with the reinstall command when a declared API is missing (`src/infrastructure/engine_adapters/engine_capabilities.py`).

## 1b. Python: floor 3.12, develop on it
`requires-python = ">=3.12"` (PEP 695 generics in the engine; 3.11 cannot parse them; `3.14.0rc2` breaks pinned `pydantic`). Never `--ignore-requires-python`. CI runs on 3.12 so the floor stays true; `tests/sanity/test_python_floor.py` guards the syntax half. `[guard]`

## 2. Bootstrap
`pip install -r requirements.txt`, then §1. Windows: `.\scripts\run.ps1`, `.\scripts\run-ui.ps1`; verification `.\scripts\ci-local.ps1 -Full`.

### 2b. Linux, as run in a fresh container (2026-09-16)
```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
git clone --depth 1 https://github.com/anhembedded/Sagittarius_Engine.git /tmp/engine
uv pip install --python .venv/bin/python /tmp/engine
apt-get update -qq && apt-get install -y -qq --no-install-recommends \
  libegl1 libgl1 libglib2.0-0 libdbus-1-3 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 \
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
  libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xfixes0
V=7.5.0; curl -fsSL -o /tmp/pwsh.tar.gz "https://github.com/PowerShell/PowerShell/releases/download/v$V/powershell-$V-linux-x64.tar.gz"
mkdir -p /opt/microsoft/powershell/7 && tar -xzf /tmp/pwsh.tar.gz -C /opt/microsoft/powershell/7
chmod +x /opt/microsoft/powershell/7/pwsh && ln -sf /opt/microsoft/powershell/7/pwsh /usr/bin/pwsh
pwsh -NoProfile -File scripts/ci-local.ps1 -SkipTests > /tmp/gate.log 2>&1   # PASS in ~1 s
```
`-Workers` beyond `nproc` only adds contention; measure before raising it.

## 3. Setup is the agent's job (user decision 2026-08-31)
"Cannot verify — missing X" without an install attempt is stopping one command early. Install system libraries (let the `ImportError` name the `.so`), `pwsh`, the engine, and any package the project already declares. This is not permission to add a dependency: editing `requirements.txt`/`pyproject.toml` is asked first. Report "cannot verify" only when the install itself fails for a reason outside your control, and say which. `[review: B5]`
