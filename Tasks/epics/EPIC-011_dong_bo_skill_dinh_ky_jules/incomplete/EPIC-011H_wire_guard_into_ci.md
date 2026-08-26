# EPIC-011H — Nối guard `.jules/` vào cổng CI

**Trạng thái:** 🔴 Chưa làm
**Repo:** Elite
**Phụ thuộc:** `EPIC-011G` ✅

## Việc

`scripts/check_jules_prompt_references.py` hiện chỉ chạy khi có người gõ tay.
Một guard chạy tay là một guard sẽ bị quên — đúng cơ chế đã để `sentinel-rule.md`
sống sót hàng tháng trong prompt.

Nối nó vào cổng để nó thật sự chặn.

## Hai hướng, chọn một

| Hướng | Ưu | Nhược |
| :--- | :--- | :--- |
| **A — bước riêng trong `ci-local.ps1 -Full`** | Cùng chỗ với `ruff`/`mypy`; thông báo lỗi đọc thẳng được | Thêm một bước vào script đã dài; phải quyết định nó chạy ở tier nào |
| **B — một test unit** (ví dụ `tests/unit/test_jules_prompt_references.py` gọi `check()`) | Không đụng `ci-local.ps1`; chạy sẵn ở mọi tier có unit test | `tests/conftest.py` có fixture `autouse` session-scope import PySide6 + `sagittarius_engine`, nên test này **không** chạy được ở môi trường không có Qt — cần cân nhắc |

Khuyến nghị: **A**. Guard không cần Qt, không cần engine, chạy trong ~mili-giây;
nhét nó vào tier test kéo theo toàn bộ điều kiện boot của tier đó mà không được
gì. Nhưng đọc `ci-rule.md` §1 và cấu trúc `ci-local.ps1` trước khi chốt — script
đó tự nhận là **nguồn sự thật duy nhất** cho verification cục bộ.

## Vì sao chưa làm trong phiên tạo epic

Không verify được. Môi trường phiên đó không có `pwsh`, không có `.venv`, không
có `PySide6`, và repo `sagittarius_engine` không nằm trên đĩa — nên không chạy
được `ci-local.ps1 -Full` để chứng minh bước mới không làm hỏng cổng. Sửa
`ci-local.ps1` mà không chạy được chính nó là đúng thứ `ci-rule.md` cấm.

## Acceptance

- [ ] `ci-local.ps1 -Full` fail khi `.jules/` có tham chiếu gãy.
- [ ] `-Full` vẫn xanh trên cây sạch, **có đọc file `LOG_FILE:`** để xác nhận
      (không tin console — `CLAUDE.md` §2).
- [ ] Bước mới xuất hiện trong log với nhãn đọc được, giống các bước tĩnh khác.
- [ ] Ghi nhận cổng mới vào `ci-rule.md` (cùng lúc, hoặc gộp với `EPIC-004C`
      đang mở — task đó cũng là "ghi nhận cổng mới vào rule").
