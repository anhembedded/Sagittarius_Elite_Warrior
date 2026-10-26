"""The remote link's wire form: one reflective codec for the contract types, a closed list of the
types it may carry, and (with the handshake) the rule that a different build is refused in words.

`EPIC-047A`, `DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md` D5 and
D6. A technical package with no host and no network in it: it turns a contract value into JSON
and back, and says in words when it cannot. It imports the standard library and `core/contracts`
(the `@wire_name` mark, the `WireRoot` entry), never a module; each module declares its own
roots and `shell/wire_roots.py` is where they meet. The hand-written file codecs
(`bot_record_codec.py`, `host_command_codec.py`) stay: a stored file must read across versions,
the link is same-build.

@par Extension cases
  · a type the link must carry - one `WireRoot` in its module's list and one contract test
    under `tests/unit/support/wire/contract/`; a union member also takes `@wire_name`;
  · a new scalar (a `UUID`) - one case in `wire_shape.py` and one pair in `wire_codec.py`;
  · a changed wire form - the root's name ends `/2`, which the handshake reports as a difference.

Capability: Carry a contract value over the remote link as JSON and back equal, from its type hints (money exact, enums typed)
    Also: wire form, serialise, serialize, to json, from json, codec, round trip, schema from type hints, dataclass to dict, remote link, bridge message, wire name, tagged union
    Use: WireRoots
    User: src/shell/wire_roots.py
    Status: stable
"""
