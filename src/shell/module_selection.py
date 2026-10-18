"""Which bounded contexts a run builds (`PRO-014`).

Every context costs its imports whether or not the run uses it: the whole list
took about 1.1 s of the 2 s a `bot list` spent before its first line, to read a
file. A command that names the contexts it needs (`"modules"` in
`cli_commands.json`, read by `support/cli_host/command_access.py`) gets those
and the contexts they depend on, nothing else; a command that names none gets the
whole list, which is every command that existed before the key and the desktop
application.

The closure is not optional. The Engine refuses a context whose declared
`dependencies` are missing, and a context reads its suppliers' ports at
`register()`/`boot()` (`bots` resolves `trading`'s venue ports even to list),
so "bots only" is "bots and its suppliers" - the price of the declaration is
the suppliers' imports, and the saving is every other context's.

Extension cases:
  · a new context - one `ModuleEntry` in `shell/modules.py`; this function does not change;
  · a command that needs more or fewer contexts - its `"modules"` list.
"""

from __future__ import annotations

from collections.abc import Collection

from Sagittarius_Elite_Warrior.src.shell.modules import ModuleEntry


def select_modules(
    entries: tuple[ModuleEntry, ...], needed: Collection[str] | None
) -> tuple[ModuleEntry, ...]:
    """`entries` in their own order, cut to `needed` and what those depend on.

    `None` selects the whole list.

    @raise ValueError a name in `needed` is not a context in `entries` (a typo in a
        declaration would otherwise boot a run missing the thing it asked for).
    """
    if needed is None:
        return entries
    by_id = {entry.module_id: entry for entry in entries}
    unknown = sorted(set(needed) - by_id.keys())
    if unknown:
        raise ValueError(
            f"no such bounded context: {', '.join(unknown)} (known: {', '.join(by_id)})"
        )
    wanted: set[str] = set()
    pending = list(needed)
    while pending:
        module_id = pending.pop()
        if module_id in wanted:
            continue
        wanted.add(module_id)
        pending.extend(by_id[module_id].load().dependencies)
    return tuple(entry for entry in entries if entry.module_id in wanted)
