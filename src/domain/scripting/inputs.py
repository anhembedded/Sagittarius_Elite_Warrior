from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any


class InputKind(str, Enum):
    """
    @brief Which widget a declared parameter needs.
    @details Deliberately a small closed set rather than "any Python type":
    the UI has to render each one, so a kind that no widget maps to is a
    kind the modal cannot show (BOT-047).
    """

    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "string"


@dataclass(frozen=True)
class ScriptInput:
    """
    @brief One parameter a script or strategy declares about itself — the
    data a UI needs to build its form field without knowing anything about
    the script (BOT-044).

    @details This is the "declaration" half of Pine Script's `input()`: the
    call site both records one of these *and* returns a usable value, so the
    parameter is described in exactly the place it is used, never in a second
    list that can drift out of sync.

    `default` is kept even after the user overrides it, because "Khôi phục
    Mặc định" (Reset to defaults) has to come from the declaration — a UI
    that remembered only current values could never restore.
    """

    name: str
    label: str
    kind: InputKind
    default: Any
    minval: float | None = None
    maxval: float | None = None
    #: Allowed values for a STRING input — renders as a dropdown. None for
    #: free text.
    options: tuple[str, ...] | None = None
    #: Section heading in the settings modal (e.g. "Quản lý Rủi ro & Đòn
    #: bẩy"). None puts the field in the modal's default section.
    group: str | None = None
    #: Unit shown after the field ("%", "x"). Display only — never parsed.
    suffix: str | None = None


class InputDeclarations:
    """
    @brief Collects the `input_*()` calls a script makes during setup(), and
    resolves each against caller-supplied params.

    @details Split out of `BaseIndicatorScript` so `BaseStrategy` can reuse
    it verbatim (BOT-046) — the two base classes share no inheritance on
    purpose, but they do share this concern. Lives in `domain/scripting/`
    for the same reason `Series` does.

    Validation happens here, at declaration time, rather than in the UI:
    a param arriving from anywhere (UI, a saved preset, a test) must not be
    able to put a script into an impossible state. Bad values raise instead
    of being silently clamped, because a silently clamped period produces a
    backtest whose numbers look plausible and are wrong.
    """

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self._params: dict[str, Any] = dict(params or {})
        self._declared: dict[str, ScriptInput] = {}

    @property
    def declared(self) -> tuple[ScriptInput, ...]:
        """Declarations in the order `setup()` made them — the order the UI
        should render fields in."""
        return tuple(self._declared.values())

    def unused_param_names(self) -> tuple[str, ...]:
        """Param keys nobody declared. Sorted so the error message is stable."""
        return tuple(sorted(set(self._params) - set(self._declared)))

    def declare(self, spec: ScriptInput) -> Any:
        """Records `spec` and returns the value to use — the caller's param
        when supplied and valid, otherwise the declared default."""
        if spec.name in self._declared:
            raise ValueError(f"Input {spec.name!r} is declared twice")
        self._declared[spec.name] = spec

        if spec.name not in self._params:
            return spec.default
        return _coerce(spec, self._params[spec.name])


def _coerce(spec: ScriptInput, raw: Any) -> Any:
    """Validates a supplied value against its declaration, returning the
    value in its declared type. Raises ValueError on anything unusable."""
    if spec.kind is InputKind.BOOL:
        if not isinstance(raw, bool):
            raise ValueError(f"Input {spec.name!r} expects a bool, got {raw!r}")
        return raw

    if spec.kind is InputKind.STRING:
        if not isinstance(raw, str):
            raise ValueError(f"Input {spec.name!r} expects a string, got {raw!r}")
        if spec.options is not None and raw not in spec.options:
            raise ValueError(
                f"Input {spec.name!r} must be one of {list(spec.options)}, got {raw!r}"
            )
        return raw

    # Numeric. bool is a subclass of int in Python, so it has to be rejected
    # explicitly or `True` would silently become the number 1.
    #
    # ValueError, not TypeError (what ruff's TRY004 would prefer), on purpose:
    # every failure in this function is "the supplied value is unusable", and
    # values arrive from untrusted places (UI fields, saved presets, JSON).
    # One exception type means the caller — the settings modal in BOT-047 —
    # catches one thing to show one inline error, instead of catching two and
    # having to explain the difference to a user who cannot act on it.
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(  # noqa: TRY004
            f"Input {spec.name!r} expects a number, got {raw!r}"
        )

    if spec.kind is InputKind.INT:
        if isinstance(raw, float) and not raw.is_integer():
            raise ValueError(f"Input {spec.name!r} expects a whole number, got {raw!r}")
        value: int | float = int(raw)
    else:
        value = float(raw)

    if spec.minval is not None and value < spec.minval:
        raise ValueError(f"Input {spec.name!r} must be >= {spec.minval}, got {value}")
    if spec.maxval is not None and value > spec.maxval:
        raise ValueError(f"Input {spec.name!r} must be <= {spec.maxval}, got {value}")
    return value


def build_input(
    kind: InputKind,
    name: str,
    default: Any,
    label: str | None,
    minval: float | None = None,
    maxval: float | None = None,
    options: Sequence[str] | None = None,
    group: str | None = None,
    suffix: str | None = None,
) -> ScriptInput:
    """Shared constructor for the `input_*()` helpers — keeps the label
    fallback and the options tuple conversion in one place instead of
    repeated in every helper on both base classes."""
    return ScriptInput(
        name=name,
        label=label if label is not None else name,
        kind=kind,
        default=default,
        minval=minval,
        maxval=maxval,
        options=tuple(options) if options is not None else None,
        group=group,
        suffix=suffix,
    )
