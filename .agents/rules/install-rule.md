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

The engine declared `requires-python >= 3.14` until 2026-08-25, which was higher
than anything it needed and made its wheel refuse to install on interpreters it
demonstrably ran on. **Corrected upstream** (engine PR #177, now `>=3.12`), so
Option 1 installs plainly — do **not** pass `--ignore-requires-python`; if that
flag is ever needed again, the constraint has regressed and it belongs in a bug
report, not in a command line.

Note when pinning: the fixed engine still reports version `2.3.0`, the same
number the broken build carried (see
[`BUG-044`](../../Tasks/bug_report/completed/BUG-044_published_engine_has_python2_except_syntax.md)).
An environment created before 2026-08-25 must reinstall rather than trust the
version string.

### Triệu chứng của môi trường Engine cũ (bẫy này đã cắn lần thứ hai)

`BUG-044` là lần đầu; [`BUG-054`](../../Tasks/bug_report/completed/BUG-054_settings_screen_crashes_on_missing_stylerole_members.md)
và [`BUG-055`](../../Tasks/bug_report/completed/BUG-055_data_row_action_stretch_not_in_installed_engine.md)
(2026-08-26) là lần thứ hai, và cả hai **ban đầu bị chẩn đoán sai** thành "code
app tham chiếu API không tồn tại":

```
AttributeError: type object 'StyleRole' has no attribute 'HEADING'
TypeError: DataRow.__init__() got an unexpected keyword argument 'action_stretch'
```

Cả ba API đó **có thật** trong repo Engine. Chỉ là bản cài cũ hơn — và **cả hai
bản đều báo `2.3.0`**, nên `pip show` không giúp gì.

**Khi một API Engine "không tồn tại", câu hỏi đầu tiên là "bản đang cài có phải
bản mới nhất không?"**, trước khi kết luận app dùng sai. Kiểm bằng chữ ký thật,
không bằng version string:

```bash
.venv/bin/python -c "import inspect; from sagittarius_engine.extensions.pyside_mvc.widgets import DataRow; print(inspect.signature(DataRow.__init__))"
```

Cũng kiểm **nguồn** cài, không chỉ phiên bản — lần này bản lỗi thời đến từ một
`file:///...` local checkout (Option 2) đã cũ, chứ không phải từ GitHub:

```bash
uv pip list --python .venv/bin/python | grep sagittarius
```

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

### 2b. Trên Linux: phải cài PowerShell trước, nếu không cổng bắt buộc không chạy được

`ci-rule.md` §1 gọi `scripts/ci-local.ps1` là **nguồn chân lý duy nhất** cho
verification, và nó là file `.ps1`. Trên một máy Linux sạch, `pwsh` không có
sẵn — nghĩa là cổng bắt buộc **không thể chạy**, và rất dễ trượt sang chạy tay
từng lệnh rồi tưởng là tương đương. Không tương đương: chạy tay bỏ mất bước
quét log cuối cùng và phần chạy Sanity song song mà script tự lo.

```bash
V=7.5.0
curl -fsSL -o /tmp/pwsh.tar.gz \
  "https://github.com/PowerShell/PowerShell/releases/download/v$V/powershell-$V-linux-x64.tar.gz"
mkdir -p /opt/microsoft/powershell/7
tar -xzf /tmp/pwsh.tar.gz -C /opt/microsoft/powershell/7
chmod +x /opt/microsoft/powershell/7/pwsh
ln -sf /opt/microsoft/powershell/7/pwsh /usr/bin/pwsh
pwsh --version        # PowerShell 7.5.0
```

Tarball chứ không phải repo apt của Microsoft: không cần thêm khoá GPG hay
apt source, và không đụng gì tới hệ thống ngoài một thư mục cộng một symlink.

Sau đó chạy đúng như trên Windows, đường dẫn đổi dấu gạch:

```bash
pwsh -NoProfile -File scripts/ci-local.ps1 -Full
```

**Đừng tăng `-Workers` để chạy nhanh hơn nếu chưa đo.** Mặc định 6 là
"benchmark sweet spot" của máy tác giả. Đo thật trên một container **4 nhân**:

| `-Workers` | Pha pytest |
| :-: | :--- |
| 6 (mặc định) | ~147s |
| 12 | 150.5s |

Tăng gấp đôi worker trên 4 nhân **không đổi gì** — không nhanh hơn, cũng không
chậm hơn đáng kể. Số worker vượt số nhân chỉ thêm tranh chấp, không thêm thông
lượng. Kiểm `nproc` trước, và coi mọi con số thời gian là của riêng từng máy.

Toàn bộ full gate trên máy này: **~2 phút 30** (`ci-local.ps1 -Full`, gồm cả
lint/format/mypy và tier Sanity chạy song song).

---

## 3. Mandatory Rules for AI Agents & Automated Tools

1. **Never Attempt Plain PyPI Install for Engine:**
   - Always install via GitHub repository URL or local editable path as defined above.
   - Do NOT run plain `pip install sagittarius-engine` or `pip install sagittarius_engine` without the git URL prefix.

2. **Clean Submodule Tree Preservation:**
   - If using Option 2 (local editable installation), ensure no temporary build artifacts, `.egg-info`, or `__pycache__` leave `Sagittarius_Engine` in a `(dirty)` git state.
   - In automated agent runs, prefer Option 1 or clean with `git -C Sagittarius_Engine clean -fdx`.
