"""Regenerate `Docs/OPERATIONS/exit_codes.md` from the `ExitCode` enum (`EPIC-038B`).

    python3 scripts/render_exit_codes.py            # print the table
    python3 scripts/render_exit_codes.py --write    # rewrite the document

The table is data in `src/support/cli_host/exit_code_table.py`; the document is
its rendering, and `test_the_exit_code_table_in_the_runbook_source_matches_the_
enum` fails when the two differ.
"""

from __future__ import annotations

import sys
from pathlib import Path

from Sagittarius_Elite_Warrior.src.support.cli_host.exit_code_table import (
    non_restarting_codes,
    render_exit_code_markdown,
)

DOCUMENT = Path(__file__).resolve().parents[1] / "Docs" / "OPERATIONS" / "exit_codes.md"

_HEAD = """# Exit codes

The process exit status of every command-line command. A supervisor, a cron job
or a monitoring script branches on these numbers, so a number is never reused
for another meaning.

This file is **generated** from `ExitCode` (`src/core/contracts/cli_outcome.py`)
and `EXIT_CODE_TABLE` (`src/support/cli_host/exit_code_table.py`) by
`python3 scripts/render_exit_codes.py --write`; do not edit the table by hand,
a guard compares it with the generator.

"""


def render_document() -> str:
    prevent = " ".join(str(code) for code in non_restarting_codes())
    tail = (
        f"\nA systemd unit takes `RestartPreventExitStatus={prevent}` from this table.\n"
        "\nA command that prints a failure and then exits 0 is a bug, not a code.\n"
    )
    return _HEAD + render_exit_code_markdown() + tail


def main(argv: list[str]) -> int:
    text = render_document()
    if "--write" in argv:
        DOCUMENT.parent.mkdir(parents=True, exist_ok=True)
        DOCUMENT.write_text(text, encoding="utf-8")
        sys.stdout.write(f"wrote {DOCUMENT}\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
