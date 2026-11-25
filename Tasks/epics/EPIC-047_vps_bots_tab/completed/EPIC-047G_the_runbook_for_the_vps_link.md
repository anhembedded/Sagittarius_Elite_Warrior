# EPIC-047G — The runbook sets up the VPS link from a clean desktop: a key for `sew`, password login off, and what to do when it fails

**Status:** ✅ Done (2026-11-25) — the runbook is written; every owner run it lists is **pending**, not run
**Board:** The runbook for the VPS link is `headless_runbook.md` §14: one ordered checklist, the restricted `sew` key, password login off last, the typed errors, and 16 owner checks, none run; it found that `sew` has the `nologin` shell and home `/var/lib/sew`, which the plan's `/home/sew` missed.
**Source:** the owner's delegation of 2026-10-24; charter D6; De-risk §3.4 and §9 item 8: A1 was false (the owner had a password and no key until 2026-10-24), and the key was installed for root, not for `sew`.
**Risk:** 🟢 — documentation; a wrong step in `authorized_keys` or `sshd_config` can lock the owner out of the VPS, so the order of steps and the open session matter.
**Complexity:** S — one runbook section, one page of troubleshooting, one Learning page.
**Epic:** [EPIC-047](../README.md)
**Depends on:** [EPIC-047C](EPIC-047C_the_bridge_behind_a_forced_command.md) (the exact forced command and the bridge launcher), [EPIC-047D](EPIC-047D_the_desktop_transport_profiles_and_the_options_page.md) (the profile fields), [EPIC-047H](../incomplete/EPIC-047H_the_host_serves_market_data_and_refreshed_facts_to_the_bridge.md) (the host's market-data and refreshed-facts files, for the troubleshooting rows); the steps can be drafted earlier

---

## 1. Context and problem
`Docs/OPERATIONS/headless_runbook.md` covers the host. Nothing covers the desktop's link: the key, the account, the restriction, the profile. De-risk §3.4 holds the key setup that worked on the owner's Windows (`ssh-keygen -t ed25519`, installing the public half, the Windows `ssh-agent` service) and the hardening (`PasswordAuthentication no` in `/etc/ssh/sshd_config.d/50-sew-keys-only.conf`, `sshd -t` before the reload). §2.3 and §2.5 give the forced command and its checks.

## 2. Acceptance criteria
- [x] The runbook section starts with the key setup for the **`sew`** account, never root: generate an ed25519 key with a passphrase asked by `ssh-keygen`, install only the public half in `sew`'s `authorized_keys` with `restrict,command="…"` naming the bridge (the line from 047C), and load the key into the agent (Windows: the `ssh-agent` service and `ssh-add`; Pageant).
- [x] It then turns **`PasswordAuthentication no`** on: write the drop-in, run `sshd -t`, reload `ssh`, and keep the current session open until `ssh -o BatchMode=yes <login>@<vps> true` succeeds from the desktop with the key; the order is stated so a mistake cannot lock the owner out.
- [x] It tells the owner to log in once and accept the host key so `known_hosts` holds it, and what the app does with a wrong key (047D).
- [x] The three checks of De-risk R2 are in it as a verification the owner can run: the restricted key gets the bridge's `hello` for a shell request, "administratively prohibited" for a port forward, and a refusal for a terminal.
- [x] A troubleshooting table maps each error the app shows (refused key, unknown or changed host key, host unreachable, version difference, bridge not started, data age growing, market data or exchange facts older than the host's cadence, "not published by the host") to its cause and its fix; the version difference says `sudo sew-update`.
- [x] It names the facts file of 047B, the bridge's idle watchdog, and that `root`'s key stays the owner's administration key outside the app's profiles.
- [x] It records the open items: the untested Windows agent path until 047D's run, the Unix socket variant as not built.
- [x] A `Docs/LEARNING/` page explains the design (the doors, the bridge, the forced command, why no port), indexed in `Docs/LEARNING/README.md` (charter D6).
- [ ] **Not done:** A walk-through of the runbook on a clean desktop profile is recorded; the document guards pass. *Pending: a walk-through on a clean desktop is the owner's; the runbook's §14.6 holds the checks.*

## 3. Design
Documentation in the repository's register (`ONBOARDING.md` §10), in the existing runbook rather than a new copy of its host sections (P3). Commands are copied from De-risk §3.4 and the final 047C line (P2: verify, don't restate); **none was run on a real host** (§14.6 lists what the owner runs).

## 3a. Reuse
`Docs/OPERATIONS/headless_runbook.md` and `deploy/linux/sew-profile.sh` (`_sew_as_service`): `used` for the host-side conventions. No UI or application need otherwise.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Docs/OPERATIONS/headless_runbook.md` | the desktop-link section |
| `Docs/LEARNING/00x_….md` and `Docs/LEARNING/README.md` | the design page and its index row |
| `Docs/MODULES/…` | the wire protocol page, if 047A's notes call for one |

## 5. Testing
Documentation-only: the guards `python3 scripts/check_skill_prompt_references.py`, `tests/unit/test_task_board_is_consistent.py`, `tests/unit/architecture/test_claude_tree_is_wired.py` and any guard that reads `Docs/`. The walk-through is a manual check with its date. Not run.

## 6. Docs touched
Those listed in §4.

## Implementation notes (written when done)
- **Delivered:** `Docs/OPERATIONS/headless_runbook.md` §14 (the ordered checklist, the key for `sew`, the restricted line, `PasswordAuthentication no` last, the host-key pin, `sudo sew-update`, the profile, the error table, the files), `Docs/LEARNING/007_…`. The bash blocks parse (`test_every_bash_block_in_the_runbook_parses`); the commands are copied from De-risk §3.4 and 047C's owner step and **not run on a VPS**.
- **A finding the plan missed.** `sew-install` creates `sew` with home `/var/lib/sew` and the shell `/usr/sbin/nologin`. `sshd` runs a forced command through the account's login shell and reads `authorized_keys` from its home, so 047C's `/home/sew/.ssh` and a `nologin` shell would not start the bridge. §14.3 first gave `sew` `/bin/sh` with a root-owned `authorized_keys`; review round 1 showed the second claim false (`sew` owns `/var/lib/sew`, so it can replace `.ssh`), and the owner decided on 2026-11-25 ("chọn phương án B") that `sew` gets a dedicated guard login shell instead and never `/bin/sh`; §14.3 now uses `sew-link-key`, which ships in the next pull request. This is derived from `sshd(8)` and `sew-install`, not run: row 1 of §14.6 is the check. The coordinator should confirm it with the owner before the first run.
- **Follow-up delivered (`sew-link-key`, the owner's request of 2026-11-25).** `deploy/linux/sew-link-key` (`check`, `shell show|set|unset`, `add`, `list`, `remove`, `--dry-run`) and the guard login shell `deploy/linux/sew-bridge-shell` replace the hand-typed key line of §14.3; `sew-install`/`sew-update` link it. Tests: `tests/unit/scripts/test_sew_link_key_*.py`, `test_sew_bridge_shell.py` (119 tests; mutation checks on 26 mechanisms, each killed: `restrict` dropped, a private key accepted, a second key replacing the first, modes loosened, a line appended without a newline, the guard accepting any argument and others; one equivalent mutant noted: the multi-line test is killed by the message check, the regex also rejects it).
- **Seen on a real OpenSSH 9.6 in the author's container (a throwaway `sew` account, the script run unchanged, `UsePAM yes`), not on the owner's VPS:** a shell request, `whoami; cat /etc/passwd` and no command all got the bridge's `hello`; `-tt` got `PTY allocation request failed`; a forward with the restricted key got nothing; a key added by hand with no restriction got `sew: this account only runs the VPS bridge` for a command and, **without** the `Match User sew` drop-in, a working TCP forward (with it, none). With `UsePAM no`, `sshd` refused the account: `User ... not allowed because account is locked`. Both are in `check`.
- **Decision for the coordinator:** keys live in `/var/lib/sew/.ssh/authorized_keys` (`sew`'s own, as `StrictModes` needs); `AuthorizedKeysFile` outside `sew`'s home is not used.
- **Owner steps still pending, each a checkbox in §14.6:** 047C (rows 1 to 4, 6), 047D (rows 5, 7), 047E (rows 8 to 11), 047H (rows 12 to 16: A6, A10 and the weight and tick-age measurement, A2, A3, A9). Nothing in this task was run on a real machine; the walk-through on a clean desktop profile is not done.
