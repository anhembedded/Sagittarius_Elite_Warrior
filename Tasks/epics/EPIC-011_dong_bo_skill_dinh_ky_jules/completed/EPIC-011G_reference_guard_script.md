# EPIC-011G — `scripts/check_jules_prompt_references.py`

**Trạng thái:** ✅ Xong 2026-08-26 — script chạy được, đã bắt lỗi thật
**Repo:** Elite
**Phụ thuộc:** `A`–`F` (guard phải xanh sau khi 7 prompt đã sửa)

## Vì sao cần

Lớp 1 và 2 của epic (§3 README) sửa nội dung. Không có gì ngăn nó trôi lại lần
nữa — và repo này đã trôi **hai lần** với `AGENTS.md`/`code-rule.md`. Guard là
lớp cơ học: nó không biết một câu đã lỗi thời, nhưng bắt đúng lớp lỗi **đã thật
sự ship**: prompt trỏ vào file không tồn tại.

## Cơ chế

Đọc mọi `.jules/*.md`, rút ra:
- mọi đoạn trong backtick, và
- mọi đích của markdown link (resolve tương đối từ `.jules/`),

rồi fail nếu có cái nào không tồn tại trên đĩa.

Hai quyết định thiết kế đáng ghi lại, cả hai đều để guard **không** cần một danh
sách ngoại lệ (ngoại lệ cũng là một dạng hardcode và cũng sẽ trôi):

1. **Chỉ kiểm đường dẫn dưới các thư mục gốc của repo** (`CHECKED_ROOTS`:
   `.agents/`, `.github/`, `.jules/`, `Docs/`, `Tasks/`, `scripts/`, `src/`,
   `tests/`). Nhờ vậy prompt vẫn nói được về `package.json` (để khẳng định repo
   **không** có) và về `sagittarius_engine/` (repo khác, không nằm trên đĩa này)
   mà không bị báo thiếu.
2. **Bỏ qua mọi thứ không phải đường dẫn literal** — có khoảng trắng, `*`, `<>`,
   `|`, `$`, ngoặc, hay `http:`. Đó là lý do journal được viết là
   `.jules/<agent>.md`: nó đọc ra là *mẫu*, không phải một khẳng định "file này
   có tồn tại". Prompt nào cần nhắc tới một file **cố ý không tồn tại** (ví dụ
   cảnh báo của Sentinel) thì viết theo cùng cách đó.

## Bằng chứng nó hoạt động

Chạy lần đầu, trên 7 prompt chưa sửa, nó bắt đúng toàn bộ lỗi mà epic này tìm ra
bằng tay — trong đó có `.agents/rules/sentinel-rule.md` (file ma) và 7 journal
chưa bao giờ tồn tại. Sau `A`–`F`: exit `0`.

## Verify

**Đã qua `ci-local.ps1 -Full` thật** (26/08, sau khi dựng được môi trường —
xem `EPIC-011H`): exit `0`, và file `LOG_FILE:` sạch `FAILED|ERROR|Traceback|
ResourceWarning` đúng theo `CLAUDE.md` §2.

> *Bản đầu của task này ghi "chưa chạy được `-Full`" vì phiên đó không có
> `pwsh`/`.venv`/PySide6. Giới hạn đó đã được gỡ ngay trong cùng epic; giữ lại
> dòng này để không ai đọc lịch sử rồi tưởng cổng chưa từng chạy.*

## Acceptance

- [x] `python3 scripts/check_jules_prompt_references.py` exit `0` trên cây hiện tại.
- [x] Exit `1` kèm danh sách rõ ràng khi có tham chiếu gãy (đã chứng minh trên
      trạng thái trước khi sửa).
- [x] Không có danh sách ngoại lệ theo tên file.
- [x] `ruff`, `ruff format`, `mypy` sạch.
