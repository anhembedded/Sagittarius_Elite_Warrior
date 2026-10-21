"""`BUG-176`, `BOT-169`, `BOT-224` — the words of what the Trading page runs off the UI thread.

@details The kinds the page's `ActionOwnershipTracker` tells apart, the cause key
each one reports a failure under, and the hints and headline that go with them.
Held apart from the presenter so it stays under the file ceiling
(`architecture-rule.md` §5.4).
"""

#: `ActionOwnershipTracker`'s `TKind`: the four things this page runs off the UI thread.
ENROL = "enrol_key"
REMOVE = "remove_key"
CHECK = "check_connections"
PUBLIC_IP = "public_ip"

#: `BOT-169` — the causes of the page's commands, one message each.
ENROL_CAUSE = "trading.settings.add_key"
REMOVE_CAUSE = "trading.settings.remove_key"
CHECK_CAUSE = "trading.settings.check_connections"
PUBLIC_IP_CAUSE = "trading.settings.public_ip"
#: What each kind was doing and its cause, for a failure nobody expected.
UNEXPECTED = {
    ENROL: ("Adding the key", ENROL_CAUSE),
    REMOVE: ("Removing the key", REMOVE_CAUSE),
    CHECK: ("Checking the connection", CHECK_CAUSE),
    PUBLIC_IP: ("Looking up the public IP", PUBLIC_IP_CAUSE),
}

ADD_HINT = (
    "Enter the key and its secret. The app asks Binance which environment the "
    "key belongs to and keeps it for the venues it can trade."
)
REPLACE_HINT = "Enter the new key and secret for {venue}. It must be a key of {venue}."
UNEXPECTED_HEADLINE = (
    "{doing} failed unexpectedly. Nothing was changed that this page can tell; "
    "check the log, then try again."
)
