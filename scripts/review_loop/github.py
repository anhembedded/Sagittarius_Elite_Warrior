"""The pull request side: open it, find the full gate on a head, collect the
gate's logs, post the reviewer's comment.

JSON calls go through `gh api`, which is the real GitHub CLI on a workstation
and Claude Code's built-in client in a cloud session; both speak the REST API.
Logs and artifacts are served from another host by redirect, which the built-in
client refuses, so a download falls back to plain HTTPS (`GH_TOKEN` or
`GITHUB_TOKEN` is sent when set, which a private repository needs).
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import subprocess
import urllib.request
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

#: What the gate log is searched for (`ci-rule.md` §1, "Log Inspection").
GATE_LOG_PATTERN = re.compile(r"FAILED|ERROR|Traceback|ResourceWarning")
GATE_ARTIFACT = "ci-local-logs"
_PASSING_CONCLUSIONS = frozenset({"success", "neutral", "skipped"})
_RUN_IN_DETAILS = re.compile(r"/actions/runs/(\d+)/")
_API_ROOT = "https://api.github.com/"
_log = logging.getLogger("App.ReviewLoop")


class GitHubError(RuntimeError):
    """A GitHub request failed or answered something unexpected."""


@dataclass(frozen=True)
class PullRequest:
    number: int
    url: str


@dataclass(frozen=True)
class PullRequestDraft:
    head: str
    base: str
    title: str
    body: str


@dataclass(frozen=True)
class GateRun:
    """A finished full-gate check run. In GitHub Actions the check run's id is
    its job's id."""

    job_id: int
    run_id: int
    conclusion: str
    url: str


@dataclass(frozen=True)
class HeadState:
    """Every check run and commit status on a head that has not passed yet."""

    pending: tuple[str, ...]
    failed: tuple[str, ...]


@dataclass(frozen=True)
class GateLogs:
    job_log: Path
    run_log: Path | None


class GitHub(ABC):
    @abstractmethod
    def ensure_pull_request(self, draft: PullRequestDraft) -> PullRequest: ...

    @abstractmethod
    def finished_gate(self, head_sha: str, check_name: str) -> GateRun | None:
        """The gate on `head_sha` once it has finished; `None` while it is
        queued, running, or not yet created."""

    @abstractmethod
    def download_gate_logs(self, gate: GateRun, directory: Path) -> GateLogs: ...

    @abstractmethod
    def post_comment(self, pull_number: int, body: str) -> str: ...

    @abstractmethod
    def head_state(self, head_sha: str) -> HeadState: ...


class GhCliGitHub(GitHub):
    def __init__(self, gh: str, repository: str) -> None:
        self._gh = gh
        self._repository = repository

    def ensure_pull_request(self, draft: PullRequestDraft) -> PullRequest:
        owner = self._repository.split("/")[0]
        found = self._json(
            "GET",
            f"repos/{self._repository}/pulls?state=open&head={owner}:{draft.head}",
            None,
        )
        if isinstance(found, list) and found:
            return _pull_request(found[0])
        created = self._json(
            "POST",
            f"repos/{self._repository}/pulls",
            {
                "title": draft.title,
                "body": draft.body,
                "head": draft.head,
                "base": draft.base,
            },
        )
        return _pull_request(created)

    def finished_gate(self, head_sha: str, check_name: str) -> GateRun | None:
        answer = self._json(
            "GET", f"repos/{self._repository}/commits/{head_sha}/check-runs", None
        )
        runs = answer.get("check_runs", []) if isinstance(answer, dict) else []
        for run in runs:
            if run.get("name") != check_name or run.get("status") != "completed":
                continue
            details = _RUN_IN_DETAILS.search(str(run.get("details_url", "")))
            if details is None:
                raise GitHubError(f"check run {run.get('id')} names no Actions run")
            return GateRun(
                job_id=int(run["id"]),
                run_id=int(details.group(1)),
                conclusion=str(run.get("conclusion")),
                url=str(run.get("html_url", "")),
            )
        return None

    def download_gate_logs(self, gate: GateRun, directory: Path) -> GateLogs:
        directory.mkdir(parents=True, exist_ok=True)
        job_log = directory / "job.log"
        job_log.write_bytes(
            self._download(f"repos/{self._repository}/actions/jobs/{gate.job_id}/logs")
        )
        return GateLogs(job_log, self._run_log(gate, directory))

    def post_comment(self, pull_number: int, body: str) -> str:
        answer = self._json(
            "POST",
            f"repos/{self._repository}/issues/{pull_number}/comments",
            {"body": body},
        )
        if not isinstance(answer, dict):
            raise GitHubError("posting the comment returned no object")
        return str(answer.get("html_url", ""))

    def head_state(self, head_sha: str) -> HeadState:
        pending: list[str] = []
        failed: list[str] = []
        runs = self._json(
            "GET", f"repos/{self._repository}/commits/{head_sha}/check-runs", None
        )
        for run in runs.get("check_runs", []) if isinstance(runs, dict) else []:
            name = str(run.get("name"))
            if run.get("status") != "completed":
                pending.append(name)
            elif run.get("conclusion") not in _PASSING_CONCLUSIONS:
                failed.append(name)
        combined = self._json(
            "GET", f"repos/{self._repository}/commits/{head_sha}/status", None
        )
        for status in (
            combined.get("statuses", []) if isinstance(combined, dict) else []
        ):
            context = str(status.get("context"))
            if status.get("state") == "pending":
                pending.append(context)
            elif status.get("state") != "success":
                failed.append(context)
        return HeadState(tuple(pending), tuple(failed))

    def _run_log(self, gate: GateRun, directory: Path) -> Path | None:
        listing = self._json(
            "GET",
            f"repos/{self._repository}/actions/runs/{gate.run_id}/artifacts",
            None,
        )
        artifacts = listing.get("artifacts", []) if isinstance(listing, dict) else []
        match = next((a for a in artifacts if a.get("name") == GATE_ARTIFACT), None)
        if match is None:
            return None
        archive = self._download(
            f"repos/{self._repository}/actions/artifacts/{match['id']}/zip"
        )
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            names = [n for n in bundle.namelist() if re.search(r"ci-local-\d", n)]
            if not names:
                return None
            target = directory / Path(names[0]).name
            target.write_bytes(bundle.read(names[0]))
        return target

    def _json(self, method: str, endpoint: str, body: dict[str, str] | None) -> object:
        argv = [self._gh, "api", "-X", method, endpoint]
        if body is not None:
            argv += ["--input", "-"]
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        completed = self._gh_run(argv, payload)
        try:
            return json.loads(completed or b"null")
        except json.JSONDecodeError as exc:
            raise GitHubError(f"{method} {endpoint} returned no JSON") from exc

    def _download(self, endpoint: str) -> bytes:
        try:
            return self._gh_run([self._gh, "api", endpoint], None)
        except GitHubError as exc:
            _log.info(
                "[review-loop] gh could not download %s (%s); using HTTPS",
                endpoint,
                exc,
            )
            request = urllib.request.Request(_API_ROOT + endpoint)  # noqa: S310 -- fixed https root
            token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
            if token:
                request.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
                return bytes(response.read())

    def _gh_run(self, argv: list[str], stdin: bytes | None) -> bytes:
        # `S603` is suppressed, not worked around: `gh` is an absolute path the
        # CLI resolved, the endpoint is built from this module's literals and
        # GitHub's own ids, and there is no shell.
        completed = subprocess.run(  # noqa: S603
            argv, input=stdin, capture_output=True, check=False
        )
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            raise GitHubError(f"{' '.join(argv[1:5])}: {stderr[:500]}")
        return completed.stdout


def gate_log_hits(run_log: Path | None, job_log: Path) -> str:
    """The lines of the run log (the job log when there is none) that match
    `GATE_LOG_PATTERN`, each with its line number."""
    source = run_log if run_log is not None else job_log
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    hits = [
        f"{n}: {line}"
        for n, line in enumerate(lines, 1)
        if GATE_LOG_PATTERN.search(line)
    ]
    return f"source: {source.name}\n" + (
        "\n".join(hits) if hits else "(no line matched)"
    )


def _pull_request(data: object) -> PullRequest:
    if not isinstance(data, dict) or not isinstance(data.get("number"), int):
        raise GitHubError("GitHub answered no pull request")
    return PullRequest(number=data["number"], url=str(data.get("html_url", "")))
