"""`Place` became `(str, Enum)` so its members satisfy `place: str` on the
Engine's own harvested contribution mechanism (`TASK-043` E1) without that
engine ever importing this closed, app-specific `Enum`. These lock the
runtime fact the fix exists to add, and that nothing else about `Place`
moved: member identity, equality-to-itself, hashing and string rendering
are exactly what they were as a bare `Enum`.
"""

from Sagittarius_Elite_Warrior.src.core.contracts.place import Place


def test_a_place_member_is_now_a_str_instance():
    assert isinstance(Place.SCREEN, str)


def test_a_place_member_equals_its_own_value_as_a_bare_string():
    assert Place.RAIL == "rail"


def test_a_place_member_does_not_equal_an_unrelated_string():
    assert Place.RAIL != "console"


def test_str_rendering_is_unchanged_by_the_str_mixin():
    """`(str, Enum)` does not adopt `StrEnum`'s different `__str__` on this
    interpreter — verified here as a locked fact, not left as a docstring
    claim (`architecture-rule.md` §7.3). If this ever prints `"rail"`
    instead, every existing log line and f-string using a `Place` silently
    changed shape."""
    assert str(Place.CONSOLE) == "Place.CONSOLE"


def test_members_are_still_distinguishable_by_identity_and_hash():
    assert Place.HEADER is Place.HEADER
    assert Place.HEADER is not Place.CONTEXT_BAR
    assert len({Place.HEADER, Place.CONTEXT_BAR, Place.HEADER}) == 2
