"""The words each role is given. Kept apart from the loop so a prompt can be
read, and changed, without reading control flow."""

from __future__ import annotations

from dataclasses import dataclass

from .replies import DevReport, Issue
from .workspace import ReviewEvidence

_DEV_RULES = """\
Rules for this round:
- Read CLAUDE.md first and follow the repository's rules
  (.claude/skills/execute-task/SKILL.md, .claude/rules/commit-rule.md).
- Commit every change (git add, git commit) with a Conventional Commit message
  and the trailers commit-rule.md requires. Leave the working tree clean.
- Never push, never merge, never rewrite history (no amend, rebase or reset).
- Run the tests you touched before committing. The loop runs the commit tier
  itself after you, and a red result comes back to you as a finding.
- A finding you are sure is wrong: leave the code, answer it as `rebuttal` with
  the reason, and repeat the reason in your next commit message if you commit.
Reply with the JSON object: one entry in `answers` per finding id, a `summary`,
and `pr_title` and `pr_body` describing the whole branch so far (`pr_body` in
the three sections of .github/PULL_REQUEST_TEMPLATE.md)."""

_REVIEWER_ROLE = """\
You are the independent reviewer of a branch in this repository, run by an
automated loop. Another session wrote the change; you did not. You have only
Read, Glob and Grep: no shell and no editing. Everything you need from git is
already in files, listed below."""


@dataclass(frozen=True)
class GateFiles:
    """What the loop collected about the full gate on the pull request's head."""

    pr_url: str
    head: str
    conclusion: str
    job_log: str
    run_log: str | None
    grep_hits: str


def developer_prompt(task: str, round_number: int, findings: tuple[Issue, ...]) -> str:
    opening = (
        f"You are the developer session of an automated dev/review loop.\n"
        f"Task: read {task} and deliver it.\nRound {round_number}.\n"
    )
    if not findings:
        return f"{opening}\nNo findings yet: implement the task.\n\n{_DEV_RULES}"
    listed = "\n".join(
        f"- [{item.id}] {item.file}: {item.problem}\n  Suggested fix: {item.fix}"
        for item in findings
    )
    return f"{opening}\nFindings to answer, each by its id:\n{listed}\n\n{_DEV_RULES}"


def first_review_prompt(task: str, base: str, evidence: ReviewEvidence) -> str:
    return f"""{_REVIEWER_ROLE}
- The whole change against {base}: {evidence.full_patch}
- Its commits and their messages: {evidence.commit_log}
The task the change delivers: {task}.

Read CLAUDE.md, .claude/ONBOARDING.md, .claude/skills/pr-review/SKILL.md and
.claude/skills/pr-review/references/rubric.md, then review as the skill defines.
Give each finding a stable id `R<round>-<n>`; a finding raised again later keeps
its id. Reply with the JSON object: `verdict` APPROVE only when nothing blocking
remains; `issues` are this round's findings; `prior_issues` is empty in this
first round; `comment` is your review as markdown."""


def re_review_prompt(evidence: ReviewEvidence, report: DevReport) -> str:
    answers = "\n".join(
        f"- [{item.id}] {item.answer.value}: {item.detail}" for item in report.answers
    )
    return f"""Re-review. The developer committed since {evidence.since}; the head is {evidence.head}.
- What changed since your last review: {evidence.delta_patch}
- The new commits and their messages: {evidence.commit_log}
- The whole change, again: {evidence.full_patch}
The developer's answers:
{answers or "- (no answers)"}

Do three things. (a) Review what changed. (b) For every finding you raised
before, set its status in `prior_issues`: `fixed`, `open`, or
`rebuttal_accepted` when the developer's reason is sound; judge the reason, not
who gave it, and never keep a finding open only because you raised it.
(c) Re-read the whole change for anything new, as `issues` with new ids."""


def gate_review_prompt(gate: GateFiles) -> str:
    run_log = gate.run_log or "not available: say so under Not verified"
    return f"""The branch is pushed and pull request {gate.pr_url} is open at head {gate.head}.
The full gate (GitHub Actions `ci-local.ps1 -Full`) finished with conclusion
`{gate.conclusion}`.
- Its job log: {gate.job_log}
- The run log from its artifact: {run_log}
- Lines matching FAILED|ERROR|Traceback|ResourceWarning: {gate.grep_hits}

Verify the gate from these files as .claude/rules/ci-rule.md §1 and your rubric's
B1 and B2 require, then give your verdict on the pull request as it stands, with
`prior_issues` as before. `comment` is now the durable pull request comment:
verdict, findings, verification state and the itemized Check ID Coverage
Disclosure table the rubric requires, under a heading with the words "Coverage
Disclosure". Do not write a `Verdict:` line or a `Claude-Session:` line: the
loop adds the reviewed head, the verdict line and your session to the comment
it posts. A failed gate is an `issues` entry per failure."""


def reformat_prompt(problem: str) -> str:
    return (
        f"Your last reply did not match the required JSON object: {problem}. "
        "Reply again with only that JSON object, keeping your content."
    )
