# RESEARCH — What real users and operators report about headless and VPS trading bots

**Epic:** [EPIC-038](README.md)
**Date:** 2026-10-09
**Collected by:** the session that scaffolded this epic. Every link below was **opened** (fetched and read) in that session, not only seen in a search listing; what a page did not say is stated as "not covered". Used by [`DESIGN_2026-10-09_headless_operation.md`](DESIGN_2026-10-09_headless_operation.md).

> **Caveat.** Most sources are vendor documentation, a vendor blog, or single issue threads. A lesson is evidence that a failure *happened to someone*, not a measured rate. A line marked **(general knowledge)** is the author's own, not from a source, and the implementing task verifies it. Section 17 lists what searches did not find, so no later session searches for it blindly again.

## 1. A restart policy is not a health check: the process lives while the bot is dead
- A VPS vendor's guide lists the usual causes of a bot that stops while the server stays up: an unhandled exception, "a websocket that never reconnects", and the kernel's out-of-memory killer. `systemctl status` can read *running* while the bot sits in a retry loop. Its fix is a heartbeat sent **after a real work step** (a market-data read), with the expected interval about twice the loop time, to a monitor on **another machine** ("a monitor that dies with the thing it watches reports nothing").
- It also says `StartLimitIntervalSec=0` is the setting people forget: without it systemd stops restarting after a few quick failures and the unit stays `failed`; `systemctl show … -p NRestarts` reveals a bot that crashes and recovers all night.
- **Meaning here:** the `run` host needs a *progress*-based health line (last tick seen, last user-stream event, bots by state), not an uptime line; the unit file sets a restart delay and no start limit; the dead man's switch (`EPIC-036E`, N7) is how an absent owner learns the host itself is gone. → [038D](incomplete/EPIC-038D_run_host.md), [038H](incomplete/EPIC-038H_service_units_and_runbook.md)
- Source (vendor guide): https://www.ssdnodes.com/learn/vps-for-trading-bots

## 2. Freqtrade ships systemd watchdog support, and says it does not work in Docker
- `internals.sd_notify` (or `--sd-notify`) makes the bot send keep-alive pings and its state (Running, Paused, Stopped); the page ships a sample unit with the watchdog. Warning on the page: sd_notify does not work inside a Docker container.
- **Meaning here:** a pluggable `IHostSignal` (sd_notify is one adapter, off by default, Linux-only) is a cheap extension; it is optional, because a container deployment cannot use it. → [038D](incomplete/EPIC-038D_run_host.md)
- Source: https://www.freqtrade.io/en/stable/advanced-setup/

## 3. Stopping: what happens to resting orders differs by tool, and users are surprised by both
- **Freqtrade:** `cancel_open_orders_on_exit` defaults to `false`; when `true`, open orders are cancelled on `/stop`, on Ctrl+C, and "if the bot dies unexpectedly" (the page says so; how a dead process can do that is not explained). Open positions are unaffected either way. `/pause` and `/stopbuy` stop new entries and let open trades run under their rules; the pause signal "is not persisted anyway, so restarting the bot will cause this to reset".
- **Hummingbot:** the `exit` command cancels all outstanding orders; closing the window of the binary install "will leave your active orders open in the exchange". The page does not say what `exit -f`, a double Ctrl+C, or a container stop does to orders.
- **Gainium (hosted bots):** a user edited settings, restarted the bot, and the orders of their existing deals closed and did not reopen (second time in a month); staff blamed an exchange-side restriction. A weak, single anecdote, kept because it is the failure this app's `RECOVERING` state exists for.
- **Meaning here:** the answer must be a **named, logged, owner-chosen policy**, not a side effect of how the process ended. The app's GUI today leaves orders resting and says so when closing (`running_bots_objection.py`); a crash cannot cancel anything, so the restart path has to cope with resting orders *whatever* the stop policy is. Pending owner decision O1. → [038D](incomplete/EPIC-038D_run_host.md), [DECISION](DECISION_2026-10-09_headless_operation.md)
- Sources: https://www.freqtrade.io/en/stable/configuration/ · https://www.freqtrade.io/en/stable/rest-api/ · https://www.freqtrade.io/en/stable/telegram-usage/ · https://hummingbot.org/client/launch-exit/ · https://community.gainium.io/t/bot-not-opening-orders-for-existing-deals-on-bot-restart/1303

## 4. Secrets on a headless Linux box: the keyring wants a D-Bus session nobody has
- The `keyring` project's own documentation says its Secret Service backend needs no X11 but **does** need D-Bus: install the GNOME Keyring daemon, start a D-Bus session (`dbus-run-session`), run `gnome-keyring-daemon --unlock` (it reads the password from stdin), and run the application **in that same session**; in a container the page says to use `--privileged`. File-based alternatives are third-party opt-ins (`keyrings.alt`, "possibly-insecure"; `keyrings.cryptfile`, "encrypted text file storage"). The page documents disabling keyring with the null backend through `PYTHON_KEYRING_BACKEND`.
- The vendor guide's advice for a bot key: no withdrawal permission, bind it to the server IP, keep it out of the code directory in a root-owned env file mode 640 read through systemd `EnvironmentFile`, run as a dedicated no-login account. "A leaked exchange key is worse than a leaked SSH key."
- systemd's own documentation: `LoadCredential=` / `LoadCredentialEncrypted=` put each secret in a file under `$CREDENTIALS_DIRECTORY`; "unlike environment variables the credential data is not propagated down the process tree"; the kernel checks access on each read, and only the service's user can read it. Freqtrade reads secrets from `FREQTRADE__…` environment variables and recommends a second config file for secrets.
- **Meaning here:** `KeyringSecretStore` already degrades correctly (reads give "nothing stored", INFO once — `keyring_secret_store.py`), and the env provider already wins first (`env_first_credentials_provider.py`), so *reading* works headless today; what is missing is a **supported, documented way to put the secret there** that is better than a shell `export`. systemd credentials and a permission-checked file are two adapters behind `ISecretStore`. Pending owner decision O3. → [038E](incomplete/EPIC-038E_headless_secret_backends.md)
- Sources: https://keyring.readthedocs.io/en/latest/ · https://systemd.io/CREDENTIALS/ · https://www.ssdnodes.com/learn/vps-for-trading-bots · https://www.freqtrade.io/en/stable/configuration/

## 5. Clock drift, NTP and Binance `-1021`
- Binance: a signed request is accepted only if `timestamp < serverTime + 1000 ms` and `serverTime − timestamp ≤ recvWindow`; `recvWindow` defaults to 5000 ms, cannot exceed 60000, and Binance recommends 5000 or less. python-binance's FAQ names the same two causes and says to make sure the system clock is in sync.
- The vendor guide: set the server to UTC, prefer `chrony` over `systemd-timesyncd`, check `chronyc tracking`. A Freqtrade maintainer, answering a user on WSL whose websocket kept falling back to REST, suggested clock drift in WSL and explicit time sync inside it. **(general knowledge)** raising `recvWindow` hides drift rather than fixing it; a firewall that blocks outbound UDP 123 is a common reason a VPS has no time sync.
- **Meaning here:** the app already measures the skew (`server_time_skew_ms` in `ConnectionStatus`, printed by `exchange-status`, with a `CLOCK_SKEW` failure kind). The preflight command reuses it, with a threshold, and `run` re-checks it periodically and puts the number on the health line, so drift is seen *before* the first rejected order. → [038F](incomplete/EPIC-038F_preflight_command.md)
- Sources: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/general-api-information · https://python-binance.readthedocs.io/en/latest/faqs.html · https://www.ssdnodes.com/learn/vps-for-trading-bots · https://github.com/freqtrade/freqtrade/issues/10597

## 6. IP restrictions on a VPS and `-2015`
- Binance limits are **per IP address, not per key**; 429 means back off, continuing earns a 418 IP ban lasting 2 minutes up to 3 days, with `Retry-After` on both (Binance REST general information).
- A Make.com user enabled "Restrict access to trusted IPs only", added the documented IPs, got `Invalid API-key, IP, or permissions for action` anyway, and a fresh key did not help; the thread has no recorded resolution. The error text names three causes in one message (key, IP, permissions), so it cannot tell the owner which.
- **(general knowledge)** the address Binance sees is the VPS's *outbound* address, which can differ from the one in the provider's panel; a dual-stack host may go out over IPv6 while only IPv4 is whitelisted; a container or proxy changes the source address.
- **Meaning here:** the preflight prints the address the exchange sees, over the family the client actually uses, beside the key's reported permissions, and maps `-2015` to a checklist rather than a bare code. It never needs a withdrawal permission and reports if the key has one. → [038F](incomplete/EPIC-038F_preflight_command.md)
- Sources: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/general-api-information · https://community.make.com/t/connecting-make-with-binance-via-api-ip-restrictions-don-t-work-makes-ip-do-not-solve-my-issue/8048

## 7. Websockets: forced closes every day, silent deaths, and a fallback that does not heal
- Binance's WebSocket API page: a connection is valid for 24 hours ("expect to be disconnected"); the server pings every 20 s and drops a connection with no pong within a minute; a `serverShutdown` event is sent before the server shuts down; limit of 300 connections per attempt every 5 minutes per IP; after a 5xx the outcome of a request is unknown and must be queried.
- Freqtrade issue #11821: a user saw streams break at about 24 h and the bot stay on REST until restarted. The maintainer: all websockets are force-closed "at around midnight (a little after)"; some exchanges do not close but **silently die**, still looking open with no updates. Issue #10597: "Failed to reuse watch" every minute after a 10-second nightly ISP outage until a restart; the maintainer asked for logs and advised a VPS for a live bot; the thread was closed, and a later reporter on WSL saw it without any outage.
- **Meaning here:** this app already has `UserStreamWatch` and a staleness rule on the price feed (`EPIC-035`); headless adds no new reconnect logic. What `run` adds is **evidence**: the health line carries the age of the last user-stream event and the last price per symbol, and a stale feed is a CRITICAL alert (`EPIC-036B`). A test with the fake exchange kills a stream at the 24 h boundary. → [038D](incomplete/EPIC-038D_run_host.md), [038C](incomplete/EPIC-038C_bot_status_read_model.md)
- Sources: https://developers.binance.com/docs/binance-spot-api-docs/websocket-api/general-api-information · https://github.com/freqtrade/freqtrade/issues/11821 · https://github.com/freqtrade/freqtrade/issues/10597

## 8. A network problem becomes a memory problem, and the OOM killer takes the biggest process
- Freqtrade issue #10933 (Debian 12, Python 3.11.2): after websocket "Abnormal closure" and timeouts the process grew from the usual 60–70% of RAM to 97–98% and was killed by the OS; the reporter suspected a leak. The maintainers: the root cause was a prolonged network problem, "systems will always kill the biggest consumer first", they run bots for months without issue, and the likely Python-specific cause was an aiohttp bug in Python 3.11.1–3.11.3; fixed by moving to Python 3.12. Closed as a question on an outdated version.
- **Meaning here:** a retry loop that queues unboundedly during an outage is the danger, not slow leaks. The health line includes the process's resident memory; the unit sets a memory ceiling so a runaway is killed *by us* and restarted rather than starving the host; the repository's Python floor is recorded in the runbook. A multi-week soak (memory over 14 days on the fake exchange with injected outages) is an exit criterion, not a hope. → [038D](incomplete/EPIC-038D_run_host.md), [038H](incomplete/EPIC-038H_service_units_and_runbook.md)
- Source: https://github.com/freqtrade/freqtrade/issues/10933

## 9. Logs fill the disk, and a full disk looks like something else
- The vendor guide: verbose logs can fill the root filesystem within weeks and "a full disk stops the database write, not the network call, so the symptoms are strange"; bound the journal (`journalctl --vacuum-time`, `SystemMaxUse=`).
- Freqtrade's documented default `log_config` uses a `RotatingFileHandler` (10 MB × 10 files) and supports syslog and journald (journald unavailable on Windows), plus a JSON formatter "alongside a human-readable one". NSSM can rotate captured stdout/stderr (`AppRotate`, `AppRotateBytes`, `AppRotateSeconds`, `AppRotateOnline`); on-demand `nssm rotate`.
- **Verified in this repository:** the engine's file log is a plain `logging.FileHandler` (`sagittarius_engine/infrastructure/logging/std_logger.py:56`); there is no rotation and no size cap. Console logging is on by default (`app_config.json`, `log.console.enabled`). So on systemd the journal is the free rotation; on Windows the wrapper is; a log *file* written by the app grows forever. → [038G](incomplete/EPIC-038G_logging_for_unattended_runs.md)
- Sources: https://www.ssdnodes.com/learn/vps-for-trading-bots · https://www.freqtrade.io/en/stable/advanced-setup/ · https://nssm.cc/usage

## 10. Windows: a service wrapper stops a console app with Ctrl-C first, and gives it 1.5 seconds
- NSSM's own usage page: to stop, it tries in order **Control-C** to the console, **WM_CLOSE** to windows, **WM_QUIT** to threads, then **TerminateProcess**, waiting **1500 ms** at each step by default (tunable); "it is highly recommended not to disable" the last. It restarts an application that exits (`AppExit` default `Restart`), with a throttle that doubles from 2 s up to 256 s; rotation of captured output is built in.
- A search summary also reported a user whose NSSM stopped restarting a crashed process when output rotation, timestamps and redirected hooks were enabled together (a single anecdote from a third-party blog; not opened, so **not** relied on).
- **(general knowledge)** Python on Windows receives Ctrl-C as `SIGINT` and Ctrl-Break as `SIGBREAK`, a separate signal.
- **Meaning here:** on a Windows server the first stop signal is Ctrl-C, so the host handles **both** `SIGINT` and `SIGBREAK`, and the runbook raises NSSM's console stop wait above the host's shutdown budget. Task Scheduler is a weaker supervisor (coarse restart settings, no stop-signal control) — kept as a documented fallback. Pending owner decision O5. → [038D](incomplete/EPIC-038D_run_host.md), [038H](incomplete/EPIC-038H_service_units_and_runbook.md)
- Source: https://nssm.cc/usage

## 11. Remote control: the security mistakes are documented, and the fix is "do not expose it"
- Freqtrade's REST API listens on localhost by default; the page "strongly" advises against exposing it to the internet, recommends an SSH tunnel or VPN because "freqUI does not support https out of the box", and warns that a Docker mapping `8080:8080` or `0.0.0.0:8080:8080` makes it "available to everyone connecting to the server"; use `127.0.0.1:8080:8080`. Secrets and the JWT key should be random (`secrets.token_hex`), 32+ characters.
- Telegram: `authorized_users` limits control; an empty list means nobody controls the bot, and with one ID listed everyone else only receives messages; adding the bot to a group "gives every member access" unless that list is set. `/forceexit` ignores `minimum_roi`.
- OctoBot issue #3632 (opened 2026-08-07): the web interface of a spawned bot is hard-bound to 127.0.0.1 and ignores the configured address — a bug for a VPS user, and a reminder that "bound to localhost" is the *safe* default people fight.
- **Meaning here:** this epic opens **no port**. `status` reads a file the host writes; control of a running host is not in v1 (O4) and, when it comes, is `EPIC-036F` (outbound Discord gateway, user-ID allowlist). A TUI or a web UI would add exactly the surface these pages warn about. → [DECISION](DECISION_2026-10-09_headless_operation.md), [038J](incomplete/EPIC-038J_control_of_a_running_host.md)
- Sources: https://www.freqtrade.io/en/stable/rest-api/ · https://www.freqtrade.io/en/stable/telegram-usage/ · https://github.com/Drakkar-Software/OctoBot/issues?q=is%3Aissue+docker+restart+headless

## 12. What status commands people use
- Freqtrade: `/status` (open trades; `/status table`; by id), `/health` (last bot loop — "bot health"), `/pause`, `/stopbuy`, `/stop`, `/start`, `/reload_config`, `/forceexit`. Hummingbot: `status`, `start`, `stop`, `exit`.
- The one with the most operational value is the **health** one: not "what do I hold" but "when did the bot last do something".
- **Meaning here:** `status` answers three questions in this order — is a host running (and since when), is it making progress (last tick, last stream event, skew), and what do the bots hold (state, reason, last alert). `--json` for scripts. → [038B](incomplete/EPIC-038B_exit_codes_and_output_formats.md), [038C](incomplete/EPIC-038C_bot_status_read_model.md)
- Sources: https://www.freqtrade.io/en/stable/rest-api/ · https://www.freqtrade.io/en/stable/telegram-usage/ · https://hummingbot.org/client/launch-exit/

## 13. Single instance: users isolate instances by state, not by a lock
- Freqtrade's multi-instance guidance: separate database files, separate Telegram bots, separate ports (`--db-url`, one `docker-compose` service each). Nothing on the page prevents starting the same configuration twice.
- **Meaning here:** this app already goes further than the sources: `acquire_instance_access` takes an OS exclusive lock on `<data root>/state/instance.lock` (the OS releases it if the process dies; `EPIC-035H`). What headless adds is the **policy**: a `run` that finds the lock taken must **refuse to start** (a read-only host is useless and a restart loop of read-only copies would look healthy), with a distinct exit code. → [038D](incomplete/EPIC-038D_run_host.md), [038B](incomplete/EPIC-038B_exit_codes_and_output_formats.md)
- Source: https://www.freqtrade.io/en/stable/advanced-setup/

## 14. Config and bot-plan files in version control
- Freqtrade layers several config files (`--config` repeated, last wins; `add_config_files`) and says to "use multiple configuration files to keep secrets secret" and "NEVER share your private configuration file or your exchange keys". The page does not discuss version control itself.
- **Meaning here:** a declarative bot plan (a file a person can review and commit) must hold **no secret and no exchange identifier that is one**; it names a venue and a symbol, never a key. `bot apply` is idempotent and prints a diff before it acts. → [038I](incomplete/EPIC-038I_bot_plan_files.md)
- Source: https://www.freqtrade.io/en/stable/configuration/

## 15. Upgrades: the sources say little, so this app must say it for itself
- Freqtrade's "updating" page covers `git pull` / `pip install -U` / `docker compose pull`, tells the user to read the changelog for breaking changes, and says **nothing** about database migration or backing up state before an update; its configuration page says to start production on a fresh database.
- **Meaning here:** the runbook includes a stop-copy-upgrade-start procedure; the host writes the app version into its snapshot, and `status` and `preflight` warn when the bots' files carry a version this build cannot read (the restore service already refuses a file it cannot read and leaves it untouched — `bot_restore_service.py`). → [038H](incomplete/EPIC-038H_service_units_and_runbook.md), [038C](incomplete/EPIC-038C_bot_status_read_model.md)
- Source: https://www.freqtrade.io/en/stable/updating/

## 16. Headless mode is also a resource saving, and a Qt install on a server has its own cost
- Hummingbot's July 2025 newsletter says headless mode cuts memory by up to 40% (a vendor claim, found in a search summary, **not opened** — not relied on). The app's own proof, [README §1](README.md): even with PySide6 installed, importing `QtWidgets` on a fresh server image failed with `libEGL.so.1: cannot open shared object file` until the package was installed.
- **Meaning here:** a headless install must not need Qt's system libraries. → [038A](incomplete/EPIC-038A_qt_free_boot_and_guard.md)

## 17. What was searched for and not found
- **Reddit.** Two searches (r/algotrading lessons, VPS crashes) returned only vendor pages; no thread was opened. Nothing in this file is attributed to Reddit.
- **Jesse.** Its live-trading page covers installing the live plugin and says nothing on restart, crash behaviour or running on a server (it points to a separate VPS page that was not opened).
- **OctoBot.** One relevant open issue (above); no operational guide was found.
- **Slow memory leaks over weeks.** Only the outage-driven growth of §8; no source documents a leak-over-weeks in any of the four bots.
- **Hummingbot on Docker/VPS** issues: one search returned release notes (an XRPL websocket leak fix, an MQTT reconnect fix) that were not opened.
- **Freqtrade "orders left open after a crash":** a search found no matching issue.
