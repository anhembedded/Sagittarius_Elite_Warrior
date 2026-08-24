# BUG-043 — `run-ui.ps1` không import được Sagittarius Engine local

**Trạng thái:** ✅ Đã sửa (2026-08-24)
**Phát hiện:** 2026-08-24, khi chạy `scripts/run-ui.ps1`

## 1. Symptom

`run-ui.ps1` cài dependencies thành công nhưng UI dừng ngay khi khởi động:

```text
ModuleNotFoundError: No module named 'sagittarius_engine'
```

## 2. Root cause

Trong workspace local, hai repo độc lập nằm cạnh nhau:

```text
Claude/
├── Sagittarius_Elite_Warrior/
└── Sagittarius_Engine/sagittarius_engine/
```

Script chỉ cài `requirements.txt`, trong khi file này không chứa Sagittarius
Engine. Vì vậy virtualenv mới không có package `sagittarius_engine`; việc chỉ
đưa `Claude/` vào `PYTHONPATH` cũng không trỏ tới sibling repository.

## 3. Fix

`scripts/run-ui.ps1` nay phát hiện sibling checkout `Sagittarius_Engine`, cài nó
ở editable mode (`pip install -e`) và thêm repo root vào `PYTHONPATH`. Khi sibling
checkout không tồn tại, script cài engine từ GitHub theo `install-rule.md`.

## 4. Regression verification

- PowerShell parser: `0` syntax errors.
- Với `PYTHONPATH` gồm workspace root và `Sagittarius_Engine`, import thật:
  `import sagittarius_engine` — **PASS**.
- Import entry module ở `QT_QPA_PLATFORM=offscreen` — **PASS**:
  `import Sagittarius_Elite_Warrior.src.presentation.ui.main_window`.
