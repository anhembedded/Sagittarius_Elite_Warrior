# EPIC-011E — `scout.prompt.md` + `scribe.prompt.md`

**Trạng thái:** ✅ Xong 2026-08-26
**Repo:** Elite
**Phụ thuộc:** `EPIC-011A`

## `scout.prompt.md`

**Sai:** định nghĩa tầng Sanity là *"construction-only, assert
`quick_widget.errors() == []`"*. `.claude/skills/test-health/contract.json` gọi
thẳng đó là *"the retired `quick_widget.errors()` clause"* và đã có clause kế
nhiệm: quan sát **mọi kênh chẩn đoán** lúc boot (`qInstallMessageHandler`,
`logging`, `warnings`, và stderr qua tầng out-of-process `--self-check`). Đó là
kết quả của `EPIC-009`.

Agent test tự xác nhận bằng một điều kiện không còn được chạy — đúng loại lỗi
mà chính `EPIC-009` được lập ra để diệt.

**Đã làm:**
- Trỏ vào `contract.json` như **nửa máy đọc được** của `testing-rule.md` +
  `ci-rule.md`, kèm nguyên tắc thiết kế của tầng: *thêm một feature phải thêm
  **không** test Sanity nào*. Ý tưởng Sanity nào có nêu tên một màn hình thì
  thuộc về `tests/unit/`.
- Bãi săn neo vào `domain-truth-rule.md`: test phải khẳng định **ngữ nghĩa** chứ
  không phải hình dạng payload — signal / order intent / fill / entry / exit là
  các sự kiện domain khác nhau, và trong engine long-only `SELL` là *thoát lệnh*,
  không phải mở short. Một test xanh trên nhãn sai vẫn là bug thật.
- Thêm nguồn việc tự làm mới: `Tasks/bug_report/` là danh sách thứ **đã hỏng một
  lần**; `bug-fix-rule.md` bắt mỗi cái phải có regression test vĩnh viễn — tìm
  cái nào chưa có.
- Bắt buộc **chứng minh test có thể fail**: phá code, thấy đỏ, trả code về.

## `scribe.prompt.md`

**Sai:** không sai sự thật nhiều như các file khác, nhưng vô hướng — "tìm chỗ
nào dùng `Any`" là một bãi săn không bao giờ cạn và cũng không bao giờ đo được
tiến độ. Với một agent chạy định kỳ, đó là công thức của việc vô nghĩa.

**Đã làm:**
- Neo vào **`[tool.mypy]` trong `pyproject.toml`** — danh sách file đang được
  miễn trừ như nợ kỹ thuật, đóng băng ở baseline `EPIC-002A` đo được. Và neo vào
  [`EPIC-002D`](../../EPIC-002_static_type_checking_in_local_ci/incomplete/EPIC-002D_incremental_strictness_rollout.md),
  task con đang mở có nhiệm vụ **rút ngắn đúng danh sách đó**.
  Một file mỗi lần chạy — đúng cỡ một lần chạy, đo được, tự làm mới, và đẩy một
  epic đang sống tiến lên.
- Hai cảnh báo kèm theo: `src/presentation/` bị loại **nguyên khối** vì một
  false positive hệ thống của PySide6 `@Property` (cần quyết định stub/plugin,
  không phải sửa từng file) → đừng bắt đầu ở đó; và **không bao giờ** thêm dòng
  vào block đó để lần chạy pass.
- Bước verify: gỡ được một dòng khỏi block `mypy` **chính là** bằng chứng — cổng
  giờ kiểm file đó thật.

## Acceptance

- [x] `scout` không còn nhắc `quick_widget.errors()` như hợp đồng đang sống.
- [x] `scribe` có một hàng đợi việc đo được, tự làm mới, gắn với `EPIC-002D`.
- [x] Cả hai không còn con số test/coverage viết cứng.
- [x] Guard xanh.
