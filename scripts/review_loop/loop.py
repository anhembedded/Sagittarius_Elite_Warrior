"""The inner loop: developer round, the commit tier, review, until APPROVE.

A round ends in one of three ways: the developer's work is unusable (dirty
tree, a fix claimed with no commit, a red commit tier), which goes straight
back to the developer; the reviewer approves; or the reviewer asks for changes.
The loop stops for a person when the rounds run out, or when a finding stays
open after the developer has answered it `stuck_after` times in a row.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from .commit_tier import CommitTier
from .prompts import (
    GateFiles,
    developer_prompt,
    first_review_prompt,
    gate_review_prompt,
    re_review_prompt,
)
from .replies import DevReport, Issue, Review, Verdict
from .roles import Developer, Reviewer
from .workspace import Workspace

_log = logging.getLogger("App.ReviewLoop")


class LoopEnd(StrEnum):
    APPROVED = "approved"
    NEEDS_HUMAN = "needs_human"


@dataclass(frozen=True)
class LoopResult:
    end: LoopEnd
    reason: str
    report: DevReport | None


@dataclass(frozen=True)
class LoopSettings:
    task: str
    base_ref: str
    max_rounds: int
    stuck_after: int


class RunRecord:
    """Every round's replies as JSON under one run directory, which also holds
    the evidence files the reviewer reads (so it lies inside the checkout)."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def round_dir(self, round_number: int) -> Path:
        return self._root / f"round-{round_number:02d}"

    def write(self, round_number: int, name: str, record: Review | DevReport) -> None:
        directory = self.round_dir(round_number)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{name}.json").write_text(
            json.dumps(asdict(record), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


class FindingLedger:
    """Every finding by id, and how many reviews in a row kept it open after
    the developer had answered it."""

    def __init__(self) -> None:
        self._known: dict[str, Issue] = {}
        self._streaks: dict[str, int] = {}

    def absorb(self, review: Review, report: DevReport | None) -> None:
        answered = {item.id for item in report.answers} if report is not None else set()
        still_open = review.still_open()
        for issue_id in list(self._streaks):
            if issue_id not in still_open:
                del self._streaks[issue_id]
        for issue_id in still_open & answered:
            self._streaks[issue_id] = self._streaks.get(issue_id, 0) + 1
        for issue in review.issues:
            self._known[issue.id] = issue

    def open_findings(self, review: Review) -> tuple[Issue, ...]:
        carried = tuple(
            self._known[issue_id]
            for issue_id in sorted(review.still_open())
            if issue_id in self._known
        )
        return review.issues + carried

    def deadlocked(self, stuck_after: int) -> tuple[str, ...]:
        return tuple(sorted(i for i, n in self._streaks.items() if n >= stuck_after))


class ReviewLoop:
    def __init__(
        self,
        workspace: Workspace,
        roles: tuple[Developer, Reviewer],
        checks: tuple[CommitTier, RunRecord],
        settings: LoopSettings,
    ) -> None:
        self._workspace = workspace
        self._developer, self._reviewer = roles
        self._commit_tier, self._record = checks
        self._settings = settings
        self._ledger = FindingLedger()
        self._round = 0
        self._reviewed_sha: str | None = None
        self._green_sha: str | None = None

    def run(self, findings: tuple[Issue, ...]) -> LoopResult:
        """Rounds until the reviewer approves the local branch, or a stop."""
        base = self._workspace.merge_base(self._settings.base_ref)
        while self._round < self._settings.max_rounds:
            self._round += 1
            report, problem = self._develop(findings)
            if problem is not None:
                findings = (problem,)
                continue
            review = self._review_round(report, base)
            if review.verdict is Verdict.APPROVE:
                return LoopResult(LoopEnd.APPROVED, "the reviewer approved", report)
            stop = self.stop_reason()
            if stop is not None:
                return LoopResult(LoopEnd.NEEDS_HUMAN, stop, report)
            findings = self._ledger.open_findings(review)
        return LoopResult(
            LoopEnd.NEEDS_HUMAN, f"{self._settings.max_rounds} rounds used", None
        )

    def review_gate(self, gate: GateFiles, reminder: str) -> Review:
        """The reviewer's verdict on the pushed head, in its same session;
        `reminder`, when not empty, follows the prompt."""
        prompt = gate_review_prompt(gate)
        review = self._reviewer.review(
            f"{prompt}\n\n{reminder}" if reminder else prompt
        )
        self._record.write(self._round, "gate-review", review)
        self._ledger.absorb(review, None)
        return review

    def reviewer_session_id(self) -> str:
        session = self._reviewer.session_id
        if session is None:
            raise RuntimeError("the reviewer has not reviewed yet")
        return session

    def findings_after(self, review: Review) -> tuple[Issue, ...]:
        return self._ledger.open_findings(review)

    def _develop(self, findings: tuple[Issue, ...]) -> tuple[DevReport, Issue | None]:
        before = self._workspace.head()
        prompt = developer_prompt(self._settings.task, self._round, findings)
        report = self._developer.work(prompt)
        self._record.write(self._round, "developer", report)
        problem = self._commit_problem(before, report, findings)
        if problem is None:
            problem = self._check_commit_tier()
        if problem is not None:
            _log.info(
                "[review-loop] round %d back to the developer: %s",
                self._round,
                problem.id,
            )
        return report, problem

    def _commit_problem(
        self, before: str, report: DevReport, findings: tuple[Issue, ...]
    ) -> Issue | None:
        if not self._workspace.is_clean():
            return Issue(
                "tree-dirty",
                "(working tree)",
                "the round ended with uncommitted changes",
                "commit them or discard them",
            )
        if self._workspace.head() != before:
            return None
        if report.claims_a_fix():
            return Issue(
                "no-commit",
                "(branch)",
                "findings were answered as fixed but HEAD did not move",
                "commit the fixes",
            )
        if not findings:
            return Issue(
                "no-change",
                "(branch)",
                "the task was not started: no commit was made",
                "implement the task and commit it",
            )
        return None

    def _check_commit_tier(self) -> Issue | None:
        head = self._workspace.head()
        if head == self._green_sha:
            return None
        transcript = self._record.round_dir(self._round) / "commit-tier.log"
        outcome = self._commit_tier.run(transcript)
        if not outcome.passed:
            return Issue(
                "commit-tier",
                "(commit tier)",
                outcome.report,
                "make every commit-tier check pass, then commit",
            )
        self._green_sha = head
        return None

    def _review_round(self, report: DevReport, base: str) -> Review:
        evidence = self._workspace.write_evidence(
            self._reviewed_sha or base,
            base,
            self._record.round_dir(self._round) / "evidence",
        )
        if self._reviewed_sha is None:
            prompt = first_review_prompt(
                self._settings.task, self._settings.base_ref, evidence
            )
        else:
            prompt = re_review_prompt(evidence, report)
        review = self._reviewer.review(prompt)
        self._record.write(self._round, "review", review)
        self._reviewed_sha = evidence.head
        self._ledger.absorb(review, report)
        return review

    def stop_reason(self) -> str | None:
        stuck = self._ledger.deadlocked(self._settings.stuck_after)
        if not stuck:
            return None
        return (
            f"findings {', '.join(stuck)} stayed open after the developer answered them "
            f"{self._settings.stuck_after} times"
        )
