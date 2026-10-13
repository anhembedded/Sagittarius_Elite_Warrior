"""`EPIC-038E` — what may name a secret file, and how a file's text becomes a secret.

@details Both file-backed stores (systemd credentials and the permission-checked
file) keep one file per secret, named by the secret's name, in one directory. A
name is a plain file name: it cannot climb out of the directory, so the secret
name `../../etc/passwd` is "not stored" and never a path. A colon is refused too: on
Windows `C:key` is drive-relative and `key:stream` names an alternate data stream.

The text is read the way `systemd` documents a credential: UTF-8, with one trailing
newline dropped (`\n` or the `\r\n` an editor on Windows writes) and a leading
byte-order mark dropped (Notepad writes one, and it would otherwise become the first
character of the key). A value of nothing but whitespace is no secret at all.

Nothing here logs: the value is the thing that must never leave the caller.
"""

from __future__ import annotations

from pathlib import Path

#: A secret is a few dozen characters; a file larger than this is not one.
MAX_SECRET_BYTES = 8192


def file_in(directory: Path, name: str) -> Path | None:
    """`directory/name`, or `None` when `name` is not a plain file name."""
    if not name or name in {".", ".."} or any(c in name for c in "/\\:\x00"):
        return None
    return directory / name


def secret_from_bytes(raw: bytes) -> str | None:
    """The secret in a file's bytes, or `None` when they hold none.

    @raise UnicodeDecodeError The bytes are not text. The caller must not put the
    exception in a message: it can quote the bytes.
    """
    text = raw.decode("utf-8-sig")  # Notepad saves a byte-order mark; it is not the key
    if text.endswith("\r\n"):
        text = text[:-2]
    elif text.endswith("\n"):
        text = text[:-1]
    return text if text.strip() else None
