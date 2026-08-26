"""`RepoStateStoreLocator` — file placement and deletion, nothing else."""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.repo_state_store_locator import (
    RepoStateStoreLocator,
)


def test_resolves_to_state_ui_state_json_under_the_given_root(tmp_path: Path):
    locator = RepoStateStoreLocator(repo_root=tmp_path)

    assert locator.state_file() == tmp_path / "state" / "ui_state.json"


def test_reset_deletes_an_existing_file(tmp_path: Path):
    locator = RepoStateStoreLocator(repo_root=tmp_path)
    target = locator.state_file()
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")

    locator.reset()

    assert not target.exists()


def test_reset_on_a_missing_file_does_not_raise(tmp_path: Path):
    """R1's whole implementation: "delete the file to reset" must be safe to
    call even when there is nothing to delete — e.g. a user who never changed
    anything yet."""
    locator = RepoStateStoreLocator(repo_root=tmp_path)

    locator.reset()  # must not raise


def test_reset_on_an_unremovable_path_logs_and_does_not_raise(tmp_path: Path):
    """A deletion failure must degrade the same way a write failure does —
    logged, never propagated (`IStateStoreLocator.reset`'s contract).

    A `chmod`-based permission fault does not reach this: tests here run as
    root, which bypasses directory write checks. Instead the path itself is
    made un-`unlink`-able: `state_file()` resolves to a *directory*, so
    `Path.unlink()` raises `IsADirectoryError` — an `OSError` subclass — no
    matter who runs the test.
    """
    locator = RepoStateStoreLocator(repo_root=tmp_path)
    target = locator.state_file()
    target.mkdir(parents=True)  # a directory sits where the file should be

    locator.reset()  # must not raise
