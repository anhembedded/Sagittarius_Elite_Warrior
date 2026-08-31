---
name: Domain Truthfulness Rule
description: Hệ thống không được nói dối về thứ nó thật sự đã làm — validate thật, snapshot bất biến, không gộp ngữ nghĩa nghiệp vụ, UI không hứa thứ backend chưa làm được, benchmark có phương pháp.
trigger: on_file_change
patterns:
  - <SRC_DIR>/domain/**
  - <SRC_DIR>/application/**
---

# TRUTHFUL DATA, VALIDATION & SNAPSHOT SEMANTICS

Nguyên tắc xuyên suốt: **hệ thống không được nói dối về thứ nó thật sự đã
làm.** Một con số hợp lệ về mặt kiểu dữ liệu vẫn có thể là lời nói dối về
nghiệp vụ — và tuỳ domain, đó có thể là tiền thật, hồ sơ y tế thật, hay quyết
định thật của người dùng.

---

## 1. Validate phải chứng minh được điều nó khẳng định

- Một kiểm tra "đã đủ dữ liệu trong khoảng X" PHẢI verify **khoảng trống bên
  trong**, dùng đúng bước/nhịp của dữ liệu và biên đã chuẩn hoá. Min/max hoặc
  tổng số dòng **không** chứng minh được độ phủ.
- Ràng buộc do hệ thống ngoài quy định (hạn mức, kích thước tối thiểu, bước
  giá trị, quota) PHẢI lấy từ metadata của chính đối tượng đang xét, đã cache.
  **Không bao giờ hard-code một ràng buộc "phổ quát"**, và không lấy đại lượng
  này thay cho đại lượng khác chỉ vì chúng cùng đơn vị.

## 2. Snapshot phải bất biến và tự mô tả

Snapshot lịch sử/cache hiển thị cho người dùng PHẢI:

- **bất biến** — không giữ tham chiếu tới model còn mutate được;
- **có chặn bộ nhớ**;
- **đủ provenance để mô tả kết quả một cách trung thực**: cấu hình đã dùng,
  cửa sổ dữ liệu / watermark, phiên bản + tham số của thuật toán, mô hình chi
  phí, chế độ chạy.

Thiếu provenance thì hai kết quả trông giống hệt nhau có thể đến từ hai cấu
hình khác nhau, và không ai phát hiện được.

## 3. Không gộp ngữ nghĩa nghiệp vụ

Các sự kiện domain **khác nhau** phải được mô hình hoá và test **riêng**.
Không để một nhãn mơ hồ lặng lẽ đại diện cho nhiều hơn một sự thật.

Ví dụ (thay theo domain của bạn): tín hiệu của thuật toán, ý định thao tác,
kết quả thực thi, mở một vị thế, đóng một vị thế — là **năm** sự thật khác
nhau. Trong một hệ chỉ hỗ trợ một chiều, thao tác "ra" là **đóng** cái đang
có, **không** phải mở chiều ngược lại.

## 4. Business contract trước implementation contract

Test phải **trước hết** diễn đạt lời hứa nghiệp vụ quan sát được, rồi mới
verify implementation. Một suite xanh chỉ chứng minh các lời gọi nội bộ, cấu
trúc dữ liệu hiện có, hay một hợp đồng engine **cố tình hạn chế**, thì **không
phải** bằng chứng rằng hành vi người dùng thấy là đúng.

Với mọi hành trình quan trọng, viết acceptance xác định (deterministic) cho:
input kỳ vọng, các chuyển trạng thái, kết quả, và **thứ hiển thị ra** (bảng,
biểu đồ, thông báo).

## 5. UI phải trung thực

Mọi nhãn, icon, marker, bộ lọc, chỉ số, và empty state PHẢI mô tả **thứ đã
thật sự xảy ra** và **thứ hệ thống hỗ trợ ở hiện tại**.

- Hai sự thật khác nhau phải có biểu diễn khác nhau (§3).
- **Không** trình bày một khả năng đang lên kế hoạch hoặc chưa hỗ trợ như thể
  đã có: ẩn nó, disable nó, hoặc ghi rõ là chưa khả dụng.
- Test **ngữ nghĩa hiển thị**, không chỉ test payload bên dưới.

## 6. Không hứa hiệu năng khi chưa đo

- Không bao giờ tuyên bố độ trễ "tức thì" hay cố định mà không có fixture
  benchmark tái lập được. Nêu rõ workload, trạng thái cache, phương pháp đo.
  ETA hiển thị phải nói rõ là **ước lượng**.
- **Phương pháp benchmark khi so sánh hai implementation:** cùng payload
  nguồn bất biến, cùng chuỗi thao tác/viewport, cùng cách chờ hoàn tất, và
  cùng cách lấy kết quả cuối. Ghi lại median/p95, môi trường, backend thật,
  ngữ nghĩa hiển thị, và cảnh báo bắt được.
- **Hiệu năng và tính đúng là hai bằng chứng riêng biệt.** Không bao giờ cải
  thiện một con số benchmark bằng cách bỏ bớt dữ liệu, nhãn, hay bước kiểm
  tra kết quả cuối.

## 7. Counterintuitive Story Check

Khi một câu chuyện người dùng, nhãn, giá trị mặc định, hay tiêu chí nghiệm thu
**có thể mâu thuẫn hợp lý** với mô hình tư duy của người dùng, **dừng lại và
báo cáo** hành vi quan sát được, bằng chứng, và đánh đổi — trước khi chốt
thiết kế. Không tự bịa ra một ý định ẩn của người dùng; mã hoá ngữ nghĩa đã
chọn một cách trung thực vào chữ trên UI và vào acceptance test.
