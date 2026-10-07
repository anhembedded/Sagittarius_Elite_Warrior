"""`BUG-176` — what adding, replacing or removing a key did, in plain words.

@details The headline of a refusal is a sentence that says what happened to the
key and what to do (`ui-presentation-rule.md` §10); the technical text, the standing
of each environment, goes behind Details…. A key that works nowhere is explained
once per environment asked, because the three answers are different advice: the
key is for another environment (`-2008`: a testnet key does not work on mainnet nor
the reverse), or Binance knows it and refused the request (`-2015`: an IP off the
key's allowlist — a LAN address such as 192.168.x.x never matches, only the public
one — or a missing permission), or Binance could not be asked.
"""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_enrolment import (
    EnrolmentRefusal,
    KeyEnrolment,
    KeyRemoval,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
    KeyEnvironment,
    KeyStanding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.connection_state_words import (
    failure_words,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_PAIR = 2


def venues_in_words(venues: Sequence[TradingVenue]) -> str:
    titles = [venue.display_name for venue in venues]
    return " and ".join(titles) if len(titles) <= _PAIR else ", ".join(titles)


def kept_message(enrolment: KeyEnrolment) -> str:
    return f"Key kept for {venues_in_words(enrolment.stored)}."


def _environment_line(verdict: EnvironmentVerdict) -> str:
    title = verdict.environment.label
    if verdict.standing is KeyStanding.UNKNOWN:
        hint = (
            " A testnet key does not work on mainnet, nor a mainnet key on a "
            "testnet: check that the key and secret come from the right Binance site."
            if verdict.environment is KeyEnvironment.MAINNET
            else " It was not made for this environment."
        )
        return f"{title}: Binance does not know this key.{hint}"
    if verdict.standing is KeyStanding.REFUSED:
        return (
            f"{title}: Binance knows this key but refused the request. If the key is "
            "restricted to trusted IP addresses, add this computer's public IP "
            "address (a LAN address such as 192.168.x.x never matches), and check "
            "that the key has the permissions it needs."
        )
    if verdict.failure is not None:
        return f"{title}: {failure_words(verdict.failure)}"
    return f"{title}: Binance could not be asked."


_SIMPLE = {
    EnrolmentRefusal.INCOMPLETE: "Enter both the key and the secret.",
    EnrolmentRefusal.NOT_A_KEY: (
        "That does not look like a Binance key: it has characters a key never "
        "has (a key and secret are plain letters and digits). Copy them again "
        "from Binance, without anything around them."
    ),
    EnrolmentRefusal.WITHDRAWAL_ENABLED: (
        "The key was not saved: it can withdraw funds. Create a key with "
        "withdrawals turned off in Binance's API management and add that one."
    ),
    EnrolmentRefusal.NO_TRADING_PERMISSION: (
        "The key was not saved: it may trade neither Spot nor Futures. Turn on "
        "Spot trading or Futures in the key's permissions on Binance, then add "
        "it again."
    ),
    EnrolmentRefusal.KEYRING_UNAVAILABLE: (
        "The key is valid but was not saved: the operating system's keyring "
        "cannot store it here. Set the venue's BINANCE_..._API_KEY and "
        "BINANCE_..._API_SECRET environment variables instead."
    ),
    EnrolmentRefusal.FILE_NOT_WRITABLE: (
        "The key is valid but secrets.local.json could not be written. Check "
        "that the file is writable, then add the key again."
    ),
}


def refusal_headline(enrolment: KeyEnrolment, target: TradingVenue | None) -> str:
    """The sentence a refused key is told with. `target` is the venue Replace was
    pressed on, `None` for Add key."""
    refusal = enrolment.refusal
    if refusal is None:
        raise ValueError("the key was not refused")
    if refusal is EnrolmentRefusal.NOT_ACCEPTED:
        lines = "\n".join(_environment_line(v) for v in enrolment.verdicts)
        return f"The key was not saved: Binance does not accept it.\n{lines}"
    if refusal is EnrolmentRefusal.OTHER_VENUE and target is not None:
        return (
            f"The key was not saved: it belongs to {venues_in_words(enrolment.venues)}, "
            f"not {target.display_name}. Use Add key… to keep it there."
        )
    if refusal is EnrolmentRefusal.FROM_ENVIRONMENT:
        return (
            f"The key was not saved: {venues_in_words(enrolment.venues)} takes its "
            "key from an environment variable, which this page cannot change. "
            "Remove the variable and add the key again."
        )
    return _SIMPLE[refusal]


def refusal_detail(enrolment: KeyEnrolment) -> str:
    """The standing of each environment asked, for Details…."""
    return "\n".join(
        f"{v.environment.value}: {v.standing.value}"
        + (f" ({v.failure.value})" if v.failure is not None else "")
        for v in enrolment.verdicts
    )


_REMOVAL = {
    KeyRemoval.FROM_ENVIRONMENT: (
        "The key comes from an environment variable, which this page cannot "
        "remove. Unset the variable instead."
    ),
    KeyRemoval.KEYRING_UNAVAILABLE: (
        "The key was not removed: the operating system's keyring cannot be used here."
    ),
    KeyRemoval.FILE_NOT_WRITABLE: (
        "The key was not removed: secrets.local.json could not be written. Check "
        "that the file is writable and try again."
    ),
}


def removal_failure_headline(removal: KeyRemoval) -> str:
    return _REMOVAL[removal]
