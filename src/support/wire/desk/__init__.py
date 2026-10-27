"""`EPIC-047D` — the desktop's side of the remote link: a transport behind a seam, the protocol, a supervisor.

The bridge (`support/wire/bridge/`) runs on the host; this package runs on the desktop. `DeskProtocol`
speaks the bridge's conversation (hello, welcome, calls, events, pings), `DeskLink` runs it over an
`ILinkTransport` on a reader thread, `LinkSupervisor` keeps one profile's link up and reconnects it,
and `AsyncSshTransport` (`asyncssh_transport.py`, which arrives with the `asyncssh` dependency the
owner approves) is the one transport, on `asyncssh`, with its event loop on a thread of its own and
no blocking call inside it. A technical package: no module, no Qt, no host.

@par What it never does
It stores no password, passphrase or key (`core/contracts/link_profile.py`), never passes
`client_keys=None` or `known_hosts=None` to `asyncssh` (`ssh_connect_options.py`), and never sends a
command twice by itself (`desk_link.py`).

@par Extension cases
  · another way to reach the bridge (a Unix socket, a VPN, a TLS endpoint) - one `ILinkTransport`,
    one `LinkProtocol` member, one `register` line in `default_transports.py`;
  · another thing to do on every new connection - the observer's `on_link_up`;
  · a new retry rule - `ReconnectPolicy`, read by the supervisor only;
  · a new typed failure - one `LinkError` subclass with its sentence in `contracts/link_errors.py`.

Capability: Reach the host's bridge from the desktop over a transport behind a seam, with a heartbeat, typed errors and automatic reconnect
    Also: ssh client, asyncssh, remote link desktop side, connect to vps, reconnect after cut, heartbeat ping, half-open link, link supervisor, transport port, known_hosts pin, connection profile
    Use: LinkSupervisor, TransportRegistry
    User: src/presentation/ui/remembered_state_wiring.py
    Status: stable
"""
