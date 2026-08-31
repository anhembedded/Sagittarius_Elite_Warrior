---
name: Commit Rule
description: Không commit khi chưa được yêu cầu, verify trước commit, Conventional Commits, chữ ký AI đúng danh tính, commit nguyên tử.
trigger: always_on
---

# Git Commit Guidelines cho AI Agent

Mọi AI assistant làm việc trên repo này PHẢI tuân thủ nghiêm ngặt, không ngoại
lệ.

---

## 0. Không bao giờ commit khi user chưa yêu cầu

- **KHÔNG tự ý `git commit`.** Luôn chờ user cho phép tường minh trước khi ghi
  thay đổi vào version control.
- **`git push` là mặc định-CẤM** — chỉ khi user yêu cầu rõ ràng, và mỗi repo
  là một lần xác nhận riêng.

---

## 1. Bắt buộc verify trước commit

- **Không bao giờ commit code hỏng, chưa test, hay đang fail.**
- Trước mỗi `git commit`, agent PHẢI chạy `<CI_CMD>` và bảo đảm:
  - **toàn bộ test pass**, zero failure, zero error;
  - **zero warning của chính dự án** — không rò tài nguyên, không coroutine bị
    bỏ quên, không kết nối chưa đóng;
  - lint/format/type check/coverage đều xanh.
- **Ngoại lệ:** commit không đụng file code nào — xem
  [`ci-rule.md`](ci-rule.md) §1 để biết ranh giới chính xác.

---

## 2. Định dạng commit message (Conventional Commits)

```
<type>(<scope>): <chủ đề ngắn, thì hiện tại, thể mệnh lệnh>

<thân tuỳ chọn: bối cảnh, lý do, thay đổi cụ thể>

- <module>: chi tiết thay đổi
- <tests>: test mới / coverage mới

Co-Authored-By: <tên và danh tính AI thật sự tạo ra commit này>
```

### Type được dùng

| Type | Dùng khi |
| :--- | :--- |
| `feat` | Tính năng mới / khả năng mới người dùng thấy được |
| `fix` | Sửa bug — **phải** nhắc root cause hoặc mã bug |
| `refactor` | Đổi cấu trúc, không thêm tính năng, không sửa bug |
| `perf` | Cải thiện hiệu năng |
| `test` | Chỉ thêm/sửa test |
| `ci` | Script CI, test runner, môi trường |
| `docs` | Chỉ tài liệu |
| `style` | Chỉ format/lint, không đổi hành vi |
| `chore` | Bảo trì, cấu hình, dependency |

**Scope** là một danh sách ngắn, chốt theo repo (`<SCOPES>`).

---

## 3. Chữ ký AI bắt buộc — đúng danh tính

Mọi commit do AI tạo ra PHẢI có trailer ở **cuối cùng** message, ghi đúng
assistant thật sự tạo ra nó:

```
Co-Authored-By: <Assistant Name> <noreply@assistant-provider.example>
```

**Không bao giờ hard-code tên một công cụ khác, và không bao giờ dùng
placeholder.** Gán nhầm quyền tác giả cho một công cụ không tạo ra commit là
**không chấp nhận được**, kể cả để "nhất quán với lịch sử commit cũ".

> **Bằng chứng thật:** ở repo gốc, một file hướng dẫn từng hard-code trailer
> của một công cụ AI **khác** — vi phạm thẳng chính file này — và tồn tại đủ
> lâu để đi vào lịch sử commit. Không ai phát hiện vì nó nằm trong một **bản
> sao trôi** của rule chứ không phải trong bản gốc.

*(Để một dòng trống trước trailer.)*

---

## 4. Commit nguyên tử & sạch

- **Một thay đổi logic một commit.** Không gộp tính năng, refactor lớn, và
  sửa bug vào một commit khổng lồ.
- **Không bao giờ commit:**
  - file rác/tạm, script test dùng một lần, thư mục scratch;
  - log debug còn sót, code chết đã comment, mock tạm;
  - môi trường ảo, file database, artifact build.
- **Không lazy import**, **không magic number** trong code được commit — xem
  [`code-quality-rule.md`](code-quality-rule.md).

---

## 5. Commit sửa bug

Quy trình đầy đủ ở [`bug-fix-rule.md`](bug-fix-rule.md). Hai điều bắt buộc ở
mức commit:

- Commit sửa bug **PHẢI chứa regression test** — không bao giờ sửa mà không
  kèm test, không bao giờ tách test ra một commit sau.
- **Nêu rõ root cause trong thân commit:** cái gì gây ra bug, và vì sao bản sửa
  này giải quyết nó một cách sạch sẽ.

---

## 6. Nhánh cũ & giải quyết conflict

Trước khi resolve/merge một nhánh (nhất là nhánh do tự động sinh ra):

1. **Kiểm giá trị:** thay đổi của nhánh còn liên quan không, hay đã được merge
   rồi? Bỏ qua nhánh cũ, trùng, hoặc 0 giá trị.
2. **Resolve cẩn thận:** không tái nhập lại pattern lỗi thời hay dòng trùng lặp
   theo marker conflict.
3. **Verify:** luôn chạy `<CI_CMD>` **trên trạng thái đã merge** trước khi
   push.
