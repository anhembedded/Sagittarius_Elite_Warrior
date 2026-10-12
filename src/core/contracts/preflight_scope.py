"""What one `preflight` run was asked about, and the reads its checks share (`EPIC-038F`).

A scope lives for one run. Besides the operator's request (`--venue`, `--skip`)
it holds a small memo, because five trading checks need the same connection
check and one exchange round trip is enough: `once(key, compute)` computes a
value the first time a key is asked for and hands the same value to everyone
after. The memo dies with the scope, so a second run (the `run` host re-checks
the skew) asks the exchange again.

**A read that has not finished is not asked again.** The runner cuts a check off
at its deadline but cannot stop its thread, so that read may still be in flight
when the next check wants it. The key is marked pending before `compute` runs;
a caller who finds it pending gets `ReadPendingError` at once, instead of
starting the same slow request a second time or waiting for it. A `compute`
that raises leaves nothing behind, so the next caller may try again.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast


class ReadPendingError(Exception):
    """An earlier caller started this read and it has not finished."""

    def __init__(self, key: str) -> None:
        super().__init__(f"the read {key!r} is still waiting for the exchange")
        self.key = key


_PENDING = object()


@dataclass(slots=True)
class PreflightScope:
    #: The venue the operator named (`--venue futures_testnet`), or `None` for every venue with a key.
    venue: str | None = None
    #: Check ids the operator asked not to run (`--skip`).
    skip: frozenset[str] = frozenset()
    _memo: dict[str, object] = field(default_factory=dict, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def once[T](self, key: str, compute: Callable[[], T]) -> T:
        """`compute()` the first time `key` is asked for; the same value after.

        @raise ReadPendingError an earlier call for `key` has not returned.
        """
        with self._lock:
            held = self._memo.get(key, None)
            if held is _PENDING:
                raise ReadPendingError(key)
            if held is not None:
                return cast("T", held)
            self._memo[key] = _PENDING
        try:
            value = compute()
        except BaseException:
            with self._lock:
                del self._memo[key]
            raise
        with self._lock:
            self._memo[key] = value
        return value
