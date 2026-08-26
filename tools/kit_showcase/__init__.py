"""
@brief A runnable gallery of every type `presentation.ui.kit` exports.

@details
Replaces `kit.gallery_coverage_guard`, whose referent is the QML kit and
which loses its subject as consumers move off QML (`EPIC-006`). Two jobs,
the same two the QML gallery had:

- **Look at it.** `python -m Sagittarius_Elite_Warrior.tools.kit_showcase` opens a window with one
  section per widget, so a change to a `StyleRole` can be seen rather than
  reasoned about.
- **Prove nothing was forgotten.** `showcased_types()` is what the coverage
  guard reads: a type exported from `kit.__all__` but absent here fails
  a test. That is the half `guards.py` records as missing — *"No
  coverage-guard counterpart yet ... no QtWidgets showcase/preview exists
  yet to check against."* This is that showcase.

Kept out of `sagittarius_engine/` on purpose: it is a development tool, and
the package it exercises must not gain a dependency on its own gallery.
"""

from __future__ import annotations

from .showcase import ShowcaseWindow, main, showcased_types

__all__ = ["ShowcaseWindow", "main", "showcased_types"]
