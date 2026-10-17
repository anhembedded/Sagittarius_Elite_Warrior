"""What `main.py run` was asked for, checked (`EPIC-038D`).

`cli_commands.json` declares the flags and argparse enforces their types and
choices (a wrong word is exit 2 before anything starts). What it cannot say is that
a timeout must be positive, which is checked here, once, and refused with the same
exit code and a sentence that names the flag.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import StrEnum

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)

#: `TimeoutStopSec` of a unit must exceed this by the app's own stop (a few seconds).
DEFAULT_STOP_TIMEOUT_SECONDS = 25.0
DEFAULT_HEALTH_INTERVAL_SECONDS = 60


class StopPolicyName(StrEnum):
    """The words `--on-stop` takes (decision O1)."""

    LEAVE_ORDERS = "leave-orders"
    STOP_BOTS = "stop-bots"


class HostSignalName(StrEnum):
    """The words `--host-signal` takes."""

    NONE = "none"
    SDNOTIFY = "sdnotify"


@dataclass(frozen=True, slots=True)
class RunOptions:
    stop_timeout_s: float = DEFAULT_STOP_TIMEOUT_SECONDS
    health_interval_s: int = DEFAULT_HEALTH_INTERVAL_SECONDS
    on_stop: StopPolicyName = StopPolicyName.LEAVE_ORDERS
    start_planned: bool = False
    resume_recovering: bool = False
    resume_halted: bool = False
    accept_silent_failures: bool = False
    skip_preflight: bool = False
    confirm_venue: str | None = None
    host_signal: HostSignalName = HostSignalName.NONE


def run_options_of(args: argparse.Namespace) -> RunOptions | CliOutcome:
    """The options, or the usage error that names the flag that is wrong."""
    options = RunOptions(
        stop_timeout_s=float(
            getattr(args, "stop_timeout", DEFAULT_STOP_TIMEOUT_SECONDS)
        ),
        health_interval_s=int(
            getattr(args, "health_interval", DEFAULT_HEALTH_INTERVAL_SECONDS)
        ),
        on_stop=StopPolicyName(getattr(args, "on_stop", StopPolicyName.LEAVE_ORDERS)),
        start_planned=bool(getattr(args, "start_planned", False)),
        resume_recovering=bool(getattr(args, "resume_recovering", False)),
        resume_halted=bool(getattr(args, "resume_halted", False)),
        accept_silent_failures=bool(getattr(args, "i_accept_silent_failures", False)),
        skip_preflight=bool(getattr(args, "skip_preflight", False)),
        confirm_venue=getattr(args, "confirm_venue", None),
        host_signal=HostSignalName(getattr(args, "host_signal", HostSignalName.NONE)),
    )
    if options.stop_timeout_s <= 0:
        return CliOutcome(ExitCode.USAGE, "--stop-timeout must be greater than zero")
    if options.health_interval_s < 1:
        return CliOutcome(ExitCode.USAGE, "--health-interval must be at least 1 second")
    return options
