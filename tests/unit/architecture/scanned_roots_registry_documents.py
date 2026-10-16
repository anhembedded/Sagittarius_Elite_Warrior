"""The registry rows of the guards that keep a document tree under `Docs/` true.

Split from `scanned_roots_registry.py` when that file reached the 400-line
ceiling again (`EPIC-041K`); the registry spreads `DOCUMENT_GUARDS` into
`GUARDS`, so nothing that reads the registry changes. Same shape, same rules:
register the directories a guard *scans*.
"""

from __future__ import annotations

DOCUMENT_GUARDS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    # `CS-001`'s own index guard. `Docs/` rather than `src/`, and registered
    # for the same reason as the rest: a case-study directory that moved would
    # otherwise leave every check in that file passing over an empty scan.
    (
        "tests/unit/architecture/test_case_study_index_is_consistent.py",
        (("Docs/CASE_STUDIES", "*.md"),),
    ),
    (
        "tests/unit/architecture/test_spec_index_is_consistent.py",
        (("Docs/SPEC", "SPEC-*.md"),),
    ),
    # `EPIC-041K` — a module's design cites code by symbol, never by line; the
    # symbols are looked up in the three source trees it may cite.
    (
        "tests/unit/architecture/test_module_docs_cite_code_by_symbol.py",
        (
            ("Docs/MODULES", "*"),
            ("src", "*.py"),
            ("scripts", "*.py"),
            ("tests", "*.py"),
        ),
    ),
)
