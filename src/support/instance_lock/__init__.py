"""Which process holds a data root: the writer's lock file, and a probe that asks without taking it.

`EPIC-038C` built the probe in the legacy `infrastructure` tree, beside the lock the writer takes
(`InstanceAccess`). `EPIC-047C` lifted the lock primitive and the probe here: the remote link's
bridge is a second process that must answer "is a host running on this data root?" before it
writes a command (`DirectoryHostControl`), and a new shell entry may not import the legacy tree
(`baseline_shell_legacy_imports.txt` only shrinks). Nothing here knows a bot, a command or a
venue: a lock is a file, and the probe tries it and gives it back at once.

@par Extension cases
  · another platform's lock call - one branch in `file_lock.py`; the probe and the writer do not change;
  · a probe that also names the holder (its pid) - a second method on `IInstanceProbe`.

Capability: Ask whether a host holds the data root's writer lock, without taking it
    Also: is the host running, single instance, lock file, probe, second process, instance lock
    Use: FileLockInstanceProbe
    User: src/shell/composition_root.py
    Status: stable
"""
