"""`BOT-144` — the Dev Board's per-card widgets, split out of
`dev_board_panel.py` once that file crossed `architecture-rule.md` §5.4's
400-line ceiling. Each card is a `Panel` subclass owning its own widgets and
wiring (`layout_helpers.py` holds the handful of layout primitives every
card shares); `dev_board_panel.py` constructs them and re-exposes whatever
private attribute the existing tests/View key off, per that file's own
class docstring.
"""
