"""`EPIC-047D` — every way the desktop's link can fail, as a typed error that carries its sentence.

The transport raises these and nothing else (`ILinkTransport`): the tab shows `words` as they
are, a retry policy asks `retriable`, and a test asserts the type. Nothing is parsed from text
(SSH record D1). A sentence names the host and says what to do; it never carries a secret, a key
or the text of a library's exception.
"""

from __future__ import annotations


class LinkError(Exception):
    """The link is not up, or was lost. `words` is the sentence the person reads."""

    #: Whether trying again can change the outcome. A refused key or a wrong host key will be
    #: refused again, and hammering `sshd` with them is how a host bans its owner.
    retriable = False

    def __init__(self, words: str) -> None:
        super().__init__(words)
        self.words = words


class KeyRefusedError(LinkError):
    def __init__(self, host: str, user: str) -> None:
        super().__init__(
            f"{host} refused the key for {user}: check that its public key is in {user}'s "
            "authorized_keys on the host, or load the key into your SSH agent"
        )


class KeyFileUnusableError(LinkError):
    def __init__(self, path: str, reason: str) -> None:
        super().__init__(
            f"the key file {path} cannot be used ({reason}): the app never asks for a "
            "passphrase, so load an encrypted key into your SSH agent and choose the agent"
        )


class UnknownHostKeyError(LinkError):
    def __init__(self, host: str, port: int, known_hosts: str) -> None:
        super().__init__(
            f"{host} is not in {known_hosts}, so its identity cannot be checked: log in once "
            f"with `ssh -p {port} <user>@{host}` and accept its key, then connect again"
        )


class WrongHostKeyError(LinkError):
    def __init__(self, host: str, known_hosts: str) -> None:
        super().__init__(
            f"{host} presented a host key that is not the one pinned in {known_hosts}: "
            "refused. If the host was reinstalled, remove its old line from that file and log "
            "in once to pin the new key; otherwise someone may be in the way"
        )


class HostUnreachableError(LinkError):
    retriable = True

    def __init__(self, host: str, port: int, reason: str) -> None:
        super().__init__(f"cannot reach {host} on port {port}: {reason}")


class VersionDifferenceError(LinkError):
    def __init__(self, words: str) -> None:
        super().__init__(words)


class BridgeRefusedError(LinkError):
    """The bridge ended the session for a reason of its own (a protocol violation, an internal failure)."""

    def __init__(self, reason: str, words: str) -> None:
        super().__init__(f"the host's bridge ended the session ({reason}): {words}")
        self.reason = reason


class LinkLostError(LinkError):
    retriable = True

    def __init__(self, reason: str) -> None:
        super().__init__(f"the link to the host was lost: {reason}")
        self.reason = reason


class CommandInFlightLostError(LinkLostError):
    """The link was cut after a command was sent and before its answer came.

    The host may have run it or not. The desktop never sends it again by itself; whoever sent it
    asks again with the **same** request id once the link is back, and the host answers from its
    audit and runs it once (`ICommandDoor.send`)."""

    def __init__(self, request_id: str) -> None:
        super().__init__(
            f"the command {request_id} was in flight and its outcome is unknown: it will not "
            "be sent again by itself"
        )
        self.request_id = request_id


class TransportMissingError(LinkError):
    def __init__(self, protocol: str) -> None:
        super().__init__(
            f"this build has no transport for the protocol {protocol!r}: choose another "
            "protocol in the profile"
        )


class CallFailedError(Exception):
    """The bridge answered a call with an `error`: the link is fine, the request was not served."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class CallTimedOutError(Exception):
    """A call got no answer in time. The link may be fine and the answer may still come; a command
    whose answer is unknown is asked again with its same request id."""

    def __init__(self, method: str, timeout_s: float) -> None:
        super().__init__(f"{method} was not answered within {timeout_s:g} s")
        self.method = method
