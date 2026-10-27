"""The remote link's bridge: what runs on the host so a desktop can read and command its bots (`EPIC-047C`).

`DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md` D2 and D3. The bridge is
a second process that `sshd` starts for each session behind a forced-command key. It speaks
newline-delimited JSON on standard input and output (`bridge_session.py` has the whole protocol),
reads the bots' files and the host-facts file through two ports, and sends a command through a third
(the host's control door). It opens no socket, loads no key and calls no exchange. A technical
package: the ports are in `contracts/`, `bots` and `operations` implement them in their `link.py`,
and `shell/link_bridge_main.py` is where they meet.

@par Extension cases
  · a new thing the desktop may read - one method in `BridgeSession._answer`, one port if it is a
    new source, one wire root;
  · a new thing the bridge pushes - one `_event` kind and the desktop's handler for it;
  · a transport other than the standard streams (a Unix socket, `EPIC-047` O1) - `serve` takes the
    two streams; a socket would hand it its two file objects and add a listener elsewhere;
  · a protocol change - the roots' names end `/2` or `PROTOCOL` does, and the handshake refuses
    the old build in words.

Capability: Serve a host's bots to a remote desktop over standard input and output, read-only, with commands through the host's own door
    Also: bridge, forced command, ssh bridge, stdio protocol, newline-delimited json, remote link host side, idle watchdog, heartbeat, snapshot and events, request id, replay
    Use: BridgeSession, serve
    User: src/shell/link_bridge_main.py
    Status: stable
"""
