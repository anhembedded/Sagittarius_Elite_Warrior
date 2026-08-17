"""Discovery boundary for the native Sagittarius QML chart module."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import PySide6
from PySide6.QtCore import QLibrary
from PySide6.QtQml import QQmlEngine

_MODULE_RELATIVE_DIR = Path("Sagittarius") / "NativeChart"
_MANIFEST_NAME = "native-chart-runtime.json"
_IMPORT_PATH_ENV = "QML_IMPORT_PATH"
_OVERRIDE_ENV = "SAGITTARIUS_NATIVE_QML_IMPORT_PATH"
_EXPECTED_MODULE_URI = "Sagittarius.NativeChart"
_EXPECTED_SNAPSHOT_ABI = 1
_UI_DIR = Path(__file__).resolve().parent
_BOT_ROOT = _UI_DIR.parents[2]
_DLL_DIRECTORY_HANDLES: list[object] = []
_DLL_DIRECTORIES: set[Path] = set()
_NATIVE_LIBRARIES: list[QLibrary] = []


class NativeChartRuntimeError(RuntimeError):
    """Raised when the native chart plugin cannot safely join the Qt runtime."""


@dataclass(frozen=True, slots=True)
class NativeChartRuntime:
    """Validated QML import root and its native ABI metadata."""

    import_root: Path
    qt_version: str
    snapshot_abi: int


def resolve_native_chart_runtime(
    *, required: bool = False
) -> NativeChartRuntime | None:
    """Return the first ABI-compatible native chart runtime candidate."""
    errors: list[str] = []
    for import_root in _candidate_import_roots():
        module_dir = import_root / _MODULE_RELATIVE_DIR
        if not (module_dir / "qmldir").is_file():
            continue
        try:
            return _read_and_validate_runtime(import_root)
        except NativeChartRuntimeError as error:
            errors.append(f"{import_root}: {error}")

    if not required:
        return None

    details = "\n".join(errors) if errors else "No generated qmldir was found."
    raise NativeChartRuntimeError(
        "Sagittarius.NativeChart is required but unavailable. "
        "Run `.\\scripts\\build-native-chart.ps1` first.\n"
        f"{details}"
    )


def configure_native_chart_engine(
    engine: QQmlEngine, *, required: bool = False
) -> NativeChartRuntime | None:
    """Add the validated module root to one QML engine."""
    runtime = resolve_native_chart_runtime(required=required)
    if runtime is not None:
        _configure_native_dll_directory(runtime)
        engine.addImportPath(str(runtime.import_root))
    return runtime


def configure_native_chart_environment(
    *, required: bool = False
) -> NativeChartRuntime | None:
    """Expose the validated import root to QML engines created afterwards."""
    runtime = resolve_native_chart_runtime(required=required)
    if runtime is None:
        return None

    _configure_native_dll_directory(runtime)
    existing_paths = [
        path for path in os.environ.get(_IMPORT_PATH_ENV, "").split(os.pathsep) if path
    ]
    import_root = str(runtime.import_root)
    if import_root not in existing_paths:
        os.environ[_IMPORT_PATH_ENV] = os.pathsep.join([import_root, *existing_paths])
    return runtime


def _candidate_import_roots() -> tuple[Path, ...]:
    override = os.environ.get(_OVERRIDE_ENV)
    candidates = [
        Path(override) if override else None,
        _UI_DIR / "native_qml",
        _BOT_ROOT / "build" / "native-chart" / "qml",
    ]
    if getattr(sys, "frozen", False):
        candidates.insert(1, Path(sys.executable).resolve().parent / "qml")

    unique_candidates: list[Path] = []
    for candidate in candidates:
        if candidate is None:
            continue
        resolved_candidate = candidate.expanduser().resolve()
        if resolved_candidate not in unique_candidates:
            unique_candidates.append(resolved_candidate)
    return tuple(unique_candidates)


def _read_and_validate_runtime(import_root: Path) -> NativeChartRuntime:
    manifest_path = import_root / _MANIFEST_NAME
    if not manifest_path.is_file():
        raise NativeChartRuntimeError(f"missing {_MANIFEST_NAME}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        module_uri = str(manifest["module_uri"])
        qt_version = str(manifest["qt_version"])
        snapshot_abi = int(manifest["snapshot_abi"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise NativeChartRuntimeError("invalid runtime manifest") from error

    if module_uri != _EXPECTED_MODULE_URI:
        raise NativeChartRuntimeError(f"unexpected module URI {module_uri!r}")
    if qt_version != PySide6.__version__:
        raise NativeChartRuntimeError(
            f"Qt SDK {qt_version} does not match PySide6 {PySide6.__version__}"
        )
    if snapshot_abi != _EXPECTED_SNAPSHOT_ABI:
        raise NativeChartRuntimeError(
            f"snapshot ABI {snapshot_abi} is unsupported; expected {_EXPECTED_SNAPSHOT_ABI}"
        )
    return NativeChartRuntime(import_root, qt_version, snapshot_abi)


def _configure_native_dll_directory(runtime: NativeChartRuntime) -> None:
    module_dir = runtime.import_root / _MODULE_RELATIVE_DIR
    if module_dir in _DLL_DIRECTORIES:
        return

    if sys.platform == "win32":
        handle = os.add_dll_directory(str(module_dir))
        _DLL_DIRECTORY_HANDLES.append(handle)

    backing_library = QLibrary(str(module_dir / "sagittarius_native_chart"))
    if not backing_library.load():
        raise NativeChartRuntimeError(
            "could not load native chart backing library: "
            f"{backing_library.errorString()}"
        )
    _NATIVE_LIBRARIES.append(backing_library)
    _DLL_DIRECTORIES.add(module_dir)
