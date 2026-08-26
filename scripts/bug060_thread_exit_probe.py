"""Name the non-daemon threads alive at TRUE interpreter exit (BUG-060/BUG-052).

Load it as a pytest plugin, not a conftest fixture::

    PYTHONPATH=scripts pytest tests -p bug060_thread_exit_probe -n 6

@par Why `threading._register_atexit` and not `atexit` or `pytest_sessionfinish`
`pytest_sessionfinish` runs while pytest is still tearing down, long before
anything joins a thread. The plain `atexit` module is worse than useless
here: it runs too LATE. CPython finalization order is

    Py_FinalizeEx -> threading._shutdown() -> ... -> atexit callbacks

and `threading._shutdown()` both runs the `_threading_atexits` list *and*
joins every non-daemon thread (verified in its own source: "Call registered
threading atexit functions before threads are joined", then "Join all
non-deamon threads"). `concurrent.futures.thread._python_exit` — the hook
that joins every executor worker regardless of what `shutdown(wait=...)`
was told, and therefore the thing that actually hangs a process — is on
that list, not on `atexit`.

So a plain `atexit` probe reports *after* every non-daemon thread has
already been joined, and can only ever print nothing. An earlier version of
this file did exactly that, and its silence was mistaken for evidence that
nothing leaks. Registering on the same list, after importing
`concurrent.futures.thread`, puts this report immediately before
`_python_exit` — the list is walked in reverse.

@par Why this measures thread liveness and not thread identity
An earlier version diffed `threading.enumerate()` idents around each test
and produced two whole classes of false positive:

  1. it measured in `pytest_runtest_teardown`, which runs *before* the
     item's fixture finalizers — so every test that legitimately builds and
     tears down an executor looked like a leak (18 of them);
  2. it reported the xdist controller's own `MainThread` as newly created.

Both read exactly like a real finding. A probe that cannot be shown to
catch a real leak is worse than no probe, so before trusting this one,
verify it against a deliberate leak::

    def test_leaks_on_purpose():
        pool = ThreadPoolExecutor(max_workers=1)
        pool.submit(lambda: None).result()   # force the worker to exist
        globals().setdefault("_keep", []).append(pool)   # never shut down

It must name that test's worker. The version in this file does.

Under xdist every worker is its own process and writes its own lines,
tagged with `PYTEST_XDIST_WORKER`.
"""

from __future__ import annotations

import concurrent.futures.thread  # noqa: F401 — puts _python_exit on the list first
import os
import sys
import threading

_OUT = os.environ.get("BUG060_PROBE_OUT", "")
_WORKER = os.environ.get("PYTEST_XDIST_WORKER", "main")


def _survivors() -> list[str]:
    return sorted(
        thread.name
        for thread in threading.enumerate()
        if not thread.daemon
        and thread.is_alive()
        and thread is not threading.main_thread()
    )


def _report() -> None:
    alive = _survivors()
    if not alive:
        return
    line = f"[{_WORKER}] AT INTERPRETER EXIT -> {', '.join(alive)}"
    if _OUT:
        with open(_OUT, "a") as handle:
            handle.write(line + "\n")
    else:
        print(line, file=sys.stderr)


# Private API on purpose, and there is no public equivalent: the public
# `atexit` module runs after `threading._shutdown()` has already joined
# every non-daemon thread (see the module docstring), which is exactly
# the mistake this probe exists to avoid. typeshed does not declare it.
threading._register_atexit(_report)  # type: ignore[attr-defined]
