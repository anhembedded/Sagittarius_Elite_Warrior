Status: Current

# 007 — A door with one key: how a desktop reaches a trading host without opening a port

**Teaches:** how to let a desktop application read and command a service on a server without a listening port, a shared password or a second copy of the rules — least privilege, a forced command, and a wire that refuses a mismatch. **Decision:** [`DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md`](../../Tasks/epics/EPIC-047_vps_bots_tab/DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md) and [`DECISION_2026-10-27_a_vps_bot_reaches_binance_only_through_the_vps.md`](../../Tasks/epics/EPIC-047_vps_bots_tab/DECISION_2026-10-27_a_vps_bot_reaches_binance_only_through_the_vps.md); the steps are [`headless_runbook.md`](../OPERATIONS/headless_runbook.md) §14. This page teaches; the records decide.

## 1. The problem
The owner's bots run on a VPS and the owner wants to see and control them from the desktop, with the Bots screen they already know. Until then the VPS was read through SSH text, plans reached it by `scp`, and the desktop and the VPS read different exchange accounts. The trading host holds real money, so the way in must be narrower than "a shell".

## 2. Constraints
- The host must listen on no new port: a public endpoint on a trading host is a bigger target than the thing it serves.
- No password, no secret in the app: the desktop keeps where a key is, never the key.
- The desktop must use the host's own rules, not copies of them: a command goes to the host's gate and its audit, and the host answers in its words.
- A desktop and a host of different builds must not talk: a mismatch on a wire that moves money is a bug waiting.
- The desktop must not reach the exchange in this tab, so its facts and the host's cannot differ.

## 3. Solutions considered
| Option | What it is | Why it lost or won |
| :--- | :--- | :--- |
| An HTTPS/REST API on the host | A server with its own auth | A new listening port, a new credential, a second implementation of the rules |
| SSH tunnel to a local port | `ssh -L` to an API | Still needs the API; the tunnel gives a general door |
| SSH shell and parse text | What was done by hand | No types, no versioning, a shell for the key |
| **SSH with a key restricted to one command** | `restrict,command="…/sew-bridge"` | **Chosen:** `sshd` is the listener that already exists; the key can run only the bridge |

## 4. The choice and why
The key in `sew`'s `authorized_keys` is *forced* to a command: whatever the client asks for, `sshd` runs the bridge, and `restrict` turns off forwarding and the terminal. The bridge speaks newline-delimited JSON on its standard input and output, reads the host's files read-only, and hands commands to the host's control directory, where the host's own gate judges them and its audit records them. Both ends carry the same wire (one reflective codec over about fifty records) and exchange digests of it at the start: a different build is refused in words, and never retried.

## 5. How it is implemented
`deploy/linux/sew-bridge` is the command; `src/shell/link_bridge_main.py` serves; `src/support/wire/` holds the codec, the bridge session and the desktop side (`LinkSupervisor`, which reconnects by itself); `src/shell/vps_tab/` stands the Bots screen on the link. A fact comes from a file the host writes (`state/host-facts.json`, `state/market-data.json`, `state/host-reads.json`), so the bridge needs no access to the running process.

## 6. Risks and failure modes
- A forced command runs through the account's login shell, so an account with the shell `nologin` never runs it: the desktop reads "This account is currently not available". The runbook gives the account a shell and keeps the key restricted.
- A cut during a command leaves its outcome unknown; the desktop asks the host's audit and never sends it again (page 006).
- `sshd` keeps the first value it reads for a setting, so a drop-in that turns password login off must sort before a cloud image's own (`01-…` before `50-cloud-init.conf`); `sshd -T` shows what is in effect.

## 7. Limits
One host at a time, one key per desktop. When there are several operators, the question becomes per-operator keys and an audit of who sent what, not a better bridge.

## 8. Names to know
*Forced command* (`command=` in `authorized_keys`), *least privilege*, *capability* (a key that can do one thing), *confused deputy*, *wire versioning by digest*, *snapshot then subscribe*, *idle watchdog / heartbeat*.

## 9. Interview questions
1. *How do you give a client access to one operation over SSH?* A key restricted with `restrict,command=…`: the server runs that command whatever the client asks; add no forwarding and no terminal.
2. *Why does a `nologin` account break it?* `sshd` runs the forced command through the account's shell with `-c`; `nologin` ignores it and prints a refusal.
3. *Why a digest of the wire instead of a version number?* A version string can stay the same while the wire changes; the digest changes with the wire.
4. *Why read files rather than ask the running process?* The bridge needs no access to the host's memory or its port; the host publishes what a reader may see.
5. *What is the trade-off of one first-value-wins setting in `sshd_config.d`?* An earlier file silently wins; verify with `sshd -T`, not by reading your file.

## 10. Read more
- `man sshd` (AUTHORIZED_KEYS FILE FORMAT: `command=`, `restrict`) and `man sshd_config` (`Include`, first value wins).
- Saltzer and Schroeder, *The Protection of Information in Computer Systems* (least privilege).
