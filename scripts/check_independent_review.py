"""A code pull request carries a passing review from a session that wrote none of it (`EPIC-031A`).

`ONBOARDING.md` §7 lets code reach `master-warrior` only after an independent
session reviews it. Every session posts from the same GitHub account, so
GitHub's own "required approvals" cannot tell author from reviewer; the
sessions can. Each commit ends with its author session's `Claude-Session:`
trailer (`commit-rule.md` §2), and the `pr-review` skill ends its PR comment
with its own. This script reads both and sets the commit status
`independent-review` on the pull request's head:

* success when the newest review comment on the head commit -- written by the
  repository's owner, a member or a collaborator, with its verdict on a line of
  its own -- says `Verdict: PASS`, holds the Check ID coverage disclosure, and
  carries a `Claude-Session:` URL that no commit of the pull request carries,
  while every commit carries one (`commit-lint` requires it);
* success, without a review, when the change is documentation-only
  (`ONBOARDING.md` §7: every changed path is `*.md` or the PR template);
* failure otherwise, naming what is missing.

`.github/workflows/independent-review.yml` runs it on every push and every
comment; the `master-warrior` ruleset can then require the status.

What this proves, and what it does not: the session URLs are self-reported. The
status shows that sessions following the process kept author and reviewer
apart; it cannot stop an owner-level account that deliberately writes another
session's URL. Comments from anyone else on this public repository are ignored.
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
#: The verdict line: alone on its line, optionally in bold, one of the three verdicts.
_VERDICT = re.compile(
    r"^\s*\**\s*Verdict:\s*\**\s*(PASS|NEEDS_REVISION|BLOCKING)\b", re.MULTILINE
)
#: Who may review: an account with write access, never a passer-by on a public repository.
TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
_DISCLOSURE = re.compile(r"coverage disclosure", re.IGNORECASE)
_DOCUMENTATION_ONLY_EXTRA = frozenset({".github/PULL_REQUEST_TEMPLATE.md"})
_API = "https://api.github.com"
_PAGE = 100
_SHORT_SHA = 7


@dataclass(frozen=True)
class Comment:
    body: str
    author_association: str


@dataclass(frozen=True)
class PullRequest:
    head_sha: str
    changed_paths: tuple[str, ...]
    commit_messages: tuple[str, ...]
    #: Oldest first, as the API lists them.
    comments: tuple[Comment, ...]


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


def _verdict(body: str) -> str | None:
    match = _VERDICT.search(body)
    return match.group(1) if match else None


def judge(pull_request: PullRequest) -> Verdict:
    """Whether the newest trusted review of the head is an independent pass."""
    if is_documentation_only(pull_request.changed_paths):
        return Verdict(True, "documentation-only: no independent review required")
    unsigned = [
        message.splitlines()[0] if message else "(empty)"
        for message in pull_request.commit_messages
        if not _SESSION.search(message)
    ]
    if unsigned:
        return Verdict(
            False, f"a commit carries no Claude-Session trailer: {unsigned[0]!r}"
        )
    authors = author_sessions(pull_request.commit_messages)
    short_head = pull_request.head_sha[:_SHORT_SHA]
    reviews = [
        comment
        for comment in pull_request.comments
        if comment.author_association in TRUSTED_ASSOCIATIONS
        and short_head in comment.body
        and _verdict(comment.body) is not None
    ]
    if not reviews:
        return Verdict(False, f"no trusted review states a verdict on {short_head}")
    newest = reviews[-1].body
    reviewers = frozenset(_SESSION.findall(newest))
    missing = [
        label
        for label, present in (
            ("`Verdict: PASS`", _verdict(newest) == "PASS"),
            ("the coverage disclosure", _DISCLOSURE.search(newest) is not None),
            ("a reviewer `Claude-Session:`", bool(reviewers)),
            ("a session that wrote no commit", bool(reviewers - authors)),
        )
        if not present
    ]
    if missing:
        return Verdict(
            False, f"the newest review of {short_head} lacks {', '.join(missing)}"
        )
    return Verdict(True, f"independent review passes on {short_head}")


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
        comments=tuple(
            Comment(
                str(item.get("body") or ""), str(item.get("author_association") or "")
            )
            for item in comments
        ),
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
