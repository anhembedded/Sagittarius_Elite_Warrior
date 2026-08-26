# EPIC-011D — `doctor.prompt.md` + `janitor.prompt.md`

**Trạng thái:** ✅ Xong 2026-08-26
**Repo:** Elite
**Phụ thuộc:** `EPIC-011A`

Gộp 2 file vì cùng một loại lệch: stack ghi "PySide6/QML", bước verify dựa vào
`.qml`, và không neo vào epic nào đang sống.

## `doctor.prompt.md`

**Sai:** ghi cứng *"839+ Unit tests + 21 Sanity tests"*. `ls tests/sanity/` cho
6 file test, và `EPIC-009` đã xây lại toàn bộ tầng đó — con số này không thể
đúng. `ONBOARDING.md` §8 mục 2 đã ghi: số đếm kiểu này sai **3 lần liên tiếp**
trong repo (10 → 9 → 8 → thực tế 7 file rule).

**Đã làm:**
- Bỏ mọi con số. Bước verify giờ là "chạy cổng, đọc log của chính lần chạy đó".
- Neo vào [`EPIC-003`](../../EPIC-003_presenter_and_god_file_decomposition/README.md)
  làm brief thường trực — epic phân rã god file/Presenter chính là việc của
  Doctor, đọc bảng task con mỗi lần chạy trước khi tự nghĩ ra refactor rời rạc.
- Thêm mục "đã có máy kiểm": Ruff `SIM`/`B`/`ERA`/`PLR2004`/`N` + `mypy` đã bắt
  dead code, magic number, nhánh rút gọn được → giá trị của Doctor là thứ không
  rule nào chấm được (một hàm làm 5 việc, một khái niệm lặp 3 hình dạng, một phụ
  thuộc chỉ sai chiều qua tầng).
- Thêm `async-ui-action-rule.md` vào authority — Coordinator Pattern là thứ phải
  đọc trước khi phân rã bất cứ gì chạm Presenter.
- Siết luật "behaviour-preserving": test cũ phải pass **không sửa**; phải sửa
  test nghĩa là đã đổi hành vi, và đó là loại việc khác.

## `janitor.prompt.md`

**Sai:** bước "verify zero callers" yêu cầu tìm trong *"tất cả file `.qml`"*.
Không còn file nào — nên bước chống-xoá-nhầm trả về 0 hit và **đọc y hệt như
bằng chứng an toàn**. Đây là dạng lỗi nguy hiểm nhất trong cả 7 prompt: nó
không làm agent bó tay, nó làm agent tự tin sai.

**Đã làm:**
- Viết lại toàn bộ phần rủi ro theo cơ chế động **thật** của app hiện nay: DI
  container, `EventRegistry` của `EPIC-008`, mô hình *scan chứ không liệt kê*
  của `EPIC-009`, indicator script nạp theo convention, và tra cứu tên/slot của
  Qt.
- Câu chốt: **"Zero grep hits is not evidence."** Bằng chứng là đã tìm ra cơ chế
  *có thể* tham chiếu tới nó và cơ chế đó không tham chiếu.
- Bắt buộc ghi vào commit body *cơ chế nào đã kiểm và kiểm thế nào*, không phải
  "grep rỗng".
- Gợi ý nguồn orphan có thật: `EPIC-006` (bỏ QML) và `EPIC-009` (xây lại Sanity)
  đều để lại rác — `ls scripts/` đáng một lượt.

## Acceptance

- [x] Không còn con số test nào trong `doctor.prompt.md`.
- [x] Không còn bước verify nào dựa trên `.qml` trong `janitor.prompt.md`.
- [x] Cả hai neo vào một nguồn việc tự làm mới.
- [x] Guard xanh.
