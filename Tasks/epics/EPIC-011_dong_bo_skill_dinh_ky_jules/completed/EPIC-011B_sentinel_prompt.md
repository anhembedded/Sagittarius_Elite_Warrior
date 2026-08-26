# EPIC-011B — `sentinel.prompt.md`: gỡ authority không tồn tại

**Trạng thái:** ✅ Xong 2026-08-26
**Repo:** Elite
**Phụ thuộc:** `EPIC-011A`

## Vấn đề

Bước 1 trong quy trình hằng ngày của Sentinel là *"Scan the codebase against
`sentinel-rule.md`'s priority matrix"*. **File đó chưa bao giờ tồn tại** —
không trên đĩa, không trong `git log` của bất kỳ nhánh nào.
`.agents/ONBOARDING.md` §8 mục 1 đã ghi nhận đúng phát hiện này (và đã gỡ 2 link
gãy khác trỏ cùng chỗ) nhưng không ai sửa file prompt.

Nghĩa là: agent bảo mật chạy định kỳ, mỗi lần chạy đều được lệnh quét theo một
ma trận rỗng. Nó vẫn sẽ tìm ra *thứ gì đó* — nhưng không theo tiêu chí nào, và
không ai biết nó bỏ sót gì.

Ngoài ra prompt còn trùng lặp với `EPIC-004`: cổng Ruff `S` (Bandit) +
`PLR2004`/`B`/`SIM`/`ERA`/`N` đã fail-cứng trong `-Full` từ `EPIC-004B` (24/08).
Sentinel đi tìm hardcoded secret và SQL injection bằng tay là làm lại việc máy
đã làm mỗi lần chạy CI.

## Đã làm

1. Thay authority ma bằng 4 file **có thật**: `domain-truth-rule.md` (chuẩn an
   toàn tài chính gần nhất repo có), `logging-rule.md` (cái gì được phép lọt vào
   log user gửi kèm bug report), `architecture-rule.md` (adapter bảo mật ở tầng
   nào), `bug-fix-rule.md` (**ràng buộc**: fix bảo mật là bug fix — root cause
   trước, regression test **trước** khi sửa).
2. Thêm mục *"What is already machine-enforced"* — nói rõ cổng `EPIC-004` phủ
   gì, kèm lệnh tự kiểm `pyproject.toml`, và kết luận: làm lại nó không đáng một
   lần chạy.
3. Định nghĩa lại bãi săn theo **4 lớp rủi ro mà linter không suy luận được**:
   secret *đang di chuyển* (lọt vào log/dialog/crash report) chứ không phải
   secret nằm yên; dựng đường dẫn shard per-symbol; validate số tài chính
   (`NaN`/`±Inf`/mẫu số 0/giá 0); nhánh lỗi nuốt exception.
4. Thêm lối thoát đúng: phát hiện thật nhưng quá lớn cho một lần chạy → **viết
   bug report** theo `Tasks/bug_report/README.md` rồi dừng, **không** thu nhỏ nó
   thành một miếng vá vô hại.

## Acceptance

- [x] Không còn tham chiếu tới một `sentinel-rule.md` như thể nó tồn tại; đoạn
      cảnh báo viết ở dạng không phải đường dẫn literal để guard không phải
      ngoại lệ hoá nó.
- [x] Mọi file rule prompt trỏ tới đều `ls` thấy được.
- [x] Có mục nói rõ phần nào đã được máy kiểm, để không lãng phí lần chạy.
- [x] Guard xanh.
