"""A code pull request carries a passing review from a session that wrote none of it (`EPIC-031A`).

`ONBOARDING.md` §7 lets code reach `master-warrior` only after an independent
session reviews it. Every session posts from the same GitHub account, so
GitHub's own "required approvals" cannot tell author from reviewer; the
sessions can. Each commit ends with its author session's `Claude-Session:`
trailer (`commit-rule.md` §2), and the `pr-review` skill ends its PR comment
with its own. This script reads both and sets the commit status
`independent-review` on the pull request's head:

* success when a comment names the head commit, says `Verdict: PASS`, holds the
  Check ID coverage disclosure, and carries a `Claude-Session:` URL that no
  commit of the pull request carries;
* success, without a review, when the change is documentation-only
  (`ONBOARDING.md` §7: every changed path is `*.md` or the PR template);
* failure otherwise, naming what is missing.

`.github/workflows/independent-review.yml` runs it on every push and every
comment; the `master-warrior` ruleset can then require the status.
Stdlib only, so it runs on the runner's system Python.

Retire when: the reviewer posts from its own GitHub identity, so a native
required-approval rule can carry the same guarantee.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass

STATUS_CONTEXT = "independent-review"
_SESSION = re.compile(
    r"Claude-Session:\s*(https://claude\.ai/code/session_[A-Za-z0-9]+)"
)
_VERDICT_PASS = re.compile(r"verdict:?\**\s*\**\s*pass\b", re.IGNORECASE)
_DISCLOSURE = re.compile(r"coverage disclosure", re.IGNORECASE)
_DOCUMENTATION_ONLY_EXTRA = frozenset({".github/PULL_REQUEST_TEMPLATE.md"})
_API = "https://api.github.com"
_PAGE = 100
_SHORT_SHA = 7


@dataclass(frozen=True)
class PullRequest:
    head_sha: str
    changed_paths: tuple[str, ...]
    commit_messages: tuple[str, ...]
    comments: tuple[str, ...]


@dataclass(frozen=True)
class Verdict:
    passed: bool
    reason: str


def is_documentation_only(paths: tuple[str, ...]) -> bool:
    return bool(paths) and all(
        path.endswith(".md") or path in _DOCUMENTATION_ONLY_EXTRA for path in paths
    )


def author_sessions(commit_messages: tuple[str, ...]) -> frozenset[str]:
    return frozenset(
        url for message in commit_messages for url in _SESSION.findall(message)
    )


def judge(pull_request: PullRequest) -> Verdict:
    """Whether the pull request carries an independent passing review of its head."""
    if is_documentation_only(pull_request.changed_paths):
        return Verdict(True, "documentation-only: no independent review required")
    authors = author_sessions(pull_request.commit_messages)
    short_head = pull_request.head_sha[:_SHORT_SHA]
    gaps: list[str] = []
    for comment in pull_request.comments:
        reviewers = frozenset(_SESSION.findall(comment))
        missing = [
            label
            for label, present in (
                ("the head commit", short_head in comment),
                ("`Verdict: PASS`", _VERDICT_PASS.search(comment) is not None),
                ("the coverage disclosure", _DISCLOSURE.search(comment) is not None),
                ("a reviewer `Claude-Session:`", bool(reviewers)),
                ("a session that wrote no commit", bool(reviewers - authors)),
            )
            if not present
        ]
        if not missing:
            return Verdict(True, f"independent review passes on {short_head}")
        if short_head in comment and _VERDICT_PASS.search(comment):
            gaps.append(", ".join(missing))
    detail = f"; the closest review lacks {gaps[-1]}" if gaps else ""
    return Verdict(False, f"no independent passing review of {short_head}{detail}")


def _get(url: str, token: str) -> object:
    request = urllib.request.Request(  # noqa: S310 -- `url` is built on the https `_API` host
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- the request above targets the https `_API` host
        return json.load(response)


def _pages(url: str, token: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    page = 1
    while True:
        batch = _get(f"{url}?per_page={_PAGE}&page={page}", token)
        if not isinstance(batch, list) or not batch:
            return items
        items.extend(batch)
        page += 1


def _field(item: object, *keys: str) -> object:
    """`item[keys[0]][keys[1]]…`, refusing anything that is not the JSON shape the API documents."""
    value = item
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"unexpected GitHub API payload: no {'.'.join(keys)}")
        value = value[key]
    return value


def fetch(repository: str, number: int, token: str) -> PullRequest:
    base = f"{_API}/repos/{repository}"
    pull = _get(f"{base}/pulls/{number}", token)
    files = _pages(f"{base}/pulls/{number}/files", token)
    commits = _pages(f"{base}/pulls/{number}/commits", token)
    comments = _pages(f"{base}/issues/{number}/comments", token)
    return PullRequest(
        head_sha=str(_field(pull, "head", "sha")),
        changed_paths=tuple(str(_field(item, "filename")) for item in files),
        commit_messages=tuple(
            str(_field(item, "commit", "message")) for item in commits
        ),
        comments=tuple(str(item.get("body") or "") for item in comments),
    )


def post_status(repository: str, sha: str, verdict: Verdict, token: str) -> None:
    body = json.dumps(
        {
            "state": "success" if verdict.passed else "failure",
            "context": STATUS_CONTEXT,
            "description": verdict.reason[:140],
        }
    ).encode()
    request = urllib.request.Request(  # noqa: S310 -- the https `_API` host
        f"{_API}/repos/{repository}/statuses/{sha}",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=30):  # noqa: S310 -- the request above targets the https `_API` host
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repository", required=True, help="owner/name")
    parser.add_argument("--pull-request", type=int, required=True)
    arguments = parser.parse_args(argv)
    token = os.environ["GITHUB_TOKEN"]
    pull_request = fetch(arguments.repository, arguments.pull_request, token)
    verdict = judge(pull_request)
    post_status(arguments.repository, pull_request.head_sha, verdict, token)
    print(
        f"{STATUS_CONTEXT}: {'success' if verdict.passed else 'failure'} — {verdict.reason}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
