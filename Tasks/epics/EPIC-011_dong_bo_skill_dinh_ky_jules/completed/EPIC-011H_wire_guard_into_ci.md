# EPIC-011H — Nối guard `.jules/` vào cổng CI

**Trạng thái:** ✅ Xong 2026-08-26
**Repo:** Elite
**Phụ thuộc:** `EPIC-011G` ✅

## Việc

`scripts/check_jules_prompt_references.py` chỉ chạy khi có người gõ tay. Một
guard chạy tay là một guard sẽ bị quên — đúng cơ chế đã để một `sentinel-rule.md`
không tồn tại sống sót hàng tháng trong prompt của Sentinel.

## Đã chọn hướng A — bước riêng trong `ci-local.ps1`

Đặt cạnh 3 cổng tĩnh khác (`ruff check` → `ruff format` → `mypy` → **guard**),
bên trong khối `if (-not $SkipLint)`. Nghĩa là nó chạy ở `-Full` — cổng bắt
buộc — và không chạy ở `-UnitOnly`/`-SanityOnly` (hai chế độ chẩn đoán, đều tự
set `$SkipLint`).

**Không chọn hướng B (một test unit).** Guard không cần Qt, không cần engine,
chạy trong mili-giây; nhét vào tier test kéo theo toàn bộ điều kiện boot của
tier đó — `tests/conftest.py` có fixture `autouse` session-scope import PySide6
và `sagittarius_engine` — mà không được gì thêm.

Dùng `$pythonExe` (Python của venv mà script đã tự phân giải), không phải
`python3` hệ thống, để bước này đi cùng interpreter với phần còn lại của cổng.

## Verify — hai chiều

**Chiều xanh:**

```bash
pwsh -NoProfile -File scripts/ci-local.ps1 -Full -SkipTests   # EXIT=0
#   ✅  Ruff Lint passed
#   ✅  Ruff Format passed
#   ✅  Mypy passed
#   ✅  Jules Prompt References passed      ← bước mới
```

**Chiều đỏ (fault injection):** thêm một tham chiếu gãy cố ý
(`.agents/rules/ghost-rule.md`) vào `doctor.prompt.md` →

```
EXIT=1
  Broken references in .jules/ prompts:
    .jules/doctor.prompt.md: .agents/rules/ghost-rule.md
  ❌  Jules Prompt References FAILED
```

Đã khôi phục file ngay sau đó; `git diff` sạch.

**Cổng đầy đủ:** `ci-local.ps1 -Full` (có test) exit `0` — ruff, format, mypy,
guard, 2287 passed / 4 skipped, Sanity passed, coverage 94.29% ≥ 80%, và bước
"Run Log Scan" báo không có WARNING/ERROR/CRITICAL. Đã `grep` file `LOG_FILE:`
cho `FAILED|ERROR|Traceback|ResourceWarning` theo đúng `CLAUDE.md` §2 — chỉ khớp
2 dòng, cả hai là **nhãn của chính bước log scan**, không phải lỗi.

## Ghi nhận cổng mới

`ci-rule.md` §1 (danh sách "`-Full` runs") đã có mục cho bước này, kèm lý do vì
sao nó không nằm ở tier test. **Không** gộp vào `EPIC-004C` — task đó là ghi
nhận cổng bảo mật Ruff, phạm vi khác, vẫn đang mở.

## Acceptance

- [x] `ci-local.ps1 -Full` fail khi `.jules/` có tham chiếu gãy.
- [x] `-Full` vẫn xanh trên cây sạch, **có đọc file `LOG_FILE:`** để xác nhận.
- [x] Bước mới xuất hiện trong log với nhãn đọc được, giống các bước tĩnh khác.
- [x] Ghi nhận cổng mới vào `ci-rule.md`.
