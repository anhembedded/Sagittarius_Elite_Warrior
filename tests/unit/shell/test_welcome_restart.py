"""`EPIC-025` PR 1.5b — what the next process is told, and what happens if it
cannot be started.

`argv_for_restart()` is a pure function so the decision is testable without
spawning anything, and the decision has one real subtlety worth a file of its
own: `--dev` / `--debug` on the *old* command line would win over the file on
the next run (`resolve_dev_mode()` reads the flag first), so a user who turns
developer mode off from a session started with the flag must not be handed it
back.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.shell.welcome.restart import (
    argv_for_restart,
    restart_now,
)


class TestWhatTheNextProcessIsTold:
    def test_the_script_path_is_kept(self) -> None:
        """The app may have been started as a script or as `python -m ...`;
        the next process has to start the way this one did, not a way this
        function guessed."""
        assert argv_for_restart(
            ["python", "-m", "Sagittarius_Elite_Warrior.src.main"],
            dev_mode_enabled=True,
        ) == ["python", "-m", "Sagittarius_Elite_Warrior.src.main"]

    def test_turning_developer_mode_off_strips_the_flag_that_would_win(self) -> None:
        """The case this function exists for: `--dev` beats the file, so
        keeping it would hand developer mode straight back to a user who just
        switched it off."""
        assert argv_for_restart(
            ["python", "app.py", "--dev"], dev_mode_enabled=False
        ) == ["python", "app.py"]

    def test_every_dev_flag_is_stripped_not_just_the_first(self) -> None:
        assert argv_for_restart(
            ["python", "app.py", "--debug", "--dev", "sync"], dev_mode_enabled=False
        ) == ["python", "app.py", "sync"]

    def test_turning_it_on_keeps_the_command_line_as_it_was(self) -> None:
        """Nothing to strip: the flag and the file now agree, and rewriting a
        user's command line further than the switch requires is a surprise."""
        assert argv_for_restart(
            ["python", "app.py", "--dev"], dev_mode_enabled=True
        ) == ["python", "app.py", "--dev"]

    def test_other_arguments_survive_in_order(self) -> None:
        assert argv_for_restart(
            ["python", "app.py", "sync", "--symbol", "BTCUSDT"],
            dev_mode_enabled=False,
        ) == ["python", "app.py", "sync", "--symbol", "BTCUSDT"]

    def test_an_empty_command_line_asks_for_nothing(self) -> None:
        assert argv_for_restart([], dev_mode_enabled=False) == []


class TestTheRestartItself:
    def test_it_starts_the_new_process_then_quits_this_one(self) -> None:
        order: list[str] = []

        started = restart_now(
            ["python", "app.py", "--dev"],
            dev_mode_enabled=False,
            start_detached=lambda arguments: (
                order.append(f"start:{' '.join(arguments)}"),
                True,
            )[1],
            quit_application=lambda: order.append("quit"),
        )

        assert started is True
        assert order == ["start:python app.py", "quit"]

    def test_a_failed_start_leaves_this_session_running(self) -> None:
        """A user left with no application at all is a worse outcome than a
        switch that needs a manual relaunch — and the setting is already on
        disk either way, so the next normal start picks it up."""
        quit_calls: list[int] = []

        started = restart_now(
            ["python", "app.py"],
            dev_mode_enabled=True,
            start_detached=lambda _arguments: False,
            quit_application=lambda: quit_calls.append(1),
        )

        assert started is False
        assert quit_calls == []
