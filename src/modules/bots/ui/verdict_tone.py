"""`EPIC-043E` — the meaning a verdict's severity is read in, on every screen that shows one.

A check the guard refused is a loss tone, one it warned about a caution tone, one that passed no
tone at all. The words ("Blocks Start:", "Advice:", the check's title) always stand beside the
colour (`ui-presentation-rule.md` §1); this is only the colour, asked of the meaning table.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import VerdictSeverity
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone

_TONES: Mapping[VerdictSeverity, Tone] = MappingProxyType(
    {
        VerdictSeverity.REFUSED: Tone.NEGATIVE,
        VerdictSeverity.WARNING: Tone.CAUTION,
        VerdictSeverity.OK: Tone.NEUTRAL,
    }
)


def verdict_tone(severity: VerdictSeverity) -> Tone:
    """The tone a check of `severity` is painted in."""
    return _TONES[severity]
