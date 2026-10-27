"""`EPIC-047D` — the words of Tools → Options → VPS link."""

from __future__ import annotations

from typing import Final

TITLE: Final = "VPS Link"
LIST_LABEL: Final = "&Connections"
ADD_TEXT: Final = "&Add"
REMOVE_TEXT: Final = "&Remove"
NEW_NAME: Final = "New connection"
EMPTY_HINT: Final = "No connection yet. Add one to reach the bots on a VPS."
NO_PROFILE_TEXT: Final = "Add a connection to edit it."

NAME_LABEL: Final = "&Name:"
HOST_LABEL: Final = "&Host:"
PORT_LABEL: Final = "&Port:"
USER_LABEL: Final = "&User:"
PROTOCOL_LABEL: Final = "P&rotocol:"
KNOWN_HOSTS_LABEL: Final = "Known &hosts file:"
KNOWN_HOSTS_HINT: Final = "Default: ~/.ssh/known_hosts"
TIMEOUT_LABEL: Final = "Connect &timeout (s):"
ATTEMPTS_LABEL: Final = "Reconnect &attempts:"
ATTEMPTS_ANY: Final = "Keep trying"
FIRST_DELAY_LABEL: Final = "&First retry after (s):"
MAX_DELAY_LABEL: Final = "&Longest wait (s):"
IN_USE_TEXT: Final = "&Use this connection for the VPS Bots tab"

KEY_GROUP: Final = "Key"
AGENT_TEXT: Final = "The SSH a&gent (Pageant, the OpenSSH agent)"
KEY_FILE_TEXT: Final = "A key &file:"
BROWSE_TEXT: Final = "&Browse…"
BROWSE_TITLE: Final = "Choose the private key file"
KEY_NOTE: Final = (
    "The app never stores a password, a passphrase or a key; "
    "it keeps only where the key file is."
)

PROTOCOL_TEXT: Final = {"ssh": "SSH"}
