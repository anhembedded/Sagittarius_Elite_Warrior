# EPIC-011A — `.jules/README.md`: hợp đồng context dùng chung

**Trạng thái:** ✅ Xong 2026-08-26
**Repo:** Elite (`Sagittarius_Elite_Warrior`)
**Phụ thuộc:** không — nhưng `B`–`F` đều link vào file này nên phải làm trước

## Vấn đề

7 prompt, mỗi file tự chép lại cùng một nửa nội dung: stack, lệnh CI, luật
commit, boundary, journal. Bảy bản sao của cùng một sự thật = bảy chỗ trôi độc
lập. Đây đúng là bệnh `CLAUDE.md` đã đặt tên (*"Không chép luật vào đây"*),
chỉ khác chỗ ở.

Hậu quả đo được: cả 7 file cùng ghi sai một chỗ — bắt agent chạy
`ci-local.ps1 -UnitOnly` rồi commit, trong khi `ci-rule.md` §1 nói nguyên văn
`-UnitOnly` *"is diagnostic-only and never sufficient for handoff or commit"*.
Sai ở một bản sao thì sửa một chỗ; sai ở bảy bản sao thì không ai sửa.

## Đã làm

Tạo `.jules/README.md`, là nửa dùng chung của cả 7 prompt:

| § | Nội dung |
| :--- | :--- |
| 1 | Luật **"verify, don't restate"** + danh sách thứ **bị cấm** viết trong `.jules/` (số đếm, ngày/phiên bản, bản chép luật, đường dẫn chưa kiểm) + bảng "thay vì viết X, hãy hỏi cây thư mục bằng lệnh Y" |
| 2 | Bối cảnh repo: 2 repo độc lập (`ls .gitmodules`), thứ tự đọc `CLAUDE.md` → `ONBOARDING.md` → rule liên quan, quy ước ngôn ngữ |
| 3 | **Cổng CI đúng**: `ci-local.ps1 -Full`, không phải `-UnitOnly`; bắt buộc đọc `LOG_FILE:` chứ không tin console; nói rõ phải làm gì khi không chạy được cổng |
| 4 | Commit: link `commit-rule.md`, cấm chép trailer, `commit` hỏi trước / `push` cấm mặc định |
| 5 | Journal: nói thẳng **chưa file nào tồn tại**, kèm lệnh tự kiểm |
| 6 | Boundary chung của cả 7 (always / ask first / never) |
| 7 | **Giữ cho có ý nghĩa**: mỗi agent phải tự quét ra việc; "không có việc" là kết quả đúng; nhiều lần chạy trống liên tiếp là tín hiệu về agent, không phải về repo |
| 8 | Lệnh chạy guard trước khi commit bất kỳ sửa đổi nào trong `.jules/` |

7 prompt còn lại mở đầu bằng một dòng đậm trỏ về file này và **chỉ** giữ phần
riêng của vai trò.

## Acceptance

- [x] `.jules/README.md` tồn tại, không chứa số đếm nào, không chép nguyên văn
      rule nào.
- [x] Cả 7 `*.prompt.md` link tới nó ở dòng đầu.
- [x] Cổng CI trong toàn bộ `.jules/` là `-Full`; `-UnitOnly` chỉ còn xuất hiện
      ở §3 đúng với vai trò "công cụ chẩn đoán".
- [x] `python3 scripts/check_jules_prompt_references.py` exit `0`.
