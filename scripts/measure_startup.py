"""Measure how long a command takes to start, here or against another checkout (`PRO-014`).

    python3 scripts/measure_startup.py -- bot list
    python3 scripts/measure_startup.py --against /opt/old/Sagittarius_Elite_Warrior --runs 25 -- bot list

Runs `src/main.py <words>` in a fresh interpreter `--runs` times and prints the wall time (min,
median, max) and the cumulative import time of the top-level imports, from one `python -X
importtime` run: the pre-log cost, which is what a short command pays before it does anything.
With `--against` the two checkouts are run interleaved, so a noisy machine moves both the same
way, and the ratio is printed. Run it as the account that runs the commands: the bytecode
cache is per directory and a checkout the account cannot write to has none to read unless
`python -m compileall` was run as root (`Docs/OPERATIONS/headless_runbook.md` §2).

The environment is inherited, so `SEW_DATA_ROOT` names the data root the command reads. Stdlib
only: it needs neither the Engine nor Qt.
"""

from __future__ import annotations

import argparse
import os
import re
import statistics
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

_CHECKOUT = Path(__file__).resolve().parents[1]
#: `import time:   self | cumulative | package` - the line `-X importtime` writes per import.
_IMPORT_LINE = re.compile(r"^import time:\s+\d+ \|\s+(\d+) \| (\S.*)$")


@dataclass(slots=True)
class Samples:
    """What was measured for one checkout."""

    checkout: Path
    wall_seconds: list[float] = field(default_factory=list)
    import_seconds: float = 0.0


def _command(checkout: Path, words: Sequence[str], *flags: str) -> list[str]:
    return [sys.executable, *flags, str(checkout / "src" / "main.py"), *words]


def _environment(checkout: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(checkout.parent), *filter(None, [env.get("PYTHONPATH")])]
    )
    return env


def _run_once(checkout: Path, words: Sequence[str]) -> float:
    started = time.perf_counter()
    subprocess.run(  # noqa: S603 -- this interpreter, the checkout's own main.py, the operator's words
        _command(checkout, words),
        env=_environment(checkout),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return time.perf_counter() - started


def top_level_import_seconds(importtime_report: str) -> float:
    """The sum of the cumulative times of the imports no other import started: depth zero."""
    total_microseconds = 0
    for line in importtime_report.splitlines():
        found = _IMPORT_LINE.match(line)
        if found and not found.group(2).startswith(" "):
            total_microseconds += int(found.group(1))
    return total_microseconds / 1_000_000


def _import_seconds(checkout: Path, words: Sequence[str]) -> float:
    completed = subprocess.run(  # noqa: S603 -- same command as _run_once, with -X importtime
        _command(checkout, words, "-X", "importtime"),
        env=_environment(checkout),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return top_level_import_seconds(completed.stderr)


def measure(
    checkouts: Sequence[Path], words: Sequence[str], runs: int
) -> list[Samples]:
    """Wall times, interleaved across the checkouts, and one import report each."""
    samples = [Samples(checkout) for checkout in checkouts]
    for _ in range(runs):
        for sample in samples:
            sample.wall_seconds.append(_run_once(sample.checkout, words))
    for sample in samples:
        sample.import_seconds = _import_seconds(sample.checkout, words)
    return samples


def _row(sample: Samples) -> str:
    walls = sample.wall_seconds
    return (
        f"wall min {min(walls):.3f}s  median {statistics.median(walls):.3f}s  "
        f"max {max(walls):.3f}s   imports {sample.import_seconds:.3f}s   {sample.checkout}"
    )


def report(samples: Sequence[Samples]) -> str:
    lines = [_row(sample) for sample in samples]
    if len(samples) > 1:
        this, other = samples[0], samples[1]
        ratio = statistics.median(other.wall_seconds) / statistics.median(
            this.wall_seconds
        )
        lines.append(
            f"median wall: {other.checkout} takes {ratio:.2f}x as long as {this.checkout}"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs", type=int, default=15, help="runs per checkout")
    parser.add_argument(
        "--against",
        type=Path,
        help="another checkout (the directory named Sagittarius_Elite_Warrior) to compare with",
    )
    parser.add_argument("words", nargs="+", help="after --: the command, e.g. bot list")
    args = parser.parse_args(argv)
    checkouts = [_CHECKOUT] + ([args.against.resolve()] if args.against else [])
    sys.stdout.write(report(measure(checkouts, args.words, args.runs)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
