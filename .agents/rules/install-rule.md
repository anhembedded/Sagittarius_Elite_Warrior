---
trigger: always_on
---

# Sagittarius Engine & Dependency Installation Guidelines

All developers and AI assistants working on this repository MUST strictly follow these installation options and guidelines when setting up the environment or resolving `sagittarius_engine` dependencies.

---

## 1. Sagittarius Engine Installation Options

### Option 1: Install from GitHub Repository (Production / Shared / CI)
When installing in fresh environments, CI pipelines, or when sharing builds, install `sagittarius_engine` directly from the official GitHub repository:

```bash
pip install git+https://github.com/anhembedded/Sagittarius-Engine.git
```

For editable / upgrade mode from GitHub:
```bash
pip install --upgrade --force-reinstall git+https://github.com/anhembedded/Sagittarius-Engine.git
```

---

### Option 2: Local Editable Installation (Development & Debugging)
When actively developing or debugging both the engine and the bot concurrently in a local monorepo / submodule setup:

```bash
# From workspace root
pip install -e Sagittarius-Engine
```

---

## 2. Full Environment Bootstrap

To install all application dependencies and tools:

```bash
# 1. Base requirements
pip install -r requirements.txt

# 2. Sagittarius Engine (GitHub)
pip install git+https://github.com/anhembedded/Sagittarius-Engine.git
```

Or run the automated setup scripts:
- **Windows (PowerShell):** `.\scripts\run.ps1` or `.\scripts\run-ui.ps1`
- **Verification:** `.\scripts\ci-local.ps1 -UnitOnly`

---

## 3. Mandatory Rules for AI Agents & Automated Tools

1. **Never Attempt Plain PyPI Install for Engine:**
   - Always install via GitHub repository URL or local editable path as defined above.
   - Do NOT run plain `pip install sagittarius-engine` or `pip install sagittarius_engine` without the git URL prefix.

2. **Clean Submodule Tree Preservation:**
   - If using Option 2 (local editable installation), ensure no temporary build artifacts, `.egg-info`, or `__pycache__` leave `Sagittarius-Engine` in a `(dirty)` git state.
   - In automated agent runs, prefer Option 1 or clean with `git -C Sagittarius-Engine clean -fdx`.
