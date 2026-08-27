# EPIC-011F — `bolt.prompt.md`: đưa về cùng khuôn

**Trạng thái:** ✅ Xong 2026-08-26
**Repo:** Elite
**Phụ thuộc:** `EPIC-011A`

## Bối cảnh

`bolt.prompt.md` đã được sửa một phần ở `8b3f387` (26/08) — nó là file **đúng
hướng nhất** trong 7 file và là bản mẫu cho cách viết "hỏi cây thư mục, đừng chép
sự kiện". Task này không sửa hướng, chỉ đưa nó về cùng khuôn với 6 file kia.

## Đã làm

- Cắt phần đã chuyển sang `.jules/README.md` (bối cảnh 2 repo, luật commit và
  trailer, boundary chung, quy ước journal) — thay bằng một dòng link ở đầu.
- **Sửa cổng CI**: `-UnitOnly` → cổng chung ở `README.md` §3 (`-Full`). Đây là
  cùng một lỗi có ở cả 7 file, `bolt` không ngoại lệ.
- Gỡ hai đoạn khảo cổ chỉ còn giá trị lịch sử: chuyện `.agents/skills/optimize.md`
  chưa bao giờ tồn tại, và ghi chú `BOT-038` về nhóm test UI flaky (`ci-local.ps1`
  đã ghi rõ flag đó là no-op từ 25/08 — script là nguồn sự thật, không phải
  prompt). Cả hai còn nguyên trong lịch sử git và trong file epic này; một prompt
  chạy mỗi ngày không phải chỗ chứa chúng.
- Sửa 3 tham chiếu guard bắt được: `.agents/skills/optimize.md`, `.jules/bolt.md`
  (journal chưa tồn tại — chuyển sang dạng `.jules/<your name>.md`), và
  `Tasks/.obsidian/` (chỉ có trên máy maintainer; luật này đã nằm ở
  `README.md` §6).
- Giữ nguyên phần thật sự thuộc về Bolt: thứ tự ưu tiên **Algorithm → Query →
  I/O → Concurrency → Caching → Memory → Micro**, danh sách tối ưu đã hiệu quả ở
  codebase này, và 2 mục "hỏi trước" có giá trị cao (thêm concurrency chỗ chưa
  có; thêm cache chưa viết chiến lược invalidation).

## Acceptance

- [x] Không còn nội dung trùng với `.jules/README.md`.
- [x] Cổng CI là `-Full`.
- [x] Guard xanh (`bolt` là file cuối cùng còn tham chiếu gãy trước task này).
