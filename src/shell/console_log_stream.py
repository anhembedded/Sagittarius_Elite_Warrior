"""Where the application's console log is written (`EPIC-038D`).

Capability: Send the console log to stderr for a run whose stdout carries a report
    Also: log to stderr, stdout is the report, --json log line, machine format, StdLogger writes to stdout, log.console.enabled
    Use: console_log_to
    User: src/main.py
    Status: stable

The Engine's `StdLogger` builds its console handler on `sys.stdout` at the moment
it is constructed, and `create_app` constructs it twice (before the bus, then in
`LoggerExtension.register`). A command that prints a machine-readable report
(`--json`, `--format <name>`) owns stdout, so its log must leave by stderr or a
single INFO line breaks the document. Switching the console log *off* for those
runs (`EPIC-038B`) fixed the document and lost the log: with `log.file` unset a
WARNING from an adapter reached nowhere but Python's last-resort printer, bare and
unformatted.

The Engine is not changed (decision O7). While the object graph is built,
`sys.stdout` names the stream the log should use; the handlers keep that stream
for the life of the process, and `sys.stdout` is put back before anything prints.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TextIO


@contextmanager
def console_log_to(stream: TextIO) -> Iterator[None]:
    """Build the logger inside this block and its console handler writes to `stream`.

    Only code that constructs the logger belongs inside; the block runs on one
    thread before the application boots.
    """
    saved = sys.stdout
    sys.stdout = stream
    try:
        yield
    finally:
        sys.stdout = saved
