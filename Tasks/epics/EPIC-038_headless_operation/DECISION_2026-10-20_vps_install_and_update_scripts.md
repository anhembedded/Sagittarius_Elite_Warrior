# ADR — A VPS is installed and upgraded by two root scripts; the daily variables live in `/etc/profile.d`

**Epic:** [EPIC-038](README.md)
**Date:** 2026-10-20
**Status:** Accepted
**Decided by:** 🤖 Agent decision, delegated by the owner (ONBOARDING §7) after his request of 2026-10-20, relayed by the coordinating session: *"a VPS install script: clone this repo, run the script, and the VPS is set up; also put the commonly used variables into bashrc"*, and his acceptance of the coordinator's design (an install script, an update script, a profile in `/etc/profile.d` instead of `~/.bashrc`). The choices below inside that design are the author's; the owner may veto any of them.
**Supersedes / superseded by (optional):** extends [`DECISION_2026-10-20_server_keys_by_root_script.md`](DECISION_2026-10-20_server_keys_by_root_script.md) (the same root-script pattern) and [`DECISION_2026-10-20_a_missing_credential_file_is_a_secret_not_set.md`](DECISION_2026-10-20_a_missing_credential_file_is_a_secret_not_set.md) (the order of an upgrade); changes nothing in either.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree at the commit §1 names |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |

## 1. Context
Read at `7082619`. ✅ Runbook §2 is twelve `sudo` commands and §8 is six steps whose order matters since BOT-203: the new unit with the old code finds no key (`headless_runbook.md` §3, "Upgrading an existing install"). ✅ §8b asks the reader to paste a 40-line `sew-backup` script and two unit files into `/usr/local/sbin` and `/etc/systemd/system`. ✅ Every command to the host is `sudo -u sew env PYTHONPATH=… SEW_DATA_ROOT=… …/main.py`, held in a `$M` variable the reader defines in each shell, and `BOT-198` found `COLUMNS` lost through that `sudo -u sew env` hop. ✅ `src/config/user_config.json` is tracked by git and edited by hand on the server (`bots.account_loss_cap`, runbook §6). ✅ The runbook's `systemctl cat sew-run | grep LoadCredential` also prints the unit's comment line that contains the word (`deploy/linux/sew-run.service`, the "Secrets:" comment), so "prints exactly" was never literally true.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **Two scripts in `deploy/linux/`, `sew-install` and `sew-update`, share one library, `sew-lib.sh`.** The library holds what both do (the unit, the backup units, the shell profile, the links, the pip / engine / compileall triple, the credentials-line check), so the order BOT-203 needs is written once. `sew-key` is untouched. | Accepted | 🤖 Agent decision, delegated by the owner | One place to change the upgrade order; a sourced file, so it is read whole before a checkout can rewrite it. |
| D2 | **`sew-install` works from any clone.** `/opt/sew/Sagittarius_Elite_Warrior` is the checkout the service runs; when the script runs from another clone it clones the repository there (`--repo-url`, default the project's GitHub) and checks `--ref` out if given. | Accepted | 🤖 Agent decision, delegated by the owner | "Clone this repo, run the script" works without first creating `/opt/sew`; the first clone is only a way in. |
| D3 | **`/etc/sew/credentials` is `0700 root`**, not the runbook's `0750 root:sew`. | Accepted | 🤖 Agent decision, delegated by the owner | Only PID 1 reads it (`LoadCredential=`); `sew` never needed it. `/etc/sew` stays `0750 root:sew` for `sew.env`. A re-run tightens an existing `0750`; the runbook's manual line follows. |
| D4 | **`sew-install` enables the service and does not start it** unless `--start`. | Accepted | 🤖 Agent decision, delegated by the owner | A fresh host has no key: the start would end in exit 5, which the unit never restarts. It prints the command and the reason. |
| D5 | **`sew-install` installs `git` and the Python venv package with `apt` when missing, and nothing else**; no Python 3.12 or 3.13 is a refusal (exit 2), not a PPA. | Accepted | 🤖 Agent decision, delegated by the owner | "The VPS is set up" without a pre-step; Python itself stays the operator's choice. These are operating-system packages, not a project dependency. |
| D6 | **Host checks are all-or-nothing and listed together**: Ubuntu, systemd 251 or newer, free space, clock synchronised; `--skip-preflight` skips them, never the rest. | Accepted | 🤖 Agent decision, delegated by the owner | The 2 GiB figure is a guess for the venv and checkout (the app's own pre-flight warns at 1 GiB); a flag exists for the host that is right in a way the check cannot see. |
| D7 | **`sew-install` never changes the code of a running host**: it skips the Python stack and refuses `--ref`, pointing at `sew-update`. | Accepted | 🤖 Agent decision, delegated by the owner | A re-run on a live host is safe: links, profile, units; no pip under a running process. |
| D8 | **`sew-update` fetches, resolves the ref and checks for a conflicting hand edit *before* it stops the host.** A bare branch name means `origin/<branch>`. | Accepted | 🤖 Agent decision, delegated by the owner | A deviation from the runbook's literal order (stop, then fetch) that costs nothing: a network failure or a refusal leaves the host running. `user_config.json` edited by hand survives unless the release changes the same file; then it refuses (exit 2) and stops nothing. |
| D9 | **`sew-update` starts the host only if it was running before**, and **never resumes a bot** (decision O2). `--no-start` keeps it stopped. | Accepted | 🤖 Agent decision, delegated by the owner | An update never turns a stopped host on; the bots return RECOVERING and the message says how to resume. |
| D10 | **The credentials-line check is anchored** (`^LoadCredential=`) and exact, in the scripts and in the runbook's manual commands. | Accepted | 🤖 Agent decision, delegated by the owner | The unit's comment no longer counts as a second line; a drop-in that adds or empties a line exits 2 and the host stays stopped. `test_headless_runbook.py` pins the new command text. |
| D11 | **The profile is `/etc/profile.d/sew.sh`, copied from `deploy/linux/sew-profile.sh`**, POSIX sh, overwritten by both scripts. It defines the function `M` and `sewlog`, `sewstatus`, `sewbots`, `sewproblems`, `sewhelp`, and exports `SEW_HOME`, `SEW_CHECKOUT`, `SEW_DATA` only. | Accepted | 🤖 Agent decision, delegated by the owner | Not `~/.bashrc` (per account, not read by login `sudo -i`, edited by hand); not a global `PYTHONPATH`, which would reach every Python tool on the host. `M` passes `COLUMNS`, `TERM`, `NO_COLOR` and `COLORTERM` through `sudo -u sew env` by hand (`BOT-198`). A non-login `sudo -s` shell does not read `profile.d`; `. /etc/profile.d/sew.sh` does. |
| D12 | **`sew-backup` and its two units become files in `deploy/linux/`**; the scripts link it and install the units; `sew-install` enables the timer, `sew-update` only when the timer is new to the host. A hand-pasted `/usr/local/sbin/sew-backup` is moved aside, not deleted. | Accepted | 🤖 Agent decision, delegated by the owner | The runbook's heredoc was untested text; the file is tested (`test_sew_backup.py`). |
| D13 | **Secrets are written only by `install -m`** and every script runs under `umask 022`; none of the three reads a key, and none writes a credential file, `sew.env` (except to create it empty) or `user_config.json`. | Accepted | 🤖 Agent decision, delegated by the owner | A pip install under root's `077` would leave a venv `sew` cannot read; secrets keep their explicit modes. |
| D14 | **The script that started finishes** (no re-exec into the new release), inside `main()` followed by `exit`. | Accepted | 🤖 Agent decision, delegated by the owner | Simplest, and the file a checkout rewrites is never read again. A release that changes the upgrade steps is applied by the run after it; a rollback to a release without the scripts still works. |

## 2a. Constitution check
Not a default decision (the owner approved the design); recorded anyway because the scripts act as root on a trading host.

| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | the order (stop, copy, code, then unit, then check, then start), the refusals and the idempotence are code, pinned by `test_sew_update.py` and `test_sew_install.py` with the order read from a log |
| P2 Verify, don't restate | ✅ | the host facts are read (`/etc/os-release`, `systemctl --version`, `timedatectl`, `df`), the ref is resolved to a sha and printed, the unit's line is read back from `systemctl cat` |
| P3 A copy drifts | ✅ | the backup script and units are one file each, no longer a heredoc beside a file; the profile installed equals the repository's (`cmp`) |
| P4 Green proves only what was tested | ✅ | the real systemd, `useradd`, `chown`, pip and apt are named as not proven in the task and the runbook §12 |
| P5 Apply before you invent | ✅ | the runbook's own commands, `install -d`/`ln -sfn`/`cmp`, `git fetch` + `checkout --detach`, `/etc/profile.d`, the `sew-key` override pattern |
| P6 Fix the mechanism | ✅ | the order lives in one script instead of in a reader's memory of §3 and §8 |
| P7 Seam now, variant later | ✅ | the library is the seam for another distribution's variant; Ubuntu only now |
| P8 Ratchets only fall | ✅ | `test_headless_runbook.py` keeps its assertion with the stricter command text; no test is weakened |
| P9 Decide alone | ✅ | decided inside the owner's approved design and recorded here |
| P10 Pyramid and units | ✅ | unit tier, scripts run under bash; no new test needs a network |
| P11 Prompt-grade artifacts | ✅ | every message names the cause, the state of the host and the next command |
| Reversible; no real money, dependency, setting, Engine, user data or secret | ✅ | files in `deploy/linux/`, tests, docs; no project dependency changes (apt packages are the host's); the scripts never touch a key or `user_config.json`; reverting is deleting the files, a host keeps what it was given |

## 3. Alternatives considered
- **`sew-install` as a Python script run from the venv.** Loses to bash: it must run before a venv, a Python 3.12 or any dependency exists, and `sew-key` already set the shell-script precedent.
- **Variables in `~/.bashrc`** (the owner's first wording). Loses: per account, not read when an operator switches with `sudo -i`, and a file a person edits by hand cannot be overwritten safely. `/etc/profile.d` reaches every login shell and is ours.
- **`ExecStartPre=` doing the compile or the checks.** Rejected in runbook §2 already: outside the sandbox, on every restart.
- **A re-exec of the new release's `sew-update` after the checkout.** Loses for now: it adds a stage that a rollback to an older release cannot use, to cover a case (a release that changes the upgrade steps) the next run covers.
- **Start the service at the end of `sew-install` by default.** Loses: no key, so exit 5 and a unit that does not restart (D4).

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Does the 2 GiB free-space floor suit the VPS plans the owner uses? | nothing (`--skip-preflight`, `SEW_DEPLOY_MIN_FREE_MB` in tests) | 2026-10-20 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1–D14 | [BOT-204](../../completed/BOT-204_vps_install_and_update_scripts_with_shell_helpers.md) | Verified under bash with stand-ins; not run under a real systemd | `tests/unit/scripts/test_sew_install.py`, `test_sew_update.py`, `test_sew_profile.py`, `test_sew_backup.py` |
