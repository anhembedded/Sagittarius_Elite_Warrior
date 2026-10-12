"""What one `preflight` run was asked about, and the reads its checks share (`EPIC-038F`).

A scope lives for one run. Besides the operator's request (`--venue`, `--skip`)
it holds a small memo, because four trading checks need the same connection
check and one exchange round trip is enough: `once(key, compute)` computes a
value the first time a key is asked for and hands the same value to everyone
after. The memo dies with the scope, so a second run (the `run` host re-checks
the skew) asks the exchange again.

The scope is not thread-safe, on purpose: the runner runs the checks one after
another. A check that outlives its deadline keeps running on a thread of its
own and may still call `once`; the runner never reads that check's result.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast


@dataclass(slots=True)
class PreflightScope:
    #: The venue the operator named (`--venue futures_testnet`), or `None` for every enabled one.
    venue: str | None = None
    #: Check ids the operator asked not to run (`--skip`).
    skip: frozenset[str] = frozenset()
    _memo: dict[str, object] = field(default_factory=dict, repr=False)

    def once[T](self, key: str, compute: Callable[[], T]) -> T:
        """`compute()` the first time `key` is asked for; the same value after."""
        if key not in self._memo:
            self._memo[key] = compute()
        return cast("T", self._memo[key])
