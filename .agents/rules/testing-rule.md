---
name: Testing Rule
description: Cách VIẾT test cho đúng — mỗi tầng chứng minh gì, async không dùng sleep, invariant, Boundary Value Analysis + mutation-verify, business acceptance.
trigger: on_demand
---

# TESTING RULES — cách VIẾT test

**Phân vai với [`ci-rule.md`](ci-rule.md):** file đó giữ *lệnh chạy*, hợp đồng
4 tầng test, và cách xử lý khi gate đỏ. File này giữ *cách viết* một test cho
đúng. Cần biết chạy cái gì → `ci-rule.md`; cần biết viết cái gì → file này.

Sửa bug thì [`bug-fix-rule.md`](bug-fix-rule.md) là nguồn chuẩn — nó quy định
regression test phải viết **trước** khi sửa và phải xác nhận fail đúng lý do.

---

## 1. Mỗi feature phải khai bằng chứng ở đủ 4 tầng

Bốn tầng định nghĩa ở [`ci-rule.md`](ci-rule.md) §4. Một thay đổi được phép
**không** thêm test mới chỉ khi một test đã có ở đúng tầng liên quan **đã**
chứng minh chính xác hành vi mới — và phải **nêu tên bằng chứng đó** trong
task/báo cáo.

---

## 2. Async & UI: không bao giờ đồng bộ bằng sleep

**Không dùng sleep để đồng bộ một test.** Chờ một signal hoàn tất có tên, một
state của FSM, một event kết thúc, hoặc một điều kiện có **giới hạn thời gian
tối đa**.

Mọi phần tử UI là thao tác quan trọng của người dùng phải có **định danh ổn
định** để test tích hợp/E2E bám vào ([`ui-rule.md`](ui-rule.md) §4).

---

## 3. Invariant cho code tính toán

Thêm test property/invariant **xác định** cho mọi code tính toán có hậu quả:

- từ chối giá trị `NaN`/vô cực;
- giữ các đại lượng không âm ở đúng chỗ chúng không được âm;
- giữ các con số dẫn xuất **nhất quán với nhau**;
- **cùng input + cùng cấu hình → cùng output, không sai khác.**

Mỗi chế độ chạy mới, mô hình chi phí mới, hay pha mô phỏng mới **phải mở rộng
bộ invariant này**, không được đi vòng.

---

## 4. Edge case: Boundary Value Analysis, không phải liệt kê vô hạn

"Test mọi edge case" là một mục tiêu không có biên và không verify được. Chọn
ca test bằng:

- **Equivalence Partitioning** — một input đại diện cho mỗi lớp mà logic được
  cho là xử lý giống nhau;
- **Boundary Value Analysis** — các giá trị **ngay tại và quanh** biên của
  lớp, nơi bug thật tập trung.

### Mutation-verify: bắt buộc cho mọi tính toán/quyết định có hậu quả

**Cố ý phá logic đang test** (lật một toán tử so sánh, dịch một biên đi một
đơn vị, đảo dấu) và **xác nhận test hiện có thật sự đỏ**. Một test vẫn xanh
trước logic đã hỏng thì **không chứng minh gì** về tính đúng, dù nó chạy qua
bao nhiêu dòng code.

> **Bằng chứng thật:** một chuỗi số **hằng số về mặt toán học** vẫn khiến hàm
> độ lệch chuẩn trả ~1e-16 thay vì đúng `0.0`, lặng lẽ pass một test giả định
> so sánh float bằng `==`.

**Đừng viết test cho một trạng thái mà một invariant hiện có đã làm cho không
thể xảy ra** (ma trận chuyển trạng thái FSM, kiểu bất biến, ràng buộc do DI
áp) — đó là độn coverage, không phải chứng minh tính đúng.

---

## 5. Business acceptance — assert **thành phần** của kết quả

Một test cho tính năng người dùng thấy PHẢI assert **thành phần nghiệp vụ**
của kết quả, không chỉ assert "đã chạy xong".

Ví dụ (thay theo domain): một hệ chỉ hỗ trợ một chiều thì kết quả được phép
chứa thao tác vào và thao tác ra, nhưng **phải không** chứa thao tác chiều
ngược lại; khi chiều ngược lại được hỗ trợ, test phải chứng minh nó **thật sự
xảy ra**, hiện đúng trong bộ lọc của nó, số liệu dẫn xuất đổi đúng chiều, và
**thứ hiển thị** biểu diễn đúng kết quả thật chứ không phải chỉ là tín hiệu
đầu vào.

---

## 6. Bốn cái bẫy khiến test vỡ oan hoặc pass oan

1. **Tự tính giá trị kỳ vọng bằng đầu** thay vì chạy code thật (xem §4).
2. **So sánh float bằng `==`.** Dùng so sánh có dung sai.
3. **Assert số lượng bằng hằng số cứng** (`len(x) == 9`). Assert theo *thứ có
   ý nghĩa*: có mặt/không có mặt, thứ tự tương đối.
4. **Assert full-object equality** trên output serialize. Assert đúng subset
   mà test thật sự quan tâm — nếu không, một field mới hợp lệ làm vỡ test.

---

## 7. Sửa bug

Theo [`bug-fix-rule.md`](bug-fix-rule.md) **đầy đủ**: root cause trước,
regression test **trước** khi sửa (đã xác nhận fail **đúng lý do**, ở **đúng
tầng test**), giữ lại vĩnh viễn sau đó.
