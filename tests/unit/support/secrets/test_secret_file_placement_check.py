"""`EPIC-038E` — where a secret file may live: outside the repository and outside any
git work tree that does not ignore it. Git's answers are passed in."""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.support.secrets.adapters.secret_file_placement_check import (
    SecretFilePlacementCheck,
)

REPO = Path("/work/repo")


def _placement(*, ignored: bool | None = None, work_trees: tuple[Path, ...] = ()):
    return SecretFilePlacementCheck(
        REPO, lambda _: ignored, lambda _: work_trees[0] if work_trees else None
    )


def test_a_file_outside_every_work_tree_is_accepted() -> None:
    assert _placement().inspect(Path("/etc/sew/secrets/key"), 0).problem == ""


def test_a_file_inside_the_repository_is_refused_even_when_git_ignores_it() -> None:
    verdict = _placement(ignored=True, work_trees=(REPO,)).inspect(
        REPO / "src" / "config" / "key", 0
    )

    assert verdict.problem
    assert "repository" in verdict.problem


def test_a_file_inside_a_git_work_tree_is_refused() -> None:
    other = Path("/home/ops/infra")

    verdict = _placement(ignored=False, work_trees=(other,)).inspect(other / "key", 0)

    assert verdict.problem
    assert "git" in verdict.problem
    assert verdict.fix


def test_a_file_in_a_work_tree_that_git_ignores_is_accepted() -> None:
    other = Path("/home/ops/infra")

    assert (
        _placement(ignored=True, work_trees=(other,)).inspect(other / "key", 0).problem
        == ""
    )


def test_a_work_tree_git_cannot_be_asked_about_refuses_rather_than_trusts() -> None:
    other = Path("/home/ops/infra")

    assert (
        _placement(ignored=None, work_trees=(other,)).inspect(other / "key", 0).problem
    )
