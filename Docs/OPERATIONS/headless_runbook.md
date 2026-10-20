Status: Current

# Headless runbook: install, run, stop, upgrade and diagnose on a server

`EPIC-038H`. For a person who has a fresh Linux VPS (systemd) or a Windows server and wants the app to run the bots there with no window, as a service. Journey: [`SPEC-015`](../SPEC/SPEC-015_run_the_bots_headless.md) · exit codes: [`exit_codes.md`](exit_codes.md) · logs and the health line: [`LOGGING.md`](LOGGING.md).

## 0. Read this first: what is not supported yet

**This host is not supported for unattended money.** A bot that halts, errs, whose stop gives up, hits its stop loss or take profit, or leaves its range, and every order that fills whole (a silent message, with the cycle's profit on the fill that closes a cycle; `BOT-189`), reaches your Discord channel once you store a webhook (§3, [`EPIC-036G`](../../Tasks/epics/EPIC-036_alerting_module/completed/EPIC-036G_walking_skeleton_halt_to_discord.md)). Until this has merged, the rest reaches nobody. A host that dies or powers off reaches you only once you store a check-in URL for the dead man's switch (§3b, [`EPIC-036E1`](../../Tasks/epics/EPIC-036_alerting_module/completed/EPIC-036E1_dead_mans_switch.md)); the heartbeat message that would show each bot's health is [`EPIC-036E`](../../Tasks/epics/EPIC-036_alerting_module/incomplete/EPIC-036E_heartbeat_dead_mans_switch_and_summary.md):

| Missing | What it leaves you without | Task |
| :--- | :--- | :--- |
| The other alert sources | a lost user-data stream or a revoked key is not sent to any channel | [`EPIC-036B`](../../Tasks/epics/EPIC-036_alerting_module/incomplete/EPIC-036B_alert_sources.md) |

Until then, use the host on a **testnet** venue. The host says whether a channel is configured: with no webhook stored, every start writes the WARNING `no alert channel is configured for bot events; nothing will tell you if a bot halts`, and `--resume-recovering` refuses without `--i-accept-silent-failures`. With a webhook stored, the start says `an alert channel carries bot events` instead.

Also true today, whatever the alerts:

- **Stopping leaves resting orders on the exchange** (decision O1) and nothing watches a stop loss or take profit while the host is down, for a stop, a crash or an upgrade. The dead man's switch (§3b) tells you the host went quiet; it does not close or protect anything.
- **A bot a restart left RECOVERING stays so until a person resumes it** (decision O2). The person does it from a second shell with `bot resume <id>` (§6, "Control one bot on the running host"), from the Bots tab, or by restarting with `--resume-recovering`, which sends each RECOVERING bot its own Resume (`BOT-183`), also when another bot's Resume opened the venue's session a moment before.
- The Windows steps and the checklist in §11 have **not been run on a machine** by their author. The Linux unit is checked mechanically (§12) but not yet run under a real systemd.

## 1. Layout this runbook assumes

| Thing | Linux | Windows |
| :--- | :--- | :--- |
| Checkout (the directory must be named `Sagittarius_Elite_Warrior`) | `/opt/sew/Sagittarius_Elite_Warrior` | `C:\sew\Sagittarius_Elite_Warrior` |
| Virtual environment | `/opt/sew/venv` | `C:\sew\venv` |
| Data root (`SEW_DATA_ROOT`: `state/`, `logs/`, the bots' files) | `/var/lib/sew` | `C:\ProgramData\sew` |
| Service account | `sew` (no login) | `NT SERVICE\sew-run` |
| Service | `sew-run.service` | `sew-run` |
| Secrets | `/etc/sew/` | the data root's `secrets\` |

The data root is outside the checkout so an update of the code never touches the bots, and the checkout can be read-only to the service.

## 2. Install on Linux

Needs systemd 251 or newer (`LoadCredential=` took a directory in 251; Ubuntu 24.04 ships 255, Ubuntu 22.04 ships 249 and is too old), Python 3.12 or newer (the floor; `preflight` checks it), `git`, and outbound HTTPS to the exchange. **No Qt and no display are needed**: the headless requirements install none of Qt's system libraries.

```bash
sudo useradd --system --home-dir /var/lib/sew --shell /usr/sbin/nologin --user-group sew
sudo install -d -o root -g root -m 0755 /opt/sew
sudo install -d -o sew -g sew -m 0700 /var/lib/sew
sudo install -d -o root -g sew -m 0750 /etc/sew /etc/sew/credentials

sudo git clone https://github.com/anhembedded/Sagittarius_Elite_Warrior.git /opt/sew/Sagittarius_Elite_Warrior
sudo python3.12 -m venv /opt/sew/venv
sudo /opt/sew/venv/bin/pip install -r /opt/sew/Sagittarius_Elite_Warrior/requirements-headless.txt \
    -c /opt/sew/Sagittarius_Elite_Warrior/requirements.lock
sudo /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/scripts/engine_pin.py install
sudo /opt/sew/venv/bin/python -m compileall -q /opt/sew/Sagittarius_Elite_Warrior   # see "Compile the checkout" below

sudo cp /opt/sew/Sagittarius_Elite_Warrior/deploy/linux/sew-run.service /etc/systemd/system/
sudo systemctl daemon-reload
```

**Compile the checkout, once after the clone and again after every `git pull` or `git checkout`** (`PRO-014`). The `sew` account cannot write into the checkout, so Python cannot keep the bytecode of the code it imports, and without it every command, `bot list` and `status` included, compiles the application's thousands of files again. Measured on the first VPS (2026-10-17): `bot list` took 3.66 s with the checkout uncompiled and 3.03 s after `compileall` as root, so skipping the step costs about 0.6 s on every command. Run it as root, which can write the `__pycache__` directories, with the service's own interpreter (the bytecode is valid for one Python minor version). It writes only `__pycache__` directories. Nothing else is needed: `PYTHONDONTWRITEBYTECODE=1` in the unit is deliberate and stays, so the host never tries to write there.

*Why the runbook and not the unit or a script.* `scripts/render_service_files.py` renders the unit from the host's constants, and `ExecStartPre=+` could run the command as root before each start, but that is wrong for two reasons: it would run outside the sandbox the unit exists to enforce (`ProtectSystem=strict`, `NoNewPrivileges`) and add seconds to every restart, and it would not help the commands an operator types between restarts, which are the ones that pay. There is no install script on Linux: this section is the install. The step therefore sits where the code changes, here and in step 4 of §8.

The unit is [`deploy/linux/sew-run.service`](../../deploy/linux/sew-run.service). It is **generated** from the host's own constants by `python3 scripts/render_service_files.py --write`; do not edit the copy in the repository, a guard compares it with the generator. To change a setting on one server use a drop-in (`sudo systemctl edit sew-run`), not an edit of the file. What it does:

- `Restart=on-failure`, `RestartSec=10`, `StartLimitIntervalSec=0`: restart after any failure, ten seconds apart, forever.
- `RestartPreventExitStatus=2 3 4 5`: **never** restart on a usage refusal (2), a held lock (3), a failed pre-flight (4) or a fault only the operator can fix (5: no key, a rejected key, a key that can withdraw). A restart would only repeat it, and repeating a rejected key is how an IP gets banned. The numbers come from the exit-code table; see [`exit_codes.md`](exit_codes.md). Exit `1` (a crash) and `6` (the exchange is out of reach) are restarted.
- `TimeoutStopSec=62`: above the longest stop. The formula is written in the unit: `ceil(--stop-timeout + 30 s + 2 s) + 5 s = ceil(25 + 30 + 2) + 5`. The host leaves by itself after 57 s at the latest, so systemd's `SIGKILL` never has to.
- `Type=notify` with `--host-signal sdnotify`: the unit is "active" only once the pre-flight passed and the bots were restored, so a start that dies in the pre-flight is a failed start. (The notify socket does not exist in a container: §13.)
- `MemoryMax=1G`, a dedicated no-login account, `ProtectSystem=strict` with the data root opened by `StateDirectory=`, `NoNewPrivileges` and the other lines you can read in the file. The host writes its data root and nothing else.
- No `log.file`, no `--dev`, no `--debug`: the log is standard output, which the journal captures and bounds ([`LOGGING.md`](LOGGING.md) §1).

## 3. Provision the keys

A key must be **bound to the server's address** at the exchange, must **not** be allowed to withdraw (the pre-flight refuses a key that can), and must never appear in a unit file, a plan file, a log or a shell history.

**The way to add, replace, remove and list a key: `sew-key`** (`BOT-200`; the venues are `spot_mainnet`, `futures_mainnet`, `spot_testnet`, `futures_testnet`; [decision](../../Tasks/epics/EPIC-038_headless_operation/DECISION_2026-10-20_server_keys_by_root_script.md)). A root-run script, [`deploy/linux/sew-key`](../../deploy/linux/sew-key), does what the commands below do by hand, and first asks the app whether the key is any good. Install it once (a link, so a `git pull` updates it; the checkout is root-owned, which a script run as root must be):

```bash
sudo ln -sf /opt/sew/Sagittarius_Elite_Warrior/deploy/linux/sew-key /usr/local/sbin/sew-key
sudo sew-key list                  # per venue: key present or not, file mode and owner; never a value
sudo sew-key add                   # type the key, then the secret (no echo); or: sudo sew-key add futures_mainnet
sudo sew-key remove futures_mainnet   # empty a mainnet venue's two files, or delete a testnet venue's two lines of sew.env
```

What `add` does, in order: it prompts for the key and the secret with `read -rsp` (no echo, not in your history, not in any argument); it pipes them to the app's `key check`, run as `sew` (`main.py key check`, which reads standard input only and writes nothing); it prints the venue the key belongs to, or why it is refused (a mainnet key that can withdraw, a key that may trade nothing, a key no environment accepts with the reason for each, a character a Binance key never has); you **type the venue's name** to confirm (a key that can trade both Spot and Futures on mainnet is stored for the one you type); and only then it writes. A mainnet key goes to `/etc/sew/credentials/<venue>_api_key` and `_api_secret`, mode `0600` root; a testnet key replaces its two lines in `/etc/sew/sew.env` (the other lines stay), mode `0640` root:sew. Each file is written as a temporary file beside the target and renamed over it, so a failure leaves the old key. It refuses when an environment variable for that venue is set in `sew.env` or in the unit (the app reads the environment before any file, so the file would never be used), when it is not root, and when `/etc/sew/credentials` does not exist (create it as §2 says).

If sudoers enables `log_input` (sudo I/O logging), sudo would record the key on its way to `key check`: turn it off for this command. The script exits `2` on a refusal it designed (wrong venue typed, shadowed, bad characters, not root), passes on the check's own `5` or `6`, and exits `1` only when a write fails. It also refuses to run as root while any `SEW_KEY_*` variable is set (those are for tests).

The script **never restarts the service**. The running host keeps the old key until you do:

```bash
sudo systemctl restart sew-run
```

After the restart every bot that was running comes back **RECOVERING**; resume each one yourself (§6): `bot resume <id>`, with `--confirm-venue <venue>` on a mainnet venue. Replacing a key on purpose, and what to do when one leaked, is §3c.

`key check` can be run by itself to ask the question without writing anything: `printf '%s\n%s\n' "$KEY" "$SECRET" | $M key check` (`$M` as in §6), but a key then sits in a shell variable or the history; prefer `sudo sew-key add`, which refuses to write. It exits `0` the key is usable, `2` the input cannot be a key, `5` the key must be replaced (it can withdraw, may trade nothing, or the exchange refuses it), `6` an environment did not answer. `--json` prints `sew.key/1`. It never prints or logs the key or the secret.

**The manual way** below is the fallback when the script cannot run (no `bash`, an unusual layout) and is what the script automates. It has no check of the key.

**Testnet** (the first run): the environment is the source. Put the four names in a file only root and the service can read:

```bash
sudo install -m 0640 -o root -g sew /dev/null /etc/sew/sew.env
sudoedit /etc/sew/sew.env
```

```text
BINANCE_FUTURES_TESTNET_API_KEY=<your futures testnet key>
BINANCE_FUTURES_TESTNET_API_SECRET=<your futures testnet secret>
BINANCE_SPOT_TESTNET_API_KEY=<your spot testnet key>
BINANCE_SPOT_TESTNET_API_SECRET=<your spot testnet secret>
```

A venue you do not use can be left out. The unit reads this file if it exists (`EnvironmentFile=-`).

**A secret whose file you have not created is a secret that is not set; the service still starts.** The unit has one line, `LoadCredential=sew:/etc/sew/credentials`. Given a directory, systemd loads every regular file in it, subdirectories included, as the credential `sew_<file name>` (symlinks are ignored; `systemd.exec(5)`; keep the directory flat), so `/etc/sew/credentials/spot_mainnet_api_key` reaches the service as `$CREDENTIALS_DIRECTORY/sew_spot_mainnet_api_key`, and a file that is not there is simply not loaded. A testnet-only server, or one without a webhook, therefore needs no placeholder files. (Until 2026-10-20 the unit had one `LoadCredential=` line per file and systemd refused to start, `status=243/CREDENTIALS`, when one was missing; observed on the first VPS install, 2026-10-14, systemd 255.) What stays true: the **directory** `/etc/sew/credentials` must exist (§2 creates it, and so does a server that ran the old unit), and an **empty file** still reads as "no key".

**Mainnet**: systemd credentials (decision O3). Each secret is a file only root can read; the unit hands the directory to the service, so a value is not in the service's environment and not inherited by a child process. Create the file for each venue or alert you use and no other. `sew-key add` does it; by hand, for a venue you use, type the value without echoing it. `read -s` is bash (the shell you are logged in to; dash, which is `sh` on Debian and Ubuntu, has no `read -s`), and `printf` is a builtin, so the value is in no process's argument list and not in your history:

```bash
read -rsp "futures mainnet key: " v; echo
[ -e /etc/sew/credentials/futures_mainnet_api_key ] || sudo install -m 0600 -o root -g root /dev/null /etc/sew/credentials/futures_mainnet_api_key
printf '%s' "$v" | sudo tee /etc/sew/credentials/futures_mainnet_api_key > /dev/null; unset v
```

The names are `futures_mainnet_api_key`, `futures_mainnet_api_secret`, `spot_mainnet_api_key`, `spot_mainnet_api_secret`, `alerting_discord_webhook` and `alerting_deadman_ping_url`; any other file in the directory is loaded and ignored. Mainnet bots are never started by the host without you typing the venue (`--confirm-venue`, decision O8); the unit passes none.

**Upgrading an existing install to the directory form (once, 2026-10-20).** Your files stay where they are, with the names they have: nothing is moved, renamed or recreated. The new code reads the credential under both names (`sew_<file>` first, then the bare name the old unit handed it), so the order below is safe at every step; do it in this order, because the **new unit with the old code** would find no key (the old code asks for the bare name):

1. `sudo systemctl stop sew-run`, and read that it drained (§8 steps 1 and 2).
2. Upgrade the code (§8 steps 3 and 4: copy the state aside, `git checkout`, `pip install`, `engine_pin.py install`, `compileall`).
3. Install the regenerated unit, then ask systemd what the service would see. The second command lists credential **names** only, never a value; expect one `sew_<file>` per file you created:

```bash
sudo cp /opt/sew/Sagittarius_Elite_Warrior/deploy/linux/sew-run.service /etc/systemd/system/ && sudo systemctl daemon-reload
sudo systemd-run --wait --pipe --quiet --uid=sew --gid=sew -p LoadCredential=sew:/etc/sew/credentials \
  /usr/bin/bash -c 'ls -1 "$CREDENTIALS_DIRECTORY"'
```

4. **Check that no drop-in resets the line.** A bare `LoadCredential=` (no value) in a drop-in empties the unit's whole list, the directory line included, and the service then starts with **no** credential at all: no key, no webhook, no check-in URL, and no error. Older versions of this runbook told a testnet-only server to add one. The command must print the unit's line and nothing else; if a drop-in line shows, delete it from the file under `/etc/systemd/system/sew-run.service.d/` and run `sudo systemctl daemon-reload` again:

```bash
systemctl cat sew-run | grep LoadCredential   # exactly: LoadCredential=sew:/etc/sew/credentials
```

5. `sudo systemctl start sew-run`, then read the credential lines: `journalctl -u sew-run -o cat | grep -E "preflight|alert-channel|dead-mans-switch"`. A mainnet venue in use must still answer `credentials-present` from `systemd-credential`; a webhook or check-in URL must still say `on`.

You may now delete the empty placeholder files you created only to satisfy the old unit; leaving them does no harm. **Rollback** to a release whose unit has one line per file needs those files again: for each name above that is missing, `[ -e F ] || sudo install -m 0600 -o root -g root /dev/null F`, before you install the old unit.

**Alerts to Discord** (`EPIC-036G`, decision D3 of the [2026-10-15 alerting record](../../Tasks/epics/EPIC-036_alerting_module/DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md)). The webhook is a secret like a key: whoever holds its URL can post to your channel. It is the systemd credential `alerting_discord_webhook`, read only by the service, never in an environment variable, a config file or a log line. In Discord: the channel's **Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL** (a channel only you read is best). Then write it to its file and restart the service (`sudo systemctl restart sew-run`):

```bash
[ -e /etc/sew/credentials/alerting_discord_webhook ] || sudo install -m 0600 -o root -g root /dev/null /etc/sew/credentials/alerting_discord_webhook
# Paste the URL without echoing it, as for a key above.
read -rsp "Discord webhook URL: " v; echo
printf '%s' "$v" | sudo tee /etc/sew/credentials/alerting_discord_webhook > /dev/null; unset v
```

An empty file means no Discord channel, and the host warns at start as in §0. A value that is not a Discord webhook URL (`https://discord.com/api/webhooks/<id>/<token>`) is refused the same way, with the WARNING `[alert-channel] discord is off: the Discord webhook credential (alerting_discord_webhook) does not hold a Discord webhook URL`, which never quotes the value. **To rotate the webhook** (it leaked, or you deleted it in Discord; the order of the steps is in §3c): create a new one, run the block above again, and restart: systemd copies a credential when the service starts, so the running host keeps the old one until then. On Windows the webhook is a file named `alerting_discord_webhook` in the `SEW_SECRET_FILES_DIR` directory (§9), like the keys.

## 3b. The dead man's switch: be told when the host goes silent

`EPIC-036E1`, [decision](../../Tasks/epics/EPIC-036_alerting_module/DECISION_2026-10-20_dead_mans_switch.md). Discord alerts are sent from inside the running process, so a process that dies, hangs or sits on a powered-off VPS tells nobody, and resting orders and any Futures position stay on the exchange (§0). The dead man's switch is the signal that **stops**: the host posts to an external monitor every 5 minutes, and the monitor alerts you when the posts stop. **It is off until you store a URL**, and it costs nothing then.

1. **Create the check.** On [healthchecks.io](https://healthchecks.io) (or any service that alerts when a URL goes quiet) make a check with **period 5 minutes and grace 10 minutes**, and add your notification channels (Discord, e-mail; use one that does not depend on this VPS). Copy its ping URL, `https://hc-ping.com/<uuid>`. The URL is a secret: whoever holds it can fake a heartbeat.
2. **Store it.** The same route as the webhook (§3); `sew-key` is for Binance keys only and is not used.

```bash
[ -e /etc/sew/credentials/alerting_deadman_ping_url ] || sudo install -m 0600 -o root -g root /dev/null /etc/sew/credentials/alerting_deadman_ping_url
read -rsp "Check-in URL: " v; echo
printf '%s' "$v" | sudo tee /etc/sew/credentials/alerting_deadman_ping_url > /dev/null; unset v
```

Then `sudo systemctl restart sew-run`; systemd copies a credential at start.

3. **Read the start line** (`journalctl -u sew-run | grep dead-mans-switch`): `[dead-mans-switch] on: pinging the check-in URL in the credential alerting_deadman_ping_url every 300 s`. `off: no check-in URL is stored` means the file is empty; `off: the credential ... does not hold an https URL` means the value is wrong. Neither line quotes the value. After a restart the check turns green within a minute.
4. **What a ping means.** The host pings only while its alert worker makes progress: each delivery lane and the housekeeping pass must have finished a pass in the last 5 minutes. A wedged worker therefore stops the ping and the monitor alerts you, though the process still exists (`[dead-mans-switch] the alert worker is not making progress (stalled: ...)` names the thread). It proves the process and its alert worker are alive, **not** that each bot is healthy.
5. **Prove it once (the kill test, checklist row 12).** With the check green, `sudo systemctl stop sew-run` (or `kill -9` the process; `Restart=on-failure` brings it back in 10 s, so use `stop`). After the period plus the grace (about 15 minutes) the monitor must alert you. Start the service again and the check recovers. Write the date in the checklist.
6. **If the monitor itself cannot be reached** the host logs `[dead-mans-switch] ping failed (n in a row)` and, after three in a row, sends one **Alert channel failing: dead_mans_switch** message to Discord, so a wrong URL (HTTP 404) or a service outage is not silent. It never delays another alert.

A stop on purpose is also silence: the check fires after its grace, which is what you want while resting orders stay on the exchange (decision O1). **Pause the check in the monitor before a planned upgrade** (§8). A restart (`RestartSec=10`) is inside the grace and fires nothing. The Windows service reads the same name from its secret store; that route is unverified on a real service, as for the webhook (§0, §9).

## 3c. Rotate a key, the webhook or the check-in URL

`EPIC-026` must-have 8 of the [2026-10-20 review](../../Tasks/epics/EPIC-026_road_to_real_money/REVIEW_2026-10-20_what_is_still_missing.md). Two cases, and the order of the first step is the whole difference: **planned** (the new secret exists before the old one dies) and **after a suspected leak** (the old one dies first). `$M` is the prefix of §6.

**What a restart does to the market.** `sudo systemctl restart sew-run` is a stop and a start. The stop leaves every resting order on the exchange (§0, decision O1) and takes up to 57 s; the start runs the pre-flight and restores the bots, so the host is down for about a minute. A Futures Grid Long or Short bot keeps its protective stop on the exchange meanwhile (`EPIC-039L`); a Spot bot has none, and nothing watches any stop loss or take profit while the host is down (§0). Orders may fill while it is down. Every bot that was RUNNING or PAUSED comes back **RECOVERING** and places nothing until you resume it: `Resume` reads the exchange by the bot's tag, not the file's memory of its orders (§6). A venue whose bots are RECOVERING starts no new bot (`VENUE_RECOVERING`, §8).

### Planned rotation of a Binance key

The old key stays valid until you delete it, so there is no gap: the new key must work **before** the old one goes.

1. At the exchange, create the new key: bound to this server's address, **no withdrawal**, only the permissions the bots need (§3). Do not delete the old key yet.
2. Store it. `add` asks the app whether the key is any good and refuses a key that can withdraw; it replaces the venue's two files in one rename each and does not touch the running host:

```bash
sudo sew-key add futures_mainnet      # or spot_mainnet, spot_testnet, futures_testnet
sudo sew-key list                     # present, mode 0600, owner root; never a value
```

3. Restart, read the pre-flight, resume the bots. The host reads a credential only at start, so until the restart it still trades with the old key. A mainnet bot needs `--confirm-venue` (§6):

```bash
sudo systemctl restart sew-run
systemctl status sew-run --no-pager
journalctl -u sew-run -o cat --since "5 minutes ago" | grep '\[preflight\]'
M="sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py"
$M bot list                                              # every bot that was running reads RECOVERING
$M bot resume 44wa1x --confirm-venue futures_mainnet     # one at a time; 44wa1x stands for each id from bot list
$M status
```

   The pre-flight lines to read are `credentials-present`, `key-permissions`, `no-withdraw-permission` and `outbound-address` (§4): all four must pass for the new key. `systemctl status` says `active (running)` only after the pre-flight passed (`Type=notify`). Exit `5` (a rejected key, a key that can withdraw) is not restarted by the unit: the old key is still valid, so fix the cause, or `sudo sew-key add` the old key back, then `sudo systemctl reset-failed sew-run && sudo systemctl start sew-run`. Resting orders stay on the exchange the whole time, which is why the old key is not deleted yet.
4. Only when the pre-flight passed and `bot list` shows the bots back on their feet, **delete the old key at the exchange**. The running host uses the new key, so nothing changes for it.

### After a suspected leak

The key is in a log, a chat, a screenshot, a shell history, or the server may be compromised. **Delete the key at the exchange first**; everything else waits for that, because only the exchange ends the other party's access. A key bound to this server's address is useless from any other address, and one without withdrawal (§3) cannot move money out; the danger is a key whose address binding you did not set, or someone on the server itself, who can place and cancel orders with it.

1. At the exchange, **delete** the key (not only restrict it). Then read the account's order history, trade history and open orders for anything you did not place. If the server itself may be compromised (someone had a shell), rotate the Discord webhook and the check-in URL below as well and treat the root-only files in `/etc/sew` as seen.
2. Stop the host, so it stops sending a rejected key (repeating one is how an IP gets banned, §2). Resting orders **stay on the exchange** and nothing watches them now: decide at the exchange's own web or app login whether to cancel them or to close a position; do not wait for the host.

```bash
sudo systemctl stop sew-run
sudo sew-key remove futures_mainnet   # empty the leaked key's two files so the old value is gone from this disk; the venue then has no key
```

3. Create a new key at the exchange (step 1 of the planned rotation), `sudo sew-key add <venue>`, then `sudo systemctl start sew-run` and the pre-flight and resume lines of step 3 above. Do not resume a bot until you have looked at the exchange's open orders: a bot's resume reconciles by tag and does not know about an order someone else placed.
4. Find where the old value went and remove it: your shell history, the chat or ticket it was pasted into. The archives of §8b hold no key, so there is nothing to purge from a backup made by the runbook; a provider snapshot of the VPS disk does hold `/etc/sew`.

### The Discord webhook and the dead man's switch URL

Both are secrets stored the way §3 and §3b describe, and both are read when the service starts, so **one restart covers a key and both of them**. Order, the same rule: planned, new before old; a leak, the old one deleted first.

- **Discord webhook.** In Discord, the channel's **Edit Channel → Integrations → Webhooks**: create a new webhook (planned) and delete the old one only after the new one has delivered a test message; on a leak, delete the old one first, since anyone holding the URL can post to your channel. Write the new URL as §3 shows (`alerting_discord_webhook`), `sudo systemctl restart sew-run`, then send the test message of §5 (`alert test`). While the old webhook is deleted and the new one is not stored, halts reach nobody: watch the log (`[health]`, §6) yourself.
- **Dead man's switch check-in URL.** At the monitor (§3b) make a **new check** with the same period (5 minutes) and grace (10 minutes) and the same notification channels, store its URL as §3b step 2 shows (`alerting_deadman_ping_url`), restart, and read `[dead-mans-switch] on:` (§3b step 3). When the new check is green, delete the old check: whoever holds the old URL can keep it green while the host is dead. A leak of this URL is lower stakes than a key (it cannot trade), but the old check must go all the same. The restart is inside the old check's grace and fires nothing.

## 4. Run the pre-flight

For **testnet**, as the service account with the keys in the environment (the service is not running, so the data root is free):

```bash
sudo -u sew bash -c 'set -a; . /etc/sew/sew.env; set +a; \
  PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew \
  /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py preflight --venue futures_testnet'
echo "exit $?"
```

For **mainnet** the credentials exist only inside the unit, so the pre-flight is the one `run` itself performs before it restores any bot: `sudo systemctl start sew-run`, then read its lines (`journalctl -u sew-run -o cat | grep '\[preflight\]'`). A failed check stops the start with exit 4, 5 or 6 and an ERROR line per finding with its remedy.

Exit codes of `preflight`: `0` nothing failed (a WARN passes), `4` a check failed, `5` credentials absent or refused, `6` the exchange is unreachable. What to do on each check:

| Check | A FAIL or WARN means | Do |
| :--- | :--- | :--- |
| `python-floor` | the interpreter is below 3.12 | install Python 3.12+ and rebuild `/opt/sew/venv` |
| `data-root-writable` | the service account cannot write the data root | `sudo chown -R sew:sew /var/lib/sew`; check it is not a read-only mount |
| `disk-space` | WARN below 1 GiB or 10 % free, FAIL below 100 MiB | free space; a full disk stops the database write, not the network call, so the symptoms are strange |
| `clock-skew` | WARN above 500 ms, FAIL at 1000 ms against the exchange's time | `timedatectl status`; enable `systemd-timesyncd` or `chrony`; the exchange refuses a request stamped 1000 ms ahead (`-1021`) |
| `credentials-present` | no key for a venue in use (exit 5) | §3; the line names which source answered, never the value |
| `key-permissions` | the exchange rejected the key (`-2015`: key, address or permission) or the signature (`-1022`) | check the key's IP binding includes this server, and that its secret is the right one |
| `no-withdraw-permission` | the key can withdraw | create a new key without withdrawal; never run with this one |
| `outbound-address` | the address the exchange sees is not the one the key is bound to, or could not be read | bind the key to the address shown, or fix the route |
| `bot-files-readable` | WARN: a bot file in `state/bots/` was written by a newer build, or is damaged; its bot is **not loaded** and the file is left untouched | §8: roll back to the build that wrote it, or copy the file out if it is damaged; do not edit it |
| `account-loss-cap` | FAIL: `bots.account_loss_cap` is set and cannot be read (exit 4, the host would not start). WARN: no figure and this host runs a mainnet venue (nothing stops the day's loss); the record cannot be read (the cap starts tripped); the cap is tripped (no bot starts or resumes) | Set `bots.account_loss_cap` to an amount and its quote asset, e.g. `500 USDT`, or empty it to switch the cap off (testnet); for a trip or an unreadable record see "The account-level loss cap" in §6 and run `bot loss-cap-ack` on the running host |

`--skip <ids>` skips checks; `run --skip-preflight` skips them all and logs a WARNING. Neither belongs in the unit.

## 5. First run, on the testnet

```bash
sudo systemctl enable --now sew-run
systemctl status sew-run --no-pager
journalctl -u sew-run -o cat -f
```

Expected, in order: `[run]` (the options in effect), `[preflight]`, `[host] BOOTING -> SERVING`, the one `[alerts]` WARNING from §0, then a `[health]` line every 60 seconds. Look at it from a second process:

```bash
sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew \
  /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py status
echo "exit $?"
```

`status` opens no connection and takes no lock: it reads `state/health.json` and the lock. Exit `0` the host is running and healthy, `10` no host is running, `11` running but unhealthy (the snapshot is stale or a section is unavailable or degraded).

**Send a test message to Discord.** `main.py alert test` sends one message to every configured channel and prints what each answered; it writes nothing and takes no lock, so it runs beside the running host. The webhook exists only inside the unit, so run it with the unit's credentials directory:

```bash
sudo systemd-run --wait --pipe --quiet --uid=sew --gid=sew \
  -p LoadCredential=sew:/etc/sew/credentials \
  -E PYTHONPATH=/opt/sew -E SEW_DATA_ROOT=/var/lib/sew \
  /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py alert test
```

Exit `0` the message was taken (check that it arrived: "sent" means Discord accepted it, not that you read it), `5` no channel is configured or Discord refused the webhook (a 401 or 404: it was deleted; rotate it as in §3), `1` Discord did not answer or asked to wait. The answer names the status, never the URL.

## 6. Day to day

**How the reports look (`BOT-195`, [`PRO-017`](../../Tasks/proposal/PRO-017.md)).** Typed at a terminal, the text reports (`bot list`, `bot show`, `bot order`, `status`, `exchange-status`, ...) print as a table or an aligned block with a bold header, and a state, a side or a profit figure is coloured (`RUNNING` and `FILLED` green, `PAUSED`, `RECOVERING` and `CANCELLED` yellow, `HALTED`, `ERROR` and `REJECTED` red; `BUY` and `LONG` green, `SELL` and `SHORT` red; a loss red, a profit green). The word or the minus sign is always printed too. **At a terminal the report is always drawn by `rich`, however wide it is** (`BOT-198`): a long cell, such as the `Ladder` or a `Recovery` row of `bot show`, wraps onto further lines; a table too wide for the terminal even then (`bot list` at 80 columns) prints one block per bot instead. An id, a state word and a number are never cut. A failed command's sentence is red too. **Anything that is not a person at a terminal gets exactly the plain text the report always had**: a pipe or a file, the systemd journal, `ssh host command` without a terminal, `NO_COLOR` set to any value and `TERM=dumb` (your choice, so silent). If `rich` is not installed, a terminal gets the plain text and one line on stderr says so (`note: rich is not installed; printing plain text (pip install ...)`); stdout stays plain. `--json` is never touched. To turn the tables off on a terminal, set `NO_COLOR=1` (`NO_COLOR=1 main.py bot list`). The logs are not coloured: the journal keeps plain text (§10). The server needs `rich`, which `pip install -r requirements-headless.txt -c requirements.lock` installs (a pure-Python wheel, about 2 MB with its two small dependencies); without it the reports are plain.

| Want | Linux | Windows |
| :--- | :--- | :--- |
| Start / stop / restart | `systemctl start\|stop\|restart sew-run` | `nssm start\|stop\|restart sew-run` |
| Run at boot | `systemctl enable sew-run` | set by the install script (`SERVICE_AUTO_START`) |
| Is it alive and what does it hold | `main.py status` (as §5) | the same, from the service account or an Administrator who sets `SEW_DATA_ROOT` |
| What orders does one bot hold (as its file records them, not from the exchange) | `main.py bot order <id> [--json]` (below) | the same |
| Stop, pause, resume, start or edit one bot without stopping the host | `main.py bot stop\|pause\|resume\|start <id>` or `bot edit <id> --set key=value` as the service account (below) | the same, from the service account |
| Follow the log | `journalctl -u sew-run -o cat -f` | `Get-Content C:\ProgramData\sew\service-logs\sew-run.log -Wait` |
| Follow the log with the values coloured, or filtered (level, bot, tag, time) | `journalctl -u sew-run -o cat -f \| main.py logs [--level warning] [--bot <id>]` (below) | `main.py logs --file C:\ProgramData\sew\service-logs\sew-run.log --follow` |
| Only problems | `journalctl -u sew-run -o cat \| grep -E ' - (WARNING\|ERROR\|CRITICAL) - '` | `Get-Content C:\ProgramData\sew\service-logs\sew-run.log \| Select-String ' - (WARNING\|ERROR\|CRITICAL) - '` |

**Reading the log coloured** (`BOT-199`, full guide in [`LOGGING.md`](LOGGING.md) §8). On the VPS, in an SSH terminal: `journalctl -u sew-run -o cat -f | .venv/bin/python src/main.py logs` (add `--level warning`, `--bot <id>`, `--tag <name>` or `--since 2h`). The values each log call substituted (a bot id, a quantity, a reason) get their own colour, the level, tag and traceback theirs. It prints the input unchanged when the output is a pipe or file, when `NO_COLOR` is set, with `--no-color`, or when `rich` is missing, so it is safe in a script; it reads and writes text only and never touches the service.

**Reading the health line** (full table in [`LOGGING.md`](LOGGING.md) §4): `[health] state=SERVING up=3600s bots=running:3,paused:1,halted:0,recovering:0,error:0,starting:0,stopping:0,awaiting_recovery:0 tick_age_s=2 stream_down_s=5 skew_ms=-120 rss_mb=310`. It is progress, not liveness: alert yourself when the line stops appearing, when `tick_age_s` or `stream_down_s` keep growing, when `halted`, `error` or `recovering` is above zero that you did not expect, when `starting` or `stopping` stays above zero for minutes, or when `skew_ms` approaches 1000. `na` means "not measured yet".

**Judging a 24-hour run clean** (`BUG-209`). In normal mode (no `--dev`, no `--debug`) a clean run has **no** record matching ` - (WARNING|ERROR|CRITICAL) - ` except the one `[alerts]` WARNING at start, and every `[health]` line shows `halted:0,error:0`. Anything else is a finding. What reaches those levels, by tag, is the table in [`LOGGING.md`](LOGGING.md) §6: a bot that lands in HALTED is a WARNING and one that lands in ERROR is an ERROR (`[bot-transition]`, with the reason), an event the lifecycle refuses is a WARNING (`[bot-transition-refused]`), a fill or an order end the stream lost and a reconcile recovered is a WARNING (`[missed-fill]`, `[missed-end]`), a periodic read that fails is one WARNING per streak and one INFO when it recovers (`[refresh-failed]`, `[refresh-recovered]`), a clock above 500 ms from the exchange is a WARNING and at 1000 ms an ERROR (`[clock-skew]`), and a market stream that failed is an ERROR (`[kline-stream]`).

**A process that was killed says nothing in the app's log.** A hard kill or the kernel's OOM killer leaves no line of the app's own, and systemd's lines (`Main process exited`, `Scheduled restart`) do not match the grep above. Besides the grep, check `systemctl show sew-run -p NRestarts` (it should be `0` for a run nobody restarted) and `journalctl -u sew-run | grep -E 'Main process exited|Scheduled restart'`. After a restart the bots that were running come back RECOVERING, one `[recovering]` WARNING each (§11 row 2).

### The orders one bot holds (`bot order`)

`BOT-187`. `main.py bot order <id>` prints, per order, the grid level, side, price, quantity, executed quantity, the level's state as the file records it (`RESTING`, `PARTIAL`, ...) and the client order id: the rows the Bots tab's "orders" table shows. It is **read-only** (like `bot show`: it takes no lock, works beside a running host and on a read-only copy of the data root) and **stored, not live**: it reads the bot's saved run record and asks the exchange nothing, so with no host running, or after a crash, the file can be behind the exchange. The text says so in its first line, and `--json` carries `source: "stored"` and `app_running`. A bot with no run prints `No orders.`; a RUNNING bot whose run record cannot be read prints `Orders unknown` (never `No orders.`); a bot file this build cannot read is named with its path; an unknown id exits `2`. Live open orders need an order session and are a separate, later command.

### The ladder and where the price stands (`bot show`, `bot show --grids`, `bot list`)

`BOT-193`. `main.py bot show <id>` also prints, after the earnings, the rows the Bots tab's Plan panel shows: `Ladder` (the spacing model, the smallest and largest step in per cent, the average profit of one cycle and the fee it is before or after), `Average per cycle (net of fees)` (what a completed cycle booked on average: grid profit over cycles, net of both legs' fees and without Futures funding), `Last price heard` (the last price the bot heard and how long ago), `Lower edge` and `Upper edge` (the range edges, with the distance from that price in per cent), `Stop loss` and `Take profit` (`off`, or the price with its distance) and, on Futures, `Liquidation price`. `bot show <id> --grids` adds one row per grid: the buy and the sell level above it, the step, the net step, the profit of one cycle before and after fees, and what the saved run says that grid is doing (`waiting to buy`, `waiting to sell`, `waiting to buy and sell` where the price stands, `no order`, `not recorded`). `bot list` has a `GRID STEP` column (`1.45% to 1.67%`, top to bottom, or `1.20% each`). An amount that two decimals would round to zero is written `less than 0.01`, never `0.00`. Like `bot order` they are **read-only** and **stored, not live**: they come from the bot's saved file, ask the exchange nothing, take no lock and need no host, and the ladder is built from the bot's **current saved parameters** (a `bot edit` shows at once), so the levels are the parameters' raw levels, within one tick of the resting orders.

Read each figure by its label: the steps and the net step are *designed* (from the parameters), the profit per cycle is an *estimate* (the capital over the `grid_count` levels that hold an order, not a promise: the bot sizes each order by the exchange's lot step and its opening price), and the state of a grid is *recorded* (the saved run). Nothing here says how often the price will cross a level and there is no profit per day. **The account's maker fee rate is recorded in the bot's file when a run starts (`BOT-194`), and with it the net step and the profit per cycle after fees are filled in; the `Ladder` line then says "after the 0.02% maker fee on both legs (rate recorded at run start)", the net columns of `--grids` are headed with the run-start rate and a note under the table names it, and the Bots tab words the same figures "after fees (run-start rate)".** It is the rate of that start, not today's: a fee tier change later leaves it stale until the next start, and a resume keeps it. A bot whose run began before this build recorded none, so it reads "before fees: no maker rate is recorded for this run" and prints `—` in the net columns until it is started again. **The Futures liquidation price is the exchange's report and is not saved, so `Liquidation price` says it is not in the record.** A price the bot has not heard is `no price yet` and its distances are left out, never zero. When the saved run's resting orders are not on the rungs of the current parameters (they were edited after the run began) every grid says `not recorded` and a note says why. `--json` carries all of it under `ladder` (in a `bot list` the summary and the price position, with `rows` empty; exact decimals as text, `null` where unknown; `rows[].state` is the state's name, `position.age_seconds` an integer; `ladder.available` is `false` with a `reason` for a bot whose parameters make no ladder or whose kind has none).

### How much has a bot earned (`bot list`, `bot show`)

`BOT-192`. `main.py bot list` has three columns, `GRID PROFIT`, `CYCLES` and `TOTAL PNL`, and `bot show <id>` four rows in this order, `Grid profit`, `Cycles`, `Total PnL` and `Unrealised`: the figures and the words of the Bots tab, whose table has the same `Grid profit`, `Cycles` and `Total PnL` columns and whose detail panel lists "Profit from completed cycles" first, then the cycles, the total and "of which unrealised". **Grid profit is what the completed buy/sell cycles booked, net of the fees of both legs of each cycle, and excludes a Futures bot's funding.** The total adds what is still held, at the price the bot itself last heard (`Unrealised` shows that part, with the price), and the funding; read the grid profit for "what has the bot earned", the total for "where does the bot stand". Like `bot order` they are **read-only** and **stored, not live**: they come from the bot's saved run record, ask the exchange nothing, take no lock and need no host, so they work beside a running host and on a read-only copy; with no host running they are what the last run saved. A figure the record cannot give is never printed as zero: `—` means the bot has no readable run record (a draft, or a record this build cannot read) or, for `Unrealised`, holds nothing; `no price yet` means the figure waits for a price the bot has not heard (it holds base and has seen no tick); a fee that could not be priced is named after the total. A new run of the same bot (stop, then start) begins a new record, so its grid profit starts again from zero cycles. `--json` carries them under `earnings` (`null` when there is no run record): `grid_profit`, `total_pnl`, `unrealised` and `mark_price` are exact decimals as text and `null` while unknown (`total_pnl`, `unrealised` and `mark_price` wait for a price), `completed_cycles` and `unpriced_fees` are integers.

### Control one bot on the running host (`bot stop`, `bot pause`, `bot resume`, `bot start`, `bot edit`)

`EPIC-038J`, `EPIC-038K` and `EPIC-038L`, decision O4 (the owner chose a local command directory). The host holds the data root's lock, so a second shell cannot change a bot itself; instead it hands the host a **command**, and the host runs the same Stop, Pause, Resume, Start or Save the Bots tab runs.

```bash
M="sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py"
$M bot show 44wa1x                  # what state is it in?
$M bot show 44wa1x --params         # every stored parameter, key and value, sorted by key (reads the file: works beside a running host)
$M bot stop 44wa1x [--confirm-venue spot_mainnet]   # Spot: cancel its orders, keep the coin, STOPPING then STOPPED
$M bot stop 44wa1x --close-position [--confirm-venue futures_mainnet]   # Futures: cancel its orders and close the position at market
$M bot pause 44wa1x                 # place no orders; the resting ones stay
$M bot resume 44wa1x                # a PAUSED or RECOVERING bot; mainnet RECOVERING: add --confirm-venue spot_mainnet
$M bot start 44wa1x [--confirm-venue spot_mainnet]  # a DRAFT or STOPPED bot, once; the other bots are not touched
$M bot edit 44wa1x --set lower=81000 --set upper=90000   # a DRAFT or STOPPED bot's parameters; it lands on DRAFT; places no order
```

- **Who may do it.** Only the account the host runs as (`sew` above). The host makes `state/control/` mode `0700` when `run` starts; each command is a file mode `0600` in it, and the host refuses any file that is not owner-only and the host account's own (on Windows, an ACL of the service account and the administrators). There is no password and no port: the host opens **no listening socket** for this (a test reads the host's sockets). An account that cannot write the directory gets exit `5`; a host that is not a `run` host (the desktop app) has no directory and gets exit `5` too.
- **What you see.** The command waits for the host's answer (`--wait`, 15 s by default) and prints the host's own sentence. Exit `0` the bot accepted it; `2` the bot's own rule refused it (not found, not in a state that allows it, a HALTED bot to resume...) and nothing changed; `5` this account has no control; `10` **no host is running, nothing was written**; `11` a host is running and recorded no answer in time (the command is withdrawn if the host never took it; see the audit). A stop is asynchronous: `0` means STOPPING. Check `bot show` for STOPPED.
- **At most once.** Every command has an id; the host writes `received` to `state/control/audit.jsonl` before it acts and the verdict after (`executed`, `refused`, `failed`, `malformed`, `unauthorised`, `replayed`, `expired`). A file with an id the host has seen is a replay and does nothing, even after a restart. A file older than 5 minutes (or dated more than 1 minute ahead of the host's clock) is `expired`: it does not run late. The audit is append-only, grows by two lines a command and is never rotated; it holds ids, actions and sentences, never a secret.
- **A HALTED bot is not resumed this way.** Its resume proposes a ladder that a person reads and confirms; use `run --resume-halted` (below) or the Bots tab.
- **A Stop opens a closed order session first** (the owner's answer "B", 2026-10-17). An Emergency Stop or a restart closes the venue's order session, and a stop cannot finish without it, so `bot stop` opens it as Start and Resume do. The opening is announced as opened for the bot you stop (`BOT-183`), so **after a host restart the other RECOVERING bots of that venue keep waiting for their own resume** (`bot resume <id>`, the Bots tab or `run --resume-recovering`); the stop resumes none of them. On a mainnet venue the session uses real money, so add `--confirm-venue spot_mainnet`; without it the stop is refused, nothing is opened, and the refusal names the other RECOVERING bots that stay waiting; an already open session, or a testnet, needs no answer. The host's own shutdown stop (`--on-stop stop-bots`) still opens nothing.
- **A Futures bot is stopped only with `--close-position`** (`BUG-224`). A leveraged position is never kept when a bot stops (no stop stands on the exchange for it yet, `EPIC-039H`), so `bot stop` on a Futures bot **without** the flag is refused with exit `2` and changes nothing; the refusal says that stopping closes the position at market and names the flag. With the flag the host runs the Bots tab's "Close the position at market": the bot's orders are cancelled and its position is closed by a reduce-only market order, at the market price, and on `futures_mainnet` that is real money. The flag is the whole consent to the close; `--confirm-venue` is still what opens a closed mainnet order session. On a Spot bot the flag sells the coin the bot holds, as the screen's close does; without it the coin is kept. The host's shutdown stop (`--on-stop stop-bots`) still keeps and so still leaves a Futures bot: it is refused, listed as left, and stopped later with `bot stop <id> --close-position`.
- **Start one bot, with no restart of the host** (`EPIC-038K`). An older host that is sent `start` reads the unknown action as a malformed command and does nothing (exit `1`, audited `malformed`): upgrade the host before using this verb. `bot start <id>` runs the Start the Bots tab and `--start-planned` run, once, and audits it; it starts that bot and no other. Only a DRAFT or STOPPED bot starts. The Start's own checks refuse it in words: **one active bot per symbol** (`ONE_ACTIVE_BOT_PER_SYMBOL`, naming the holder), **at most five active bots per venue** (`VENUE_FULL`), and **a venue that holds a RECOVERING bot starts nothing** (`VENUE_RECOVERING`: starting opens the order session, which would return the waiting bots to trading, so resume or stop them first, §8 "Bots on more than one venue"). A HALTED or AWAITING_RECOVERY bot is refused with exit `2`: its resume proposes a ladder a person reads, so use `run --resume-halted` or the Bots tab. On a mainnet venue the start uses real money: add `--confirm-venue spot_mainnet` (or `futures_mainnet`); without it nothing is opened or started and the refusal names the venue's other RECOVERING bots, because opening the order session reconciles them. A Futures start is the same Start and costs the same request weight (about 300).
- **Edit one bot's parameters, with no restart of the host** (`EPIC-038L`). The case it was built for: `bot start sj9rno` is refused ("The price 81233 is below the range's lower bound 81305. Starting now would buy ... Lower the range to include the price"), and `bot apply` cannot correct it because the running host holds the data root ("Another copy ... read-only"). So: `bot stop <id>` until `bot show` says STOPPED (a DRAFT bot needs no stop), then `bot show <id> --params` to read the current values, `bot edit <id> --set lower=81000`, then `bot start <id>`. The other bots keep trading throughout. `bot edit` is the Save of the Bots tab for one bot: the lifecycle table decides (only **DRAFT and STOPPED**; RUNNING, PAUSED, HALTED, RECOVERING, AWAITING_RECOVERY, STARTING, STOPPING and ERROR are refused in words, exit `2`, nothing changed), and the bot lands on **DRAFT**, so it does nothing until `bot start`. It is an edit and not an order: it needs **no `--confirm-venue`**, even on `spot_mainnet` or `futures_mainnet`, and opens no order session; the real-money question stays at `bot start`, whose guard is untouched.
  - **What you read first.** `bot show <id> --params` prints every parameter the bot stores, one row per key, sorted by key, values exactly as stored (no rounding; `--json` carries them under `parameters`, `--format` works as for every report). It is a plain read of the bot's file, so it works on the read-only copy beside the host with no command file and no host round trip. The keys it lists are the ones `--set` accepts.
  - **What you type.** `--set key=value`, repeated, at most 16, each parameter once. Every parameter is text (a number as written, no quotes needed: `lower=81000`, `spacing=GEOMETRIC`, `stop_loss=percent:5`), exactly as in a plan file; the bot's kind says which keys exist and which values it can read. A Grid's keys are `lower`, `upper`, `grid_count`, `spacing`, `capital_quote`, `stop_loss`, `take_profit` and, on a position venue, `direction` and `leverage` (named together) and `on_range_exit`. A key or a value is 1 to 32, respectively 1 to 64, characters of letters, digits and `_ . : + -` (no spaces or quotes), because the file crosses a trust boundary. The same checks as the Bots tab refuse an **unknown key** or a **value the kind cannot read** (`lower is not a number`, `upper must be above lower`, `grid_count must be at least 1`) in words, exit `2`, **and change nothing**: one bad setting among good ones refuses all of them, and a STOPPED bot stays STOPPED. A set whose values are the bot's own already is refused ("nothing to change"), so a STOPPED bot is not moved to DRAFT for nothing. What needs the exchange (the venue's filters, the account, `on_range_exit=close` on Spot) is still judged by `bot start`.
  - **What you see.** The reply names each change as `key old -> new` (`(unset)` for a parameter the bot did not hold) and says the bot is DRAFT.
  - **Your plan file is not updated, and neither is `state/bot_plan.json`.** `bot apply plan.json` is declarative and the file is yours; the applied record holds a desired state per bot and no parameters, so there is nothing in it to update. **After `bot edit`, change the same value in `plan.json` too: otherwise the next `bot apply` of the old plan sees the bot's parameters differ from the plan, edits them back (an EDIT entry lands the bot on DRAFT again) and the old range returns.** `bot export --bot-id <id> --output new-plan.json` writes the bot as it is now, if you prefer to regenerate the entry.
  - **An older host** reads `edit` as an unknown action and `set` as an unknown key: it audits the command `malformed`, executes nothing and the verb exits `1`; upgrade the host before using it.
  - **It cannot race a start.** The edit runs under the same lock a Start holds while it reads the bots and moves one to STARTING, on the host's command thread like the other verbs: either the Start has moved the bot first (the edit is refused: it is STARTING) or the edit landed first (the Start reads the new parameters). A bot at rest has no worker and so no queue of its own; the write is the one the Bots tab's Save makes.
- **Delete is not a running-host command.** `bot delete` was dropped from `EPIC-038K` by the owner (2026-10-17). A DRAFT or STOPPED bot is still deleted with the host stopped, by `bot apply --prune` (§8); there is no `delete` action word in the command file.
- **To free the symbol for a new run:** `bot stop <id>` until `bot show` says STOPPED, then `bot start <id>` again (after `bot edit <id> --set ...`, the Bots tab, or applying a plan with the host stopped), or stop the host, `bot apply plan.json [--prune]` and start it with `--start-planned` (§8). `bot apply` itself still needs the host stopped.

### The account-level loss cap (`bot loss-cap-ack`)

`EPIC-026L`, decision N3 of the 2026-10-20 review. One figure for the whole host: the most the bots may lose in one UTC day, summed over all of them, realised plus unrealised, in one quote asset. At that figure the host stops **every** bot through the Stop the Bots tab uses, and **no bot starts or resumes** until you acknowledge it. The figure is yours; there is no default, and an unset figure means the cap is **off**.

```bash
# Set it in user_config.json, the file the owner's options live in (src/config/user_config.json of the install), then restart the host
#   { "bots.account_loss_cap": "500 USDT" }      # amount, a space, the quote asset; empty or absent = off
$M preflight --venue spot_mainnet               # the "account-loss-cap" line: set, off (WARN on mainnet), or tripped
$M bot loss-cap-ack                             # after a trip: clear it so bots may start again
$M status                                       # the "loss_cap" section: figure, tripped, why; never the day's loss
```

- **What it counts.** Each bot's own account (`bot list` shows it as its total), read at the price the bot last saved to its file, which is at most 30 s old, every 15 s. It starts counting at 00:00 UTC, or at the first sample after the host (or the bot) was first seen that day; a bot that began a new run keeps what its earlier run lost today. It is **not** your exchange equity, and between the trip and the last bot reaching STOPPED the market goes on.
- **What a trip does.** In this order: it writes `state/loss_cap.json`, asks every bot that is not at rest to stop (a **Spot** bot cancels its orders and **keeps its coin**, so its loss can still move: selling it is your decision; a **Futures** bot cancels its orders and **closes its position at market**), then sends a CRITICAL alert to Discord and logs `[loss-cap] TRIPPED` at CRITICAL. It places no order of its own.
- **What it refuses.** While tripped, `bot start`, `bot resume`, the Bots tab's Start and Resume, `run --start-planned` and `run --resume-recovering` are refused with the cap's sentence. A bot that gets going by a path that does not ask (an automatic recovery) is stopped again by the next sample. A restart, a day roll-over and removing the figure from the config do **not** clear it.
- **Acknowledging.** `bot loss-cap-ack` goes through the same command directory as the other `bot` verbs (exit `10` when no host is running, `5` when this account has no control). It starts nothing: start each bot yourself afterwards. **The day's count is not reset:** it keeps adding up from 00:00 UTC, so the cap trips again at the figure. While today's loss is still at or above the figure the acknowledgement is **refused**, because clearing the trip would only trip it again: raise `bots.account_loss_cap` and restart the host, then acknowledge, or acknowledge after 00:00 UTC (the next UTC day starts from zero). It is also refused when the cap is not tripped.
- **It fails closed.** If the cap cannot tell what the bots have lost for two minutes (the bots cannot be read, a bot file is refused, a running bot has no price yet or trades in another quote asset than the figure's), it **trips** and says why. A `bots.account_loss_cap` that is set and cannot be read stops the host from starting. A record that cannot be written is logged at ERROR and the trip holds in memory; a record that cannot be read at start-up starts the cap tripped.
- **Fix the cause before you acknowledge a `not_judgeable` trip.** A refused bot file, or a running bot in another quote asset than the figure's, trips the cap again two minutes after every acknowledgement until it is gone.
- **On the desktop there is no Acknowledge command yet** (the command directory is served by `run` alone). Stop the app and delete `state/loss_cap.json`: it is the same decision, taken by hand.
- **An older host** reads `loss-cap-ack` as an unknown action: it audits the command `malformed`, executes nothing and the verb exits `1`; upgrade the host before using it.

## 7. What the exit codes mean for you

The full table is [`exit_codes.md`](exit_codes.md). The ones a service meets:

| Code | systemd does | You do |
| :-: | :--- | :--- |
| `0` | nothing (a requested stop, or a second signal) | nothing |
| `1` | restarts after 10 s | read the traceback in the journal; a crash loop is a bug to report with the log **file** |
| `2` | does not restart | a flag in the unit is wrong; `journalctl` names it |
| `3` | does not restart | another copy holds the data root: a second `run`, or the desktop app on the same `SEW_DATA_ROOT`. Stop it |
| `4` | does not restart | a machine check failed: the table in §4 |
| `5` | does not restart | the key: absent, rejected, can withdraw, or `--resume-recovering` / `--resume-halted` without an alert channel; §3 and §4 |
| `6` | restarts after 10 s | the exchange is down or unreachable; it retries until it is back |

After fixing a code `2`–`5` cause, `systemctl reset-failed sew-run && systemctl start sew-run`.

## 8. Upgrade and rollback

The state is the data root's `state/` (the bots' files, the alert outbox, the snapshot). The upgrade **leaves resting orders on the exchange** (the default stop, §0) and nothing watches them while the host is down; do it when that is acceptable. `--on-stop stop-bots` cancels first, but it is a flag of the process being stopped: it only applies if the running host was *started* with it (a drop-in for `ExecStart`).

```bash
# 1. See what is running.
sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python \
    /opt/sew/Sagittarius_Elite_Warrior/src/main.py bot list
# 2. Stop, and read that it drained: "DRAINING -> STOPPED" and "workers closed", exit 0.
sudo systemctl stop sew-run
journalctl -u sew-run -o cat -n 40
# 3. Copy the state aside (the way back). Also take the dated, root-only archive of §8b: sudo sew-backup
sudo cp -a /var/lib/sew/state "/var/lib/sew/state.before-$(date +%F)"
# 4. Upgrade the code and its dependencies.
sudo git -C /opt/sew/Sagittarius_Elite_Warrior fetch --tags
REF='<the release tag or commit>'   # edit this line first
sudo git -C /opt/sew/Sagittarius_Elite_Warrior checkout "$REF"
sudo /opt/sew/venv/bin/pip install -r /opt/sew/Sagittarius_Elite_Warrior/requirements-headless.txt \
    -c /opt/sew/Sagittarius_Elite_Warrior/requirements.lock
sudo /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/scripts/engine_pin.py install
sudo /opt/sew/venv/bin/python -m compileall -q /opt/sew/Sagittarius_Elite_Warrior   # the sew user cannot write bytecode (§2)
# 5. Regenerate the unit if the release changed it, then:
sudo cp /opt/sew/Sagittarius_Elite_Warrior/deploy/linux/sew-run.service /etc/systemd/system/ && sudo systemctl daemon-reload
# 6. Pre-flight (testnet: §4; mainnet: the start does it), start, look.
sudo systemctl start sew-run
sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python \
    /opt/sew/Sagittarius_Elite_Warrior/src/main.py status
```

Read the `[preflight]` lines after the start. **`bot-files-readable` WARN** means a bot file was written by a newer build than this one and its bot is not loaded; `status` and `bot list` list that file with its path and reason (`unknown schema_version 2`). The file is never rewritten. Every bot a restart found RUNNING or PAUSED is now RECOVERING and **stays so until a person resumes it**; one WARNING per bot names it (§0).

**Rollback**: stop, `git checkout` the previous release, reinstall its dependencies (step 4), and put the state back from step 3 **if the newer build has written bot files** (an older build refuses a newer file and leaves it; restoring the copy returns the bots as they were). Start and check as above.

### Which halts a bot recovers from by itself (`bot show`)

`bot show <bot_id>` prints the bot's effective recovery table, one `Recovery` row per halt reason: how long the cause must stay clear before an attempt, how many of the bot's attempts are used inside that rule's window, how long a wait may last before you are told, and which layer decided it. A Futures bot prints `no automatic recovery (futures layer)`. `--json` carries the same rows under `recovery`, and `reason_detail` carries the words the bot wrote beside its reason (where "the automatic recoveries are used up; resume by hand" is said). `bot list` and `status` carry `recovery: null`.

### Plan files and version control (`bot export`, `bot apply`, `run --start-planned`)

A plan is a JSON file (`sew.bot-plan/1`) that names each bot by name and venue and holds **no key, secret or account identifier**, so it is safe to keep in version control and to review as a diff. It is how a server's bots are defined without the desktop app. The desktop app's Bots → Export plan… writes the same file (same query, same never-overwrite writer), so a bot designed there reaches the server with `scp`; it defaults to *All stopped* when a mainnet bot is in scope, so a copied plan starts nothing under `--start-planned` until you change `desired_state` on purpose. The procedure, each step run as in §5 (`M` is the `sudo -u sew env ... main.py` prefix there):

```bash
M="sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py"
$M bot export --all --output /var/lib/sew/plan.json   # once; read-only; never overwrites a file
# edit plan.json (or keep it in git and copy it over), then:
$M bot apply /var/lib/sew/plan.json --dry-run         # prints what would change; changes nothing; works beside a running host
sudo systemctl stop sew-run
$M bot apply /var/lib/sew/plan.json [--prune]         # creates and edits bots (with --prune deletes the ones the plan omits, if at rest); starts and stops nothing
sudo systemctl start sew-run
```

- `bot apply` changes bots, so it needs the data root's lock: with the host running it exits `3` and changes nothing (`bot stop`, `bot pause`, `bot resume`, `bot start` and `bot edit` are the commands that reach a running host, §6; `bot apply --prune` deletes only with the host stopped). A real apply is a **writable boot**, so the restart rule runs first, as at any start: a bot saved as RUNNING or PAUSED becomes RECOVERING in its file (the same state the next `run` would have made it). `--dry-run` boots read-only and changes nothing, which is why it is safe beside a running host. A second apply of the same plan changes nothing. An entry that would edit a bot in a state the lifecycle forbids (it must be stopped first) is reported, not applied, and the command exits `2`; the other entries are applied.
- **A `bot edit` on the running host is not in your plan file.** It changes one stopped bot's parameters while the host runs (§6) and leaves `plan.json` and `state/bot_plan.json` as they were; the next `bot apply` of the old plan edits the bot back to the plan's values. After a `bot edit`, change the same value in `plan.json`.
- `apply` records what the plan wants in **`state/bot_plan.json`** (beside the bots' files, keyed by bot id). **Only that applied record is what the host reads**, never the file you edit, so an edit counts once it has been applied.
- **`run --start-planned`** starts the bots the applied plan says are running and that are at rest. It is not in the unit by default. With no applied plan, or a record that cannot be read, it exits **`5`** before anything boots, which the unit does not restart; so add it to the unit only after a plan has been applied. To add it, use a drop-in (`sudo systemctl edit sew-run`): write `[Service]`, an empty `ExecStart=`, then `ExecStart=` followed by the unit's own line with ` --start-planned` appended.

  `systemctl edit` opens an editor. Its `--stdin` option needs systemd 256 or newer, and Ubuntu 24.04 ships 255, where it answers `unrecognized option '--stdin'`. To do it without an editor, write the drop-in file yourself:

  ```bash
  sudo mkdir -p /etc/systemd/system/sew-run.service.d
  sudo tee /etc/systemd/system/sew-run.service.d/override.conf > /dev/null <<'EOF'
  [Service]
  ExecStart=
  ExecStart=/opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py run --stop-timeout 25 --health-interval 60 --on-stop leave-orders --host-signal sdnotify --start-planned
  EOF
  sudo systemctl daemon-reload
  sudo systemctl reset-failed sew-run
  sudo systemctl restart sew-run
  systemctl cat sew-run | grep -E "LoadCredential|ExecStart"   # the drop-in's lines come last and win
  ```

- A bot on a **mainnet** venue is started only with `--confirm-venue <venue>` in the same line; without it the host exits `2` and starts nothing. One `--confirm-venue` names one venue.
- **`--resume-halted`** (`EPIC-042E`) is a person's Resume and Confirm answered in advance, for every bot that is `HALTED` or `AWAITING_RECOVERY` (no other state): the exchange is read, the order session is opened and the ladder the bot proposes is laid, with the price re-read and its tolerance applied. Read the `[resume-halted]` lines after the start: one INFO per bot resumed, one WARNING per bot that stays as it was, with the reason in the words the Resume gave (a session that would not open, a readiness check, a missing `--confirm-venue`). With both flags the halted bots are resumed first, so only a halt that existed before this start is re-planned, never one the recovering reconcile makes in the same start. Unlike `--resume-recovering`, a mainnet bot whose venue was not typed is **skipped and named**, not a reason to refuse the run. The host refuses (exit `5`) without an alert channel or `--i-accept-silent-failures`, as `--resume-recovering` does. The owner does not read the proposal on a headless host; use the flag for a halt you have judged transient (a bot halted for `price_feed_stale` whose bot-halt alert you read), and keep the Bots tab for any other.

### Bots on more than one venue, and several on one (`EPIC-029J1a`, `EPIC-029J1b`)

Bots run together on different venues (Spot or Futures, mainnet or testnet), and on one venue they run together on **different symbols**, up to **5 active bots per venue** (`MAX_ACTIVE_BOTS_PER_VENUE`, the owner's choice of 2026-10-17; a venue is Spot or Futures, mainnet or testnet, so one mainnet account may run five Spot and five Futures bots). Start, the plan's `--start-planned` and the Bots screen ask the same question, so what the screen lists is what the host is told.

- **`--start-planned`**: planned bots on different symbols of one venue all start, up to the venue's five; planned bots on a testnet and on a confirmed mainnet venue both start. Of two planned bots on the **same symbol** of a venue the lowest bot id starts (the run goes in bot-id order) and the other logs `[start-planned] bot <id> was not started: ONE_ACTIVE_BOT_PER_SYMBOL (A bot on <venue> is still active on <symbol> (<id>); ...)`; a sixth bot of a venue logs `VENUE_FULL`. Each stays at rest. **Mind the start weight:** a Futures Start costs about 300 request weight, so a plan of five bots on one Futures venue spends about 1,500 of the minute's 2,400 in its first minute, and the gate (70 %, 1,680) closes before a sixth; a start the closed gate refuses reads `Not connected: exchange asked for a pause` and succeeds on a later run. Idle, each Futures bot costs about 175 weight a minute.
- **A restart with bots waiting to recover blocks new starts on their venue.** `--start-planned` after a restart logs `[start-planned] bot <id> was not started: VENUE_RECOVERING (...)` for every planned bot of a venue that has a `RECOVERING` bot: a Start stays refused while a bot of the venue waits (`EPIC-029J1b`), so that the owner resumes the waiting bots deliberately first. Run `--resume-recovering` first (or stop those bots), then start the rest. `--resume-halted` and a stop through the command directory also open the session, but they open it for the bot they act on (`BOT-183`): the `RECOVERING` bots of that venue keep waiting for their own resume. A `bot start` on the running host is refused for the same reason (`VENUE_RECOVERING`), and on a mainnet venue its refusal for a missing `--confirm-venue` names those bots.
- **`--confirm-venue` names one venue per run.** Real-money bots on **two mainnet venues** cannot all be started or resumed by one run: `--start-planned` and `--resume-recovering` judge every wanted real-money bot before anything boots and exit `2` while any is on an unconfirmed venue, naming `--confirm-venue <first venue>` and "one mainnet venue per run". `--resume-halted` skips and names the unconfirmed venue's bots instead (WARNING per bot) and resumes the confirmed venue's. To bring both venues' bots back, keep the other venue's bots out of the run (stopped, or not in the plan) or start them from the Bots tab of the desktop app on the same data root. The owner decided (2026-10-17) to keep one venue per run for now; confirming several is a separate, later task.
- **Emergency Stop and a rate limit act on one venue.** An Emergency Stop halts **every** bot of the venue it was given and none on the other. A rate limit (or the used weight reaching 70 % of the minute's) closes **that venue's** requests, for every caller, until the exchange's pause or the minute ends. Each bot that then needs an order halts `RATE_LIMITED` and resumes by itself at the pause's end (all of them at the same instant); a bot that only reads says so in the log and keeps its ladder; the other venue is unaffected. The venue's orders are also paced together (one 250 ms pacer per venue), so a ladder of 20 orders takes about 5 s and a neighbour's orders queue behind it. Only orders that build a ladder or open a position wait in that queue; a protective stop, a reduce-only close and a Spot exit never do.
- **A refused bot file counts as active on every venue** (its venue is unknown): `status` and `bot list` name it, and no Start passes until it is dealt with.

## 8b. Back up and restore the state

`EPIC-026` must-have 8. Without `state/bots/` the exchange still holds the orders and positions the bots tagged, and no bot manages them. The data root is `/var/lib/sew` (`SEW_DATA_ROOT`, §1). Linux first; the Windows lines are at the end and not run.

**What is in it, and what goes into the archive** (the paths are those the code writes, `core/repo_root.py` → `data_root`):

| Path under the data root | Holds | In the archive |
| :--- | :--- | :-: |
| `state/bots/<bot id>.json` | every bot: parameters, state, run record, client order ids (`modules/bots/adapters/persistence/json_bot_store.py` → `JsonBotStore`, atomic write) | yes |
| `state/bot_plan.json` | what `bot apply` recorded; `--start-planned` reads only this (`modules/bots/composition/state_bindings.py` → `_build_applied_plan_store`) | yes |
| `state/loss_cap.json` | the account loss cap's trip record and day stamp (`modules/bots/composition/loss_cap_bindings.py` → `loss_cap_record_path`) | yes |
| `state/trading/owner_inventory/`, `state/trading/owner_position/` | the budget checkpoints the bots' inventory is derived from (`modules/trading/composition/adapter_bindings.py`) | yes |
| `state/alert_settings.json` | what you set per bot for alerts (`modules/alerting/composition/alerting_bindings.py` → `alert_settings_path`) | yes |
| `plan.json` (if you made one, §8) | your plan file | yes |
| `state/alerts.sqlite3` and its `-wal`, `-shm` | the alert outbox (`outbox_path`): queued alerts, stale by the time of a restore | no |
| `state/health.json`, `state/instance.lock`, `state/control/` | the live snapshot, the single-instance lock, the command files (`modules/operations/module.py`, `shell/composition_root.py` → `instance_lock_file`, `adapters/control_directory.py`): all rewritten by the next start | no |
| `database/`, `logs/` | the market-data cache, refetched from the exchange (`database_directory`); the CLI logs (§10); the journal is the host's log | no |

The archive also carries three things outside the data root that you edited by hand: the unit's drop-in directory `/etc/systemd/system/sew-run.service.d` (for example `--start-planned`, §8), and `src/config/user_config.json` of the checkout (the `bots.account_loss_cap` figure, §6).

**Secrets stay out of it.** `/etc/sew/sew.env` and `/etc/sew/credentials/` are not archived, on purpose. A key restored onto a new VPS is bound to the old address and would be rejected, so a new server gets a new key from the exchange in any case (§3c); an archive without keys can sit in a cloud drive or an e-mail account without being a second place to leak from. Keep the webhook URL and the check-in URL in your password manager (they can also be recreated, §3c). A provider snapshot of the whole disk does hold `/etc/sew`: treat it as a secret.

**A consistent copy.** The safe copy is taken with the host **stopped**: every file is at rest, and the stop leaves the orders on the exchange (§0). A **hot copy**, with the host running, is also usable and is what the timer below takes: every file the host writes into the archive is written as a temporary file and renamed over the old one (the stores named above), so a copy never holds half a file; but two bot files may be seconds apart, and the archive is as old as its newest write. That is the state a crash leaves, and a restore comes back RECOVERING for the same reason (below). Take the stopped copy before the first real-money run, before an upgrade (§8) and before any `bot apply --prune`.

**Install the script once** (a dated archive, mode `0600` in a `0700` root-only directory, written under a temporary name and renamed when it is whole and passes `gzip --test`; it keeps the last 30 days and prints the number of bot files it archived):

```bash
sudo tee /usr/local/sbin/sew-backup > /dev/null <<'EOF'
#!/usr/bin/env bash
# sew-backup - a dated, root-only archive of the host's state (runbook section 8b). Run as root.
set -euo pipefail
umask 077
ROOT=${SEW_BACKUP_ROOT:-/}
DEST=${SEW_BACKUP_DIR:-/var/backups/sew}
KEEP_DAYS=${SEW_BACKUP_KEEP_DAYS:-30}

[ "$(id -u)" = 0 ] || { echo "sew-backup: run this as root (sudo sew-backup)" >&2; exit 2; }
[ -d "$ROOT/var/lib/sew/state" ] || { echo "sew-backup: $ROOT/var/lib/sew/state does not exist" >&2; exit 2; }
if systemctl is-active --quiet sew-run 2>/dev/null; then
  echo "sew-backup: the host is running; this is a hot copy (runbook section 8b)" >&2
fi

install -d -o root -g root -m 0700 "$DEST"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
FINAL="$DEST/sew-state-$STAMP.tar.gz"
PARTIAL="$DEST/.sew-state-$STAMP.partial"

MEMBERS=(var/lib/sew/state)
for p in var/lib/sew/plan.json etc/systemd/system/sew-run.service.d \
         opt/sew/Sagittarius_Elite_Warrior/src/config/user_config.json; do
  [ -e "$ROOT/$p" ] && MEMBERS+=("$p")
done

# Exit 1 from tar is "a file changed while it was read": a warning for a hot copy, not a failure.
rc=0
tar --create --gzip --file "$PARTIAL" --directory "$ROOT" \
  --exclude='*.tmp' --exclude='var/lib/sew/state/alerts.sqlite3*' \
  --exclude='var/lib/sew/state/health.json*' --exclude='var/lib/sew/state/instance.lock' \
  --exclude='var/lib/sew/state/control' "${MEMBERS[@]}" || rc=$?
if [ "$rc" -gt 1 ]; then rm -f -- "$PARTIAL"; echo "sew-backup: tar failed (exit $rc)" >&2; exit 1; fi

gzip --test "$PARTIAL"
mv -f -- "$PARTIAL" "$FINAL"
echo "sew-backup: wrote $FINAL ($(du -h "$FINAL" | cut -f1)), $(tar -tzf "$FINAL" | grep -c 'state/bots/[^/]*\.json$') bot file(s)"
find "$DEST" -maxdepth 1 -name 'sew-state-*.tar.gz' -mtime +"$KEEP_DAYS" -delete
EOF
sudo chmod 0750 /usr/local/sbin/sew-backup
```

**Take a backup** (the stopped copy; leave out the `stop` and `start` lines for a hot copy). Compare the bot-file count it prints with the number of rows of `bot list`:

```bash
sudo systemctl stop sew-run
sudo sew-backup
sudo systemctl start sew-run
sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python \
    /opt/sew/Sagittarius_Elite_Warrior/src/main.py bot list
```

**Keep a copy off the VPS.** An archive on the disk that failed is not a backup. Pull it from your own machine, so the server holds no credential to the backup store. The archive is root-only, so first hand the newest one to your login account for the length of the copy (`you@vps` is the account you log in with and may `sudo`):

```bash
sudo ls -t /var/backups/sew                       # newest first
NAME=sew-state-YYYYMMDDTHHMMSSZ.tar.gz            # edit this line first
sudo install -m 0600 -o "$USER" -g "$USER" "/var/backups/sew/$NAME" "$HOME/$NAME"
```

Then, on your own machine, fetch it, test it and remove the temporary copy on the VPS:

```bash
mkdir -p ~/sew-backups && chmod 0700 ~/sew-backups
NAME=sew-state-YYYYMMDDTHHMMSSZ.tar.gz            # the same name
scp you@vps:"$NAME" ~/sew-backups/ && gzip --test ~/sew-backups/"$NAME" && ssh you@vps "rm -f $NAME"
ls -l ~/sew-backups
```

The archive holds your bots' parameters and order ids, not a key: keep it somewhere only you read, and encrypted if it goes to a shared drive (`gpg --symmetric <file>`).

**How often.** Once before the first real-money run (checklist row 13); before every upgrade and every `bot apply` or `bot edit` (they change the files); and daily, which the timer does for the hot copy. The pull from your machine is the part that must also happen after a change you care about: a daily pull from `cron` or Task Scheduler there is enough.

```bash
sudo tee /etc/systemd/system/sew-backup.service > /dev/null <<'EOF'
[Unit]
Description=Back up the sew-run state (runbook section 8b)

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/sew-backup
EOF
sudo tee /etc/systemd/system/sew-backup.timer > /dev/null <<'EOF'
[Unit]
Description=Daily sew-run state backup

[Timer]
OnCalendar=*-*-* 03:17:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now sew-backup.timer
systemctl list-timers sew-backup.timer --no-pager
```

### Restore

Onto **the same VPS** (a bad edit, a wrong `--prune`, a damaged file) or onto **a new one**. Order matters:

1. **A new VPS first needs §2** (the account, the directories, the checkout at the release that wrote the archive or a newer one: an older build refuses a newer bot file, §8), the keys of §3 (a **new** key bound to the new address, `sudo sew-key add`; no file for a venue or alert you do not use: a file never created is a secret not set, §3), and the unit. Do not start the service yet. Copy the archive onto the new server into `/var/backups/sew` (mode `0600` root).
2. **Make sure no other host runs on the same exchange account.** The old VPS must be stopped (`sudo systemctl disable --now sew-run` there) or destroyed before a bot is resumed here. Two hosts acting on the same tagged orders would fight over them.
3. **Restore.** The current state is moved aside, never deleted. Ownership and modes are set afterwards, because a new VPS may give the `sew` account another numeric id:

```bash
ARCHIVE=/var/backups/sew/sew-state-YYYYMMDDTHHMMSSZ.tar.gz   # edit this line first
sudo systemctl stop sew-run || true
sudo gzip --test "$ARCHIVE" && sudo tar --list --gzip --file "$ARCHIVE" | grep 'state/bots/[^/]*\.json$'
[ -e /var/lib/sew/state ] && sudo mv /var/lib/sew/state "/var/lib/sew/state.replaced-$(date -u +%Y%m%dT%H%M%SZ)"
sudo tar --extract --gzip --file "$ARCHIVE" --directory / --no-same-owner var/lib/sew
if sudo tar --list --gzip --file "$ARCHIVE" | grep -q '^etc/systemd/system/sew-run.service.d/'; then
  sudo tar --extract --gzip --file "$ARCHIVE" --directory / --no-same-owner etc/systemd/system/sew-run.service.d
  sudo systemctl daemon-reload
fi
sudo chown -R sew:sew /var/lib/sew
sudo chmod -R u+rwX,go-rwx /var/lib/sew
# The edited config is not copied over the checkout (a release may have added keys): compare, then edit by hand.
sudo tar --extract --gzip --file "$ARCHIVE" --to-stdout opt/sew/Sagittarius_Elite_Warrior/src/config/user_config.json \
  | diff - /opt/sew/Sagittarius_Elite_Warrior/src/config/user_config.json
```

4. **Start, and check.** The start runs the pre-flight (§4) and restores the bots from the files:

```bash
sudo systemctl start sew-run
journalctl -u sew-run -o cat --since "5 minutes ago" | grep -E '\[preflight\]|bot-files-readable|\[recovering\]|\[loss-cap\]'
M="sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py"
$M bot list                    # the same bot ids and names as before; every bot that was running reads RECOVERING
$M status                      # exit 0; the "loss_cap" section shows the figure and whether it is tripped
$M bot order 44wa1x            # an id from bot list: the orders the restored file records, to compare with the exchange
```

   The restored bots are as old as the archive. Fills, stops and starts since then are not in the files; `bot order` is what the **file** believes, the exchange is the truth. Compare the open orders at the exchange with each bot before you resume it. A `loss_cap.json` restored from a tripped moment is tripped (no bot starts until `bot loss-cap-ack`, §6); one from an earlier UTC day counts again from zero today.
5. **Resume each bot yourself** (§6): `$M bot resume <bot id>`, with `--confirm-venue <venue>` on mainnet, or restart once with `--resume-recovering`. A bot never resumes by itself after a restore.
6. **Check the dead man's switch and the alert channel** (§3b step 3, §5 `alert test`), which a new VPS has stored fresh.

**A lost state with no usable archive.** The orders and positions of the bots are still on the exchange, tagged, and nothing adopts them. Look at the open orders and positions in the exchange's own app, cancel the orders and close the positions you do not want, and rebuild the bots from your plan file (`bot apply`, §8) or the Bots tab. This is the case the archive exists to avoid.

**Windows** (not run on a machine, like §9). The state is `C:\ProgramData\sew\state` and the same table applies. From an elevated PowerShell, with the folder `C:\ProgramData\sew-backup` open to Administrators only:

```powershell
nssm stop sew-run
Compress-Archive -Path C:\ProgramData\sew\state -DestinationPath "C:\ProgramData\sew-backup\sew-state-$(Get-Date -Format 'yyyyMMdd-HHmmss').zip"
nssm start sew-run
```

Restore is the reverse: stop the service, move `state` aside, `Expand-Archive` into `C:\ProgramData\sew`, give the service account modify on the folder again (§9), start, and resume the bots. Copy the archive off the machine as above.

## 9. Install on Windows (NSSM)

*Not run on a Windows machine by its author; §11 is how it is proven.* Decision O5: NSSM is documented as an external tool, Task Scheduler as the stated fallback; neither is a dependency of the app.

1. Python 3.12+, `git`, then the same three steps as §2 with Windows paths: clone to `C:\sew\Sagittarius_Elite_Warrior` (the directory name is required), `python -m venv C:\sew\venv`, `C:\sew\venv\Scripts\pip install -r requirements-headless.txt -c requirements.lock`, then `scripts\engine_pin.py install`.
2. Download NSSM from <https://nssm.cc> to a folder you control (for example `C:\tools\nssm.exe`). Check the download against the publisher's page; the install runs it as an Administrator.
3. From an elevated PowerShell:

```powershell
.\deploy\windows\nssm-install.ps1 -Nssm C:\tools\nssm.exe -Python C:\sew\venv\Scripts\python.exe `
    -Checkout C:\sew\Sagittarius_Elite_Warrior -DataRoot C:\ProgramData\sew
```

The script ([`deploy/windows/nssm-install.ps1`](../../deploy/windows/nssm-install.ps1), generated by the same `render_service_files.py`) is idempotent: every setting is a `nssm set`, so running it again changes nothing. It sets:

- `AppExit Default Restart` and `AppExit 0|2|3|4|5 Exit`: NSSM restarts on every status unless told otherwise, so it ends the service on a clean exit `0` (as the unit's `Restart=on-failure` does) and on the unit's `RestartPreventExitStatus` codes, with `AppRestartDelay 10000`.
- **`AppStopMethodConsole 62000`**: NSSM stops a console program by sending **Ctrl-C first**, which the host handles as `SIGINT` (a drain, then exit 0), and waits this long before it tries `WM_CLOSE` and then `TerminateProcess`. NSSM's default wait is 1500 ms, far below the host's 57 s worst case, which would kill a drain in progress. The figure is the unit's `TimeoutStopSec` in milliseconds.
- `AppStdout`/`AppStderr` to `service-logs\sew-run.log` with `AppRotateFiles 1`, `AppRotateOnline 1`, `AppRotateBytes 10485760`: the log is rotated by the wrapper; the app sets no `log.file`.
- `AppEnvironmentExtra` with `PYTHONPATH` and `SEW_DATA_ROOT`; the service account `NT SERVICE\sew-run` (a virtual account, no password), granted modify on the data root and nothing else.

**Keys on Windows.** There is no `LoadCredential`. For a **mainnet** venue use the permission-checked file store (decision O3's fallback): a directory outside the checkout whose ACL grants only the service account, SYSTEM and Administrators, named by `SEW_SECRET_FILES_DIR`, one file per secret (`futures_mainnet_api_key`, `futures_mainnet_api_secret`, and the spot pair). The store refuses a file anyone else can reach and prints the `icacls` command that fixes it. Whether the Windows Credential Manager works for a service account is **unanswered** (`EPIC-038E`); do not rely on it.

```powershell
$dir = 'C:\ProgramData\sew\secrets'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
icacls $dir /inheritance:r /grant 'NT SERVICE\sew-run:(OI)(CI)R' 'SYSTEM:(OI)(CI)F' 'Administrators:(OI)(CI)F'
$secret = Read-Host -AsSecureString 'futures mainnet key'
$plain = [System.Net.NetworkCredential]::new('', $secret).Password
[System.IO.File]::WriteAllText("$dir\futures_mainnet_api_key", $plain, [System.Text.UTF8Encoding]::new($false))
```

Then install (or re-run the install script) with `-SecretFilesDir C:\ProgramData\sew\secrets`, which sets `SEW_SECRET_FILES_DIR` for the service.

A **testnet** key goes in the service's environment: `nssm set sew-run AppEnvironmentExtra "+BINANCE_FUTURES_TESTNET_API_KEY=<key>"` (the `+` appends). NSSM keeps that in the registry, readable by Administrators: acceptable for a testnet key, not for a mainnet one. **Running the install script again replaces the whole environment list**, so append the testnet variables again afterwards.

**Reboot.** Windows gives a service a limited time to stop at shutdown (`WaitToKillServiceTimeout`, 5 s by default for the system), shorter than a drain. A host that was killed at a reboot has not written `STOPPED`; the next start reads each bot as RECOVERING, as after a crash. The checklist records what a reboot does on your server.

**Task Scheduler (the fallback).** Use it only if NSSM is unacceptable. Per the research this decision rests on (R10, not run here): its restart settings are coarse (a fixed count and interval, no way to say which exit codes not to restart on, so a configuration fault would loop), and it has no setting that sends Ctrl-C first, so a stop ends the process outright and no drain runs. It can start a task at boot with highest privileges and "run whether the user is logged on or not"; everything else in §6–§8 is the same.

## 10. Logs

The host writes to standard output only. systemd's journal captures and bounds it (`SystemMaxUse=` in `journald.conf`, `journalctl --vacuum-time=14d`); NSSM rotates what it captures. If you set `log.file` anyway it grows without bound until the Engine gains rotation (decision O7); [`LOGGING.md`](LOGGING.md) §2 has the `logrotate` stanza and says why `copytruncate` is required. Do not restate it here.

**Commands that only read, and short-lived commands that write, keep their log off the console** (`BOT-185`, `BOT-186`). `status`, `bot list`, `bot show`, `plan`, `alert test`, `preflight`, `exchange-status` and the other commands that open a read-only copy, and the short-lived writer `bot apply`, print their result and nothing else (the `bot apply` table and any `--confirm-venue` refusal are still on the console): the 60-odd INFO lines of the boot go to `<data root>/logs/cli-<UTC timestamp>-<pid>.log`, one file per command run (`/var/lib/sew/logs/` on Linux, `C:\ProgramData\sew\logs\` on Windows), the newest 40 kept, each capped at 512 KiB (20 MiB at most). A WARNING or ERROR still appears on the console, on stderr, so a failed command is never silent, and a `--json` document on stdout is untouched. To read the log of the run you just made, `ls -t <data root>/logs/cli-*.log | head -1`; for the whole picture add `--verbose`, which puts every record on the console as it was before (`main.py bot list --verbose`, anywhere on the line). `run`, `sync`, `stream` and `trade-once` are not affected: a `keeps_console_log` command's log stays on standard output, which the supervisor above rotates (or is its progress). The design and its trade-offs: [`LOGGING.md`](LOGGING.md) §1b.

**Reading it coloured or filtered** is `main.py logs`, a pipe from `journalctl` or a `--file` (`BOT-199`, [`LOGGING.md`](LOGGING.md) §8); it changes no stored byte.

## 11. The checklist the owner signs

Testnet only. Two machines: a fresh Linux VPS and a fresh Windows server. **Not run yet**; each row is filled in with the date, the result and the log line that proves it, and signed.

| # | Do | Pass when | Linux | Windows |
| :-: | :--- | :--- | :-: | :-: |
| 1 | Install per §2 / §9, provision the testnet keys, start | `status` exits 0; the journal shows `BOOTING -> SERVING` and a `[health]` line | ☐ | ☐ |
| 2 | `kill -9` the process (Windows: end the task in Task Manager) | the service restarts within ~15 s; bots that were running are RECOVERING and named in a WARNING each; `[health]` lines resume; the alert for the crash is the one `EPIC-036` defines (until it merges, none) | ☐ | ☐ |
| 3 | Reboot the machine | the service is running again without a login; record whether `STOPPED` was written | ☐ | ☐ |
| 4 | `systemctl stop` / `nssm stop` while a bot is RUNNING | the log shows `DRAINING -> STOPPED` and `workers closed`; the stop took less than `TimeoutStopSec`; exit 0; orders are still on the testnet exchange | ☐ | ☐ |
| 5 | While the service runs, start a second service on the same data root (Linux: a copy of the unit named `sew-run2`; Windows: a second NSSM service) | the second exits `3` and its supervisor does **not** restart it (`systemctl status` shows `failed`, one start only; NSSM shows it stopped); the first is unaffected; remove the second | ☐ | ☐ |
| 6 | Set the clock 2 s ahead, start | the pre-flight fails `clock-skew` (exit 4) and the unit is not restarted; fix the clock and `reset-failed` | ☐ | ☐ |
| 7 | Fill the data volume below 100 MiB (a throwaway file) and start | `disk-space` is reported FAIL with its remedy (exit 4); remove the file | ☐ | ☐ |
| 8 | Remove the testnet key and start | exit 5 (`credentials-present`), not restarted | ☐ | ☐ |
| 9 | Put a bot file with `"schema_version": 99` in `state/bots/` and start | the `bot-files-readable` WARN names it; `bot list` lists it; the file is byte-for-byte unchanged | ☐ | ☐ |
| 10 | Upgrade per §8 to the next commit and back (rollback) | the bots return as RECOVERING; the state copy restores them | ☐ | ☐ |
| 11 | Set `log.file` to `/var/log/sew/sew.log` (Linux), install the `logrotate` stanza of [`LOGGING.md`](LOGGING.md) §2, run `logrotate -f` | the file rotates, the app keeps writing to it, nothing is lost beyond the documented `copytruncate` window; then remove `log.file` | ☐ | n/a |
| 12 | With the check green (§3b), `systemctl stop` the host and wait the period plus the grace | the monitor alerts you within about 15 minutes; after the start the check recovers | ☐ | ☐ |
| 13 | **One backup taken before the first real-money run** (§8b): the stopped copy, then the pull to your own machine | `sew-backup` printed a bot-file count equal to the rows of `bot list`; `gzip --test` passes on your machine's copy; the date and the file name are written here: ____________ | ☐ | ☐ |

Signed: ____________________ date: ____________ machine: ____________________

## 12. What is proven mechanically, and what is not

Guards in the test suite (`tests/unit/scripts/test_service_files.py`, `test_nssm_install_script.py`, `test_headless_runbook.py`, `test_runbook_shell_snippets.py`): the unit and the NSSM script equal their generator; `RestartPreventExitStatus` equals the exit-code table's non-restarting codes; `TimeoutStopSec` and `AppStopMethodConsole` exceed `--stop-timeout` + the host's grace and snapshot constants; the unit's arguments are accepted by the real command-line parser; no `log.file`, `--dev` or `--debug`; the unit has one `LoadCredential=` line, for the credentials directory, and none that names a file a missing file could break; every credential name is found under the name systemd gives its file, and the same directory is the one `sew-key` writes; the hardening leaves the data root and the notify socket open; `systemd-analyze verify` accepts the unit; the NSSM script parses as PowerShell and, run against a stand-in `nssm`, issues the settings above and installs nothing the second time; this runbook names those figures and every pre-flight check; every bash block in it parses and the key-provisioning step is run for real with a placeholder value. The `sew-backup` script of §8b was run for real by its author against a stand-in root and the restore block against a stand-in `/var/lib/sew`; neither is a test in the suite, and neither has run on a VPS under a real systemd. On the CI runner a missing `pwsh`, `systemd-analyze` or `bash` fails these tests rather than skipping them.

**Not proven**: `alert test` through `systemd-run` and a message reaching a real Discord channel (the owner's run, recorded in `EPIC-036G`), the unit under a running systemd (no systemd was PID 1 where it was written; in particular that systemd 255 loads `/etc/sew/credentials` as `sew_<file>` and starts with a file absent is read from `systemd.exec(5)` and the 251 release notes, and is proven by step 3 of the §3 upgrade note on the first server that runs it), the NSSM script on Windows, the reboot and `kill -9` rows above, and the Windows Credential Manager. The checklist is how they get proven.

## 13. Containers

`--host-signal sdnotify` does not work inside Docker unless the host's notify socket is mounted into the container, and systemd credentials do not exist there. A Dockerfile is out of scope for this epic; if you run the app in a container, run `main.py run` without `--host-signal`, supply keys through the container runtime's secrets as environment variables, and let the container runtime restart it with the same policy: do not restart on exit codes `2`–`5`.
