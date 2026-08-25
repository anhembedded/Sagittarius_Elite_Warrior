# BUG-044 — Published `sagittarius_engine` 2.3.0 cannot be imported: Python-2 `except` syntax

**Reported:** 2026-08-25, while standing up a clean environment for `EPIC-009`.
**Severity:** 🔴 **P1** — anyone installing per `install-rule.md` Option 1 gets an
engine that raises `SyntaxError` on import. Blocks every fresh environment and CI.
**Status:** ✅ **Fixed 2026-08-25** — merged upstream (PR #175), verified from
this repository by a clean install, full gate green.

## Symptom

```
File ".../sagittarius_engine/infrastructure/config/config_manager.py", line 115
    except ValueError, TypeError:
           ^^^^^^^^^^^^^^^^^^^^^
SyntaxError: multiple exception types must be parenthesized
```

Reproduced on a clean checkout:

```bash
pip install git+https://github.com/anhembedded/Sagittarius_Engine.git   # install-rule.md Option 1
python -c "from sagittarius_engine.infrastructure.config.config_manager import ConfigManager"
```

`import sagittarius_engine` alone succeeds, which is why this hides: the package
`__init__` does not reach these modules. The failure only appears once anything
touches config, the thread manager, or the FSM — i.e. as soon as the app boots.

## Scope — 4 files, 5 sites, engine 2.3.0

| File | Line | Statement |
| :--- | ---: | :--- |
| `extensions/thread_manager/thread_manager_module.py` | 39 | `except ValueError, TypeError:` |
| `infrastructure/config/dict_config.py` | 33 | `except ValueError, TypeError:` |
| `infrastructure/config/config_manager.py` | 115 | `except ValueError, TypeError:` |
| `infrastructure/config/config_manager.py` | 167 | `except OSError, json.JSONDecodeError:` |
| `infrastructure/config/json_source.py` | 27 | `except FileNotFoundError, json.JSONDecodeError:` |

`except A, B:` is Python 2 syntax. It is a `SyntaxError` on **every** Python 3,
so no interpreter version makes this work — this is not a 3.13-versus-3.14 issue.

## Confirmed against the engine repository itself, 2026-08-25

Not only the published wheel — the defect is live on `main`
(`2d9154b`, the current HEAD of `anhembedded/sagittarius_engine`). All five
sites are present in the source tree, and **the engine's own test suite cannot
be collected**:

```
$ pytest tests/infrastructure/config/test_config_manager.py --collect-only
sagittarius_engine/infrastructure/config/__init__.py:1: in <module>
    from .config_manager import ConfigManager
E     File ".../config_manager.py", line 115
E       except ValueError, TypeError:
E   SyntaxError: multiple exception types must be parenthesized
```

`tests/infrastructure/config/test_config_manager.py:6` imports `ConfigManager`
directly, so this is not a test that merely *could* fail — the engine repository
is red for its own suite, right now, on its default branch.

The introduction date could not be established: the checkout used here is
shallow (`--depth 1`), so `git log -- <file>` cannot see past HEAD. Worth a
`git bisect` on a full clone, because the answer decides whether any released
version is safe.

### Verified independently in this repository's session, 2026-08-25

Everything below was checked against a full clone
(`git fetch --unshallow`, 760 commits, tags `v1.0.0`/`v2.1.0`/`v2.2.0`), not
taken from a report.

| Claim | Verdict |
| :--- | :--- |
| Introduced by `df51202` *"fix(lint): consolidate ruff config; apply the rule set for the first time"* (2026-08-23) | ✅ **5 sites at `df51202`, 0 at its parent `1e300ac`** |
| `v2.1.0` affected | ✅ 5 sites |
| `v2.2.0` affected | ✅ 5 sites |
| `v1.0.0` affected | ❌ 0 sites — predates the file |
| Fix branch closes all five | ✅ all parenthesized; `compileall` over the package reports **0 errors** |

**Both published tags ship an unimportable package.** `pip install
git+...@v2.1.0` and `@v2.2.0` both yield an engine that raises `SyntaxError`.

The commit that broke it was a **lint-tidying commit** — which is the part worth
remembering, and leads directly to the root cause below.

### Root cause of the *escape*: `ruff check` passes on unparseable Python

Reproduced here from scratch, on a different ruff version than the one upstream
used (0.15.8 vs 0.16.4), so it is not version-specific:

```
$ cat ruff_blindspot.py
try:
    pass
except ValueError, TypeError:
    pass

$ ruff check ruff_blindspot.py
All checks passed!            exit=0

$ python3 -c "import ast; ast.parse(open('ruff_blindspot.py').read())"
SyntaxError: multiple exception types must be parenthesized
```

Ruff's parser accepts the bare tuple; CPython does not. So the lint gate was
green on code no interpreter can run — and the commit that introduced the defect
was itself a lint commit. `mypy` does catch it, but upstream CI's other jobs
declare `needs: lint`, so once lint went red for unrelated reasons everything
else was **skipped, not run**.

### Correction to this report's first version

It originally reasoned that the concurrent engine session *"most likely already
carries a local fix it has not pushed"*. **That was wrong.** That container's
tree matched `main` exactly — all five sites broken, nothing fixed — and it had
no `.venv` and Python 3.11, so the *"Python 3.14rc2, 953 tests pass"* summary
described neither container. The inference was drawn from an untrustworthy
session summary rather than from the repository; recorded here because the
lesson is the same one this bug teaches.

Parenthesise all five: `except (A, B):`. Repository: `anhembedded/Sagittarius_Engine`.

## Why no existing test caught it

The bot repository's CI runs against a **local editable checkout** of the engine
(`install-rule.md` Option 2), which evidently differs from what is published on
GitHub. Nothing in either repository verifies that the *published* artefact is
importable, so the two can drift indefinitely without a red build. Same class as
[`BUG-043`](../completed/BUG-043_run_ui_cannot_import_local_engine.md), where a
launch path could not import the engine while tests were green.

## Regression guard to add

An engine-side CI step that installs the built wheel into a clean environment
and imports every module (`python -m compileall` plus an import sweep). A syntax
error in a published package is the cheapest possible thing to detect and the
most expensive to discover downstream.

## Also worth checking

`pyproject.toml` declares `requires-python >= 3.14`, but no released CPython
3.14 was reachable in this environment (only `3.14.0rc2`, on which the pinned
`pydantic` fails: `typing._eval_type() got an unexpected keyword argument
'prefer_fwd_module'`). The engine imports and runs correctly on **3.13** once
the five `except` clauses are fixed, so the `>= 3.14` floor may be higher than
the code actually requires. Verify before it forces anyone onto a release
candidate.


## Downstream impact on this repository

`tests/sanity/`'s first green run was measured against a **hand-patched** local
engine. It has since been re-measured against the real fix branch installed
clean — **16 passed, no local modification** — so `EPIC-009`'s numbers stand on
a legitimate engine.

Two items this repository must decide separately:

- **Pin.** `pyproject.toml`'s notes reference engine `2.3.0`. Both published
  tags carry the defect, so any pin must name a release made *after* the fix
  lands on `main`.
- **`requires-python`.** Upstream declares `>= 3.14`, but the real syntax floor
  is **3.12** (PEP 695 generics in `repository.py`, `state_machine.py`,
  `declarative_state_machine.py`), and the engine runs correctly on 3.12 and
  3.13. The declared floor makes the wheel uninstallable on interpreters it
  demonstrably works on — and no stable CPython 3.14 was reachable here, only
  `3.14.0rc2`, on which this project's pinned `pydantic` fails
  (`typing._eval_type() got an unexpected keyword argument 'prefer_fwd_module'`).
  The engine imports no pydantic, so that failure is ours to own, not theirs.


## Closing verification, 2026-08-25

Checked from this repository against `anhembedded/sagittarius_engine` `main`
(`2b72557`), not taken from a report:

| Check | Result |
| :--- | :--- |
| Python-2 `except` sites in the package on `main` | **0** |
| `requires-python` | now `>=3.12` (was `>=3.14`) — PR #177 |
| `pip install git+...` **without** `--ignore-requires-python` | ✅ succeeds |
| `compileall` over the installed package | ✅ 0 errors, no local patch |
| `from ...config_manager import ConfigManager` | ✅ imports clean |

Downstream gate on Python 3.12.3 with that engine installed plainly:

```
1,761 passed, 0 failed, exit 0      log scan FAILED/ERROR/Traceback -> 0
mypy 142 files / 0 errors           ruff + ruff format -> clean
```

### One thing left open deliberately

The fixed engine still reports **version `2.3.0`** — the same number the broken
build carried. Any environment that installed `2.3.0` before 2026-08-25 holds an
unimportable package under a version string that now also names a working one.
A version string that identifies two different artefacts cannot be pinned
against.

This is upstream's call, not this repository's, but it is worth raising: a
patch release (`2.3.1`) would make the fix nameable. Until then, "engine 2.3.0"
in `pyproject.toml`'s notes and in `install-rule.md` means *whatever `main` held
when you installed*, and any environment predating the fix must reinstall rather
than trust the version.
