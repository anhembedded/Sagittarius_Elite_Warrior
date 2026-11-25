r"""`EPIC-047F` (condition 4) — a line that may carry a secret is not kept: the whole line goes, never a redaction.

@details A deny list of **key shapes**, not of words alone: an API key or secret (a long run of letters and digits, as the
exchange issues them), a signature, a listen key, a bearer token, a webhook URL, a PEM block, and an assignment to a name
that holds one (`apikey=…`, `secret: …`). When any shape matches, the line is dropped whole; a line is never edited, because
a redaction that misses a variant still leaks. A false positive costs one line in a view; a miss costs a key, so the list
leans to drop.

The shapes are ASCII: a key written with a zero-width character or a space inside it passes, which is acceptable for keys the
exchange issues and the bots never split. Every shape is linear in the text (no unbounded `\S*` before an alternation), and the
handler only scans a message of at most `MAX_MESSAGE_CHARS`.

Each shape has a name so a test can prove each alone (`test_bot_log_secret_filter.py`: remove one and exactly its sample
gets through).
"""

from __future__ import annotations

import re
from typing import Final

#: Name, then the shape. Case-insensitive unless the shape says otherwise.
SECRET_SHAPES: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "assignment",
        re.compile(
            r"(api[_ -]?key|api[_ -]?secret|secret|signature|listen[_ -]?key|password|passphrase|"
            r"token|authorization|x-mbx-apikey)\s*[=:]",
            re.IGNORECASE,
        ),
    ),
    ("bearer", re.compile(r"\bbearer\s+\S{6,}", re.IGNORECASE)),
    (
        "webhook-url",
        re.compile(
            r"https?://\S{0,200}(webhook|hooks\.slack\.com|api\.telegram\.org/bot|discord(app)?\.com/api)",
            re.IGNORECASE,
        ),
    ),
    ("long-token", re.compile(r"[A-Za-z0-9+/_=-]{32,}")),
    ("pem", re.compile(r"-----BEGIN")),
)


def shapes_matching(text: str) -> tuple[str, ...]:
    """The names of the shapes `text` has, in list order."""
    return tuple(name for name, shape in SECRET_SHAPES if shape.search(text))


def may_carry_a_secret(text: str) -> bool:
    return any(shape.search(text) for _name, shape in SECRET_SHAPES)
