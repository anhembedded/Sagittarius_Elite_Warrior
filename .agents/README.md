# `.agents/` — bộ quy tắc làm việc cho AI agent (bản dùng chung cho mọi dự án)

Thư mục này là **template**. Copy nguyên nó vào bất kỳ repo nào, thay các
placeholder ở §2, xoá phần không dùng, là xong.

Nó không phải bộ sưu tập "best practice" chép từ sách. Mọi luật ở đây tồn tại
vì đã có một lớp lỗi thật đi qua nó. Phần *ví dụ cụ thể* đã bị lược đi cho
trung lập; phần *cơ chế* thì giữ nguyên.

---

## 1. Có gì trong đây

| File | Nội dung | Khi nào đọc |
| :--- | :--- | :--- |
| [`ONBOARDING.md`](ONBOARDING.md) | Bản đồ quy trình: vòng đời task/bug, verification, bookkeeping, quyền hạn, các bẫy | **Luôn luôn, đầu tiên** |
| [`AGENTS.md`](AGENTS.md) | Stub điều hướng: chủ đề → file rule | Khi cần tìm luật theo chủ đề |
| [`Handover.md`](Handover.md) | Trạng thái phiên gần nhất — file **thay mới mỗi phiên** | Ngay sau `ONBOARDING.md` |
| [`rules/architecture-rule.md`](rules/architecture-rule.md) | SOLID, tầng, Port/interface, hợp đồng tường minh, tách theo abstraction level, đặt chỗ event | Khi đụng kiến trúc |
| [`rules/code-quality-rule.md`](rules/code-quality-rule.md) | Typing, readability, immutability, magic number, God object, cohesion | Mọi thay đổi code |
| [`rules/testing-rule.md`](rules/testing-rule.md) | *Cách viết* test cho đúng | Khi viết test |
| [`rules/ci-rule.md`](rules/ci-rule.md) | *Cách chạy* cổng verification, 4 tầng test, xử lý khi đỏ | Trước khi tuyên bố "xong" |
| [`rules/commit-rule.md`](rules/commit-rule.md) | Conventional Commits, kiểm tra trước commit, chữ ký AI | Trước mọi commit |
| [`rules/bug-fix-rule.md`](rules/bug-fix-rule.md) | Quy trình sửa bug bắt buộc | **Khi user báo bug** |
| [`rules/logging-rule.md`](rules/logging-rule.md) | Đặt log ở đâu để bug tự khai nguyên nhân | Khi thêm/sửa log |
| [`rules/async-action-rule.md`](rules/async-action-rule.md) | Sở hữu tác vụ nền, stale callback, cancellation | Khi có việc chạy nền do user khởi tạo |
| [`rules/ui-rule.md`](rules/ui-rule.md) | Tầng presentation: view thuần khai báo, responsive, injection defense | Khi đụng UI |
| [`rules/domain-truth-rule.md`](rules/domain-truth-rule.md) | Hệ thống không được nói dối về thứ nó đã làm | Khi đụng domain/nghiệp vụ |
| [`rules/environment-rule.md`](rules/environment-rule.md) | Dựng môi trường là việc của agent; ranh giới cài đặt vs thêm dependency | Khi thiếu công cụ để verify |

Xoá thẳng file nào dự án không cần (không có UI → xoá `ui-rule.md` và
`async-action-rule.md`). **Xoá thì phải xoá cả dòng trỏ tới nó** ở
`AGENTS.md` và `ONBOARDING.md` §1 — link gãy trong tài liệu agent là thứ
lặng lẽ nhất: agent đọc không thấy file, tự bịa ra luật.

---

## 2. Placeholder phải thay trước khi dùng

`grep -rn --exclude=README.md '<[A-Z_]\+>' .agents/` liệt kê hết chỗ còn phải
thay (bảng dưới đây luôn tự khớp, nên loại nó ra). Không còn hit nào là xong.

| Placeholder | Nghĩa | Ví dụ |
| :--- | :--- | :--- |
| `<SRC_DIR>` | Thư mục mã nguồn chính | `src/`, `app/`, `lib/` |
| `<TEST_DIR>` | Thư mục test | `tests/`, `spec/` |
| `<CI_CMD>` | **Một** lệnh chạy toàn bộ cổng verification | `make ci`, `npm run ci`, `./scripts/ci-local.sh` |
| `<LINT_CMD>` | Lint + format ở chế độ **chỉ đọc** | `ruff check . && ruff format --check .` |
| `<TYPECHECK_CMD>` | Kiểm kiểu tĩnh (bỏ nếu ngôn ngữ không có) | `mypy src scripts`, `tsc --noEmit` |
| `<TASKS_DIR>` | Nơi chứa task/bug | `Tasks/`, `docs/tasks/` |
| `<TASK_ID>` | Tiền tố mã task | `TASK`, `BOT`, `PROJ` |
| `<BUG_ID>` | Tiền tố mã bug | `BUG` |
| `<LOG_NAMESPACE>` | Namespace logger gốc của app | `App`, `acme` |
| `<SCOPES>` | Danh sách scope hợp lệ của commit | `ui, api, domain, infra, ci` |
| `<DOC_LANG>` / `<UI_LANG>` | Ngôn ngữ tài liệu / ngôn ngữ chuỗi UI | `tiếng Việt` / `tiếng Việt` |

---

## 3. Ba luật không được sửa khi đem đi

Chúng là thứ đắt nhất trong bộ này — mọi luật khác chỉ là chi tiết:

1. **Không tin exit code, đọc file log.** Một lệnh có thể exit `0` trong khi
   ghi WARNING/ERROR mô tả một đường chạy đã hỏng lặng lẽ.
   (`ci-rule.md` §5)
2. **Regression test viết TRƯỚC khi sửa bug, và phải xác nhận nó fail đúng
   lý do.** Test viết sau không chứng minh gì. (`bug-fix-rule.md` §3)
3. **Không `commit` khi user chưa yêu cầu; không `push` khi user chưa yêu
   cầu rõ ràng.** (`ONBOARDING.md` §6)

---

## 4. Cách bộ rule này tự mục ruỗng — và cách chặn

Kinh nghiệm thật từ repo gốc, giữ lại vì nó sẽ lặp lại ở repo của bạn:

- **Bản sao trôi.** Chép nội dung một rule sang file thứ hai (`CLAUDE.md`,
  `README`, prompt của agent) → sửa một nơi, quên nơi kia → hai bản mâu
  thuẫn, và bản sai vẫn được đọc. **Luôn trỏ link, không bao giờ chép.**
- **Con số cứng trong tài liệu.** "9 file rule", "1641 test", "14 lỗi lint"
  — trôi trong vài giờ. Viết **lệnh đếm** thay cho con số.
- **Link tới file không tồn tại.** Đã có prompt trỏ vào một file rule chưa
  bao giờ tồn tại và chạy hàng tháng mà không ai biết, vì agent chạy không
  người trông vẫn báo thành công. Nếu repo có agent tự động: thêm một test
  duyệt mọi đường dẫn xuất hiện trong `.agents/` và đỏ khi có link gãy.
- **Luật chỉ sống trong prose.** Xem `architecture-rule.md` §7: cái gì hoãn
  lại hoặc đánh đổi thì phải có **type hoặc test** đại diện, không chỉ một
  đoạn văn.
