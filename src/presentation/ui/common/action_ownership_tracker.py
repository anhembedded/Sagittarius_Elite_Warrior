from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Generic, Protocol, TypeVar

TKind = TypeVar("TKind")
TConfig = TypeVar("TConfig")
TState = TypeVar("TState")


class ActionOutcome(str, Enum):
    """Lifecycle outcome of a background action."""

    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    EMPTY = "EMPTY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INVALIDATED = "INVALIDATED"


class ActionTraceCallback(Protocol):
    """Protocol for logging diagnostic trace events from the tracker."""

    def __call__(self, action: str, **fields: object) -> None: ...


def _extract_field_value(val: object) -> object:
    if hasattr(val, "value"):
        return val.value
    return val


def _format_config_label(config: object) -> str:
    if hasattr(config, "to_summary_label") and callable(config.to_summary_label):
        return str(config.to_summary_label())
    return str(config)


@dataclass(frozen=True)
class ActionContext(Generic[TKind, TConfig, TState]):
    """Immutable owner record for one submitted background action."""

    action_id: int
    kind: TKind
    config: TConfig
    started_at: datetime
    previous_state: TState


class ActionOwnershipTracker(Generic[TKind, TConfig, TState]):
    """Tracks active async action generation, fencing, and lifecycle outcomes.

    Provides single-source-of-truth action identity to prevent race conditions
    and stale background callbacks from overwriting newer user intents.
    """

    def __init__(self, on_trace: ActionTraceCallback | None = None) -> None:
        self._on_trace = on_trace
        self._next_action_id = 0
        self._active_action: ActionContext[TKind, TConfig, TState] | None = None
        self._active_outcome: ActionOutcome | None = None

    @property
    def active_action(self) -> ActionContext[TKind, TConfig, TState] | None:
        """The currently active action context, if any."""
        return self._active_action

    @property
    def active_outcome(self) -> ActionOutcome | None:
        """The outcome of the currently active action, if any."""
        return self._active_outcome

    def begin_action(
        self,
        kind: TKind,
        config: TConfig,
        previous_state: TState,
    ) -> ActionContext[TKind, TConfig, TState]:
        """Create the immutable owner record before background submission."""
        if self._active_action is not None:
            self._trace(
                "action_superseded",
                action_id=self._active_action.action_id,
                kind=_extract_field_value(self._active_action.kind),
                outcome=(
                    self._active_outcome.value
                    if self._active_outcome is not None
                    else None
                ),
            )
            if self._active_outcome is ActionOutcome.PENDING:
                self.finish_action(
                    self._active_action.action_id, ActionOutcome.INVALIDATED
                )

        self._next_action_id += 1
        context = ActionContext[TKind, TConfig, TState](
            action_id=self._next_action_id,
            kind=kind,
            config=deepcopy(config),
            started_at=datetime.now(UTC),
            previous_state=previous_state,
        )
        self._active_action = context
        self._active_outcome = ActionOutcome.PENDING

        self._trace(
            "action_started",
            action_id=context.action_id,
            kind=_extract_field_value(context.kind),
            config=_format_config_label(context.config),
            previous_state=_extract_field_value(context.previous_state),
        )
        return context

    def is_current(self, action_id: int, kind: TKind) -> bool:
        """Verify if the action_id and kind match the currently active action."""
        return (
            self._active_action is not None
            and self._active_action.action_id == action_id
            and self._active_action.kind is kind
        )

    def is_current_pending(self, action_id: int, kind: TKind) -> bool:
        """Verify if the action is currently active, matching kind, and still PENDING."""
        return self.is_current(action_id, kind) and (
            self._active_outcome is ActionOutcome.PENDING
        )

    def current_action_id(self, kind: TKind) -> int | None:
        """Return the active action_id if matching kind, otherwise None."""
        if self._active_action is not None and self._active_action.kind is kind:
            return self._active_action.action_id
        return None

    def finish_action(self, action_id: int, outcome: ActionOutcome) -> bool:
        """Record the terminal outcome of an active action."""
        if self._active_action is None or self._active_action.action_id != action_id:
            return False

        self._active_outcome = outcome
        self._trace(
            "action_finished",
            action_id=action_id,
            kind=_extract_field_value(self._active_action.kind),
            outcome=outcome.value,
        )
        return True

    def invalidate_active(self) -> None:
        """Invalidate a pending action without assigning a replacement.

        Used in cancellation flows before requesting cooperative worker cancellation,
        so late callbacks are fenced immediately.
        """
        if (
            self._active_action is not None
            and self._active_outcome is ActionOutcome.PENDING
        ):
            self.finish_action(self._active_action.action_id, ActionOutcome.INVALIDATED)

    def log_stale_callback(self, callback: str, action_id: int, kind: TKind) -> None:
        """Log diagnostic trace when a stale callback is ignored."""
        self._trace(
            "action_callback_ignored",
            callback=callback,
            action_id=action_id,
            kind=_extract_field_value(kind),
            active_action_id=(
                self._active_action.action_id if self._active_action else None
            ),
            active_outcome=(
                self._active_outcome.value if self._active_outcome is not None else None
            ),
        )

    def _trace(self, action: str, **fields: object) -> None:
        if self._on_trace is not None:
            self._on_trace(action, **fields)
