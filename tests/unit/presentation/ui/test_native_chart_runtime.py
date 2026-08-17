from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import PySide6
import pytest

from Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_runtime import (
    NativeChartRuntimeError,
    resolve_native_chart_runtime,
)


def _write_runtime_fixture(import_root: Path, *, qt_version: str) -> None:
    module_dir = import_root / "Sagittarius" / "NativeChart"
    module_dir.mkdir(parents=True)
    (module_dir / "qmldir").write_text(
        "module Sagittarius.NativeChart\n", encoding="utf-8"
    )
    (import_root / "native-chart-runtime.json").write_text(
        json.dumps(
            {
                "module_uri": "Sagittarius.NativeChart",
                "module_version": "1.0",
                "snapshot_abi": 1,
                "qt_version": qt_version,
            }
        ),
        encoding="utf-8",
    )


def test_runtime_resolver_accepts_exact_pyside_abi(tmp_path):
    _write_runtime_fixture(tmp_path, qt_version=PySide6.__version__)

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_runtime._candidate_import_roots",
        return_value=(tmp_path,),
    ):
        runtime = resolve_native_chart_runtime(required=True)

    assert runtime is not None
    assert runtime.import_root == tmp_path
    assert runtime.qt_version == PySide6.__version__
    assert runtime.snapshot_abi == 1


def test_runtime_resolver_rejects_qt_abi_mismatch(tmp_path):
    _write_runtime_fixture(tmp_path, qt_version="0.0.0")

    with (
        patch(
            "Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_runtime._candidate_import_roots",
            return_value=(tmp_path,),
        ),
        pytest.raises(NativeChartRuntimeError, match="does not match PySide6"),
    ):
        resolve_native_chart_runtime(required=True)


def test_optional_runtime_resolution_keeps_production_fallback_explicit(tmp_path):
    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.native_chart_runtime._candidate_import_roots",
        return_value=(tmp_path,),
    ):
        runtime = resolve_native_chart_runtime(required=False)

    assert runtime is None
