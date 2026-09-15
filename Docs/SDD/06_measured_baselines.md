# SDD §6 — The baselines Phase 0 committed

> Part of the SDD, split out of the single `README.md` this document used to be
> (2026-09-15, user decision). Every `###` heading below is **verbatim** from that
> file, so a reference written as *"SDD, 'Threading contract'"* still resolves.
> [`README.md`](README.md) is the index.

### Measured baselines committed in Phase 0

- `tools/measure_duplicate_members.py`: the "59 duplicated names" script, defined over
  `screens/*`, `modules/*/ui/**` and `shell/surfaces/**` together, so the Phase 1 criterion cannot
  be satisfied by moving files. Its Phase 0 output is recorded in the task file.
- `tests/unit/architecture/allowlist_module_boundaries.txt`: one entry per
  `(importing_module, imported_module)` pair, no line numbers — 10 entries as found (12 imported
  symbols across 10 import statements).
