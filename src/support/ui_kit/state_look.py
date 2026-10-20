"""`EPIC-043C` — how a state looks: an icon and a tone, beside its word.

A bot's lifecycle state and a connection's state are told in a word first (`Running`,
`Not connected`). The look adds to the word and never replaces it: an icon from the Lucide set
(`assets/icons`) whose shape says the same thing, in the colour of the tone the meaning table
gives it. A module owns its table of looks (the states are its own); this is only the pair.

Extension cases: a look with two tones (a state that is bad only while it lasts) is one more
field here; a state with no icon is `None`, never a made-up one.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone


@dataclass(frozen=True, slots=True)
class StateLook:
    """The icon (a file stem in `assets/icons`) and the tone that go beside a state's word."""

    icon: str
    tone: Tone
