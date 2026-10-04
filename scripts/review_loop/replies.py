"""What the developer and the reviewer answer, as JSON schemas and frozen records.

Both roles reply through `claude -p --json-schema`, so the CLI validates the
shape before this module sees it. The parsers here still check every field:
a schema guards the shape, not the meaning, and an APPROVE that lists open
issues is well-formed JSON that no loop can act on.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class ReplyShapeError(ValueError):
    """A reply that is not the record its schema promises."""


class Verdict(StrEnum):
    APPROVE = "APPROVE"
    CHANGES = "CHANGES"


class IssueStatus(StrEnum):
    """Where a finding from an earlier round stands at this review."""

    FIXED = "fixed"
    OPEN = "open"
    REBUTTAL_ACCEPTED = "rebuttal_accepted"


class Answer(StrEnum):
    """How the developer answered one finding."""

    FIXED = "fixed"
    REBUTTAL = "rebuttal"


@dataclass(frozen=True)
class Issue:
    """One finding the developer must fix or rebut. `id` is stable across
    rounds, so the loop can tell a finding that keeps coming back."""

    id: str
    file: str
    problem: str
    fix: str


@dataclass(frozen=True)
class PriorIssue:
    id: str
    status: IssueStatus


@dataclass(frozen=True)
class Review:
    verdict: Verdict
    issues: tuple[Issue, ...]
    prior_issues: tuple[PriorIssue, ...]
    comment: str

    def still_open(self) -> frozenset[str]:
        """The ids of every earlier finding this review keeps open."""
        return frozenset(
            prior.id for prior in self.prior_issues if prior.status is IssueStatus.OPEN
        )


@dataclass(frozen=True)
class IssueAnswer:
    id: str
    answer: Answer
    detail: str


@dataclass(frozen=True)
class DevReport:
    answers: tuple[IssueAnswer, ...]
    summary: str
    pr_title: str
    pr_body: str

    def claims_a_fix(self) -> bool:
        return any(item.answer is Answer.FIXED for item in self.answers)


_ISSUE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "file": {"type": "string"},
        "problem": {"type": "string"},
        "fix": {"type": "string"},
    },
    "required": ["id", "file", "problem", "fix"],
}

REVIEW_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": [v.value for v in Verdict]},
        "issues": {"type": "array", "items": _ISSUE_SCHEMA},
        "prior_issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": [s.value for s in IssueStatus],
                    },
                },
                "required": ["id", "status"],
            },
        },
        "comment": {"type": "string"},
    },
    "required": ["verdict", "issues", "prior_issues", "comment"],
}

DEV_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "answer": {"type": "string", "enum": [a.value for a in Answer]},
                    "detail": {"type": "string"},
                },
                "required": ["id", "answer", "detail"],
            },
        },
        "summary": {"type": "string"},
        "pr_title": {"type": "string"},
        "pr_body": {"type": "string"},
    },
    "required": ["answers", "summary", "pr_title", "pr_body"],
}


def parse_review(data: object) -> Review:
    record = _mapping(data, "review")
    verdict = _enum(Verdict, _text(record, "verdict"))
    issues = tuple(_issue(item) for item in _items(record, "issues"))
    prior = tuple(
        PriorIssue(
            id=_text(_mapping(item, "prior issue"), "id"),
            status=_enum(IssueStatus, _text(_mapping(item, "prior issue"), "status")),
        )
        for item in _items(record, "prior_issues")
    )
    review = Review(verdict, issues, prior, _text(record, "comment"))
    if verdict is Verdict.APPROVE and (issues or review.still_open()):
        raise ReplyShapeError("APPROVE while findings are still open")
    if verdict is Verdict.CHANGES and not (issues or review.still_open()):
        raise ReplyShapeError("CHANGES without one open finding to act on")
    return review


def parse_dev_report(data: object) -> DevReport:
    record = _mapping(data, "developer report")
    answers = tuple(
        IssueAnswer(
            id=_text(_mapping(item, "answer"), "id"),
            answer=_enum(Answer, _text(_mapping(item, "answer"), "answer")),
            detail=_text(_mapping(item, "answer"), "detail"),
        )
        for item in _items(record, "answers")
    )
    return DevReport(
        answers=answers,
        summary=_text(record, "summary"),
        pr_title=_text(record, "pr_title"),
        pr_body=_text(record, "pr_body"),
    )


def _issue(item: object) -> Issue:
    record = _mapping(item, "issue")
    return Issue(
        id=_text(record, "id"),
        file=_text(record, "file"),
        problem=_text(record, "problem"),
        fix=_text(record, "fix"),
    )


def _mapping(value: object, what: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ReplyShapeError(f"{what} is not a JSON object")
    return value


def _text(record: Mapping[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise ReplyShapeError(f"field {key!r} is missing or not a string")
    return value


def _items(record: Mapping[str, object], key: str) -> list[object]:
    value = record.get(key)
    if not isinstance(value, list):
        raise ReplyShapeError(f"field {key!r} is missing or not a list")
    return value


def _enum[E: StrEnum](kind: type[E], raw: str) -> E:
    try:
        return kind(raw)
    except ValueError as exc:
        raise ReplyShapeError(f"{raw!r} is not a {kind.__name__}") from exc
