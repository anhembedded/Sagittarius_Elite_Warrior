# BUG-044 — Published `sagittarius_engine` 2.3.0 cannot be imported: Python-2 `except` syntax

**Reported:** 2026-08-25, while standing up a clean environment for `EPIC-009`.
**Severity:** 🔴 **P1** — anyone installing per `install-rule.md` Option 1 gets an
engine that raises `SyntaxError` on import. Blocks every fresh environment and CI.
**Status:** 🔴 Open

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

### Note on the concurrent engine session

A Claude session (`session_01WUsUMutFtqiMjemMTiTtWY`, idle/review-ready) reports
*"dev env setup complete: Python 3.14rc2, .venv, 953 tests pass"* for this
repository. Those two facts cannot both hold on `main` as published: the suite
does not collect there. Its branch `claude/dazzling-clarke-knjtv4` **does not
exist on the remote**, so that work is local to that session's container. The
most likely reading is that the session already carries a local fix it has not
pushed — which should be confirmed before anyone duplicates the work.

## Fix

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
