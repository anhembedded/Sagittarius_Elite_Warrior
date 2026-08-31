---
name: Bug Fix Rule
description: Quy trình bắt buộc khi chẩn đoán và sửa một bug được báo — root cause trước, bằng chứng log cho cả tái hiện lẫn bản sửa, regression test trước khi sửa, đúng tầng test, giữ test vĩnh viễn, có bug report.
trigger: always_on
---

# BUG FIX WORKFLOW

File này sở hữu **toàn bộ** quy trình sửa bug. Đừng để một mảnh của nó nằm rải
rác ở file rule khác — hai bản sao từng phần sẽ trôi khỏi nhau.

---

## 1. Chẩn đoán root cause trước — không bao giờ đoán

- **Đọc bằng chứng thất bại thật** (traceback, log, ảnh chụp màn hình) và
  **nguồn thật mà nó chỉ tới** trước khi viết một dòng code sửa. "Giả thuyết
  hợp lý" **không phải** "root cause" — truy đúng chuỗi lời gọi mà lỗi đi qua.
- **Nêu root cause tường minh trước khi sửa:** cái gì gây ra bug, và vì sao
  bản sửa dự định giải quyết nó sạch sẽ mà không vượt ranh giới tầng kiến
  trúc.
- **Sửa cơ chế, không hot fix.** Cùng một lỗi lặp ở nhiều nơi mà chỉ sửa đúng
  chỗ được báo là **không chấp nhận được**. Và **sửa mà không giải thích được
  vì sao triệu chứng biến mất thì không tính là sửa.**

---

## 2. Chứng minh tái hiện VÀ bản sửa bằng bằng chứng log

- Khi đọc code tĩnh chưa đủ kết luận, thêm log **tạm thời** ở **từng tầng mà
  lỗi có thể đi qua** — input, logic nghiệp vụ, ranh giới adapter/render —
  không chỉ ở tầng bạn đang nghi. Nhiều tầng cùng lúc để **chính log chỉ ra
  chỗ hành vi thật lệch khỏi hành vi kỳ vọng**, thay vì bạn đoán tầng nào có
  lỗi.
- **Tái hiện với log đó tại chỗ** và giữ output làm bằng chứng thật cho root
  cause ở bước 1 — không phải một câu diễn giải lại điều bạn *nghĩ* nó sẽ nói.
- **Sau khi sửa, tái hiện lại và đọc CÙNG log đó để tìm bằng chứng DƯƠNG rằng
  cơ chế mới thật sự đã chạy** — ví dụ "đã loại 2 dòng chỉ báo cũ sau khi dựng
  lại" — chứ **không** chỉ là sự **vắng mặt** của triệu chứng cũ. Vắng mặt là
  bằng chứng yếu: bug có thể biến mất vì một lý do không liên quan (một nhánh
  code khác, một tình cờ về thời điểm) trong khi cơ chế sửa **chưa hề chạy**.

### Quyết định tường minh: giữ hay bỏ từng mẩu log tạm

Không phản xạ xoá hết, cũng không phản xạ giữ hết.

- **GIỮ và thăng cấp thành log vĩnh viễn** những dòng mô tả **hành vi chung**
  của hệ thống, hữu ích để chẩn đoán các bug **tương lai chưa biết** ở cùng
  khu vực. Log được giữ PHẢI được chuyển về đúng chỗ theo
  [`logging-rule.md`](logging-rule.md) — đúng namespace logger, đúng mức —
  **không bao giờ** để lại dạng `print()` thô hay một logger ad-hoc không phát
  ra gì. *(Chính điều này từng là **root cause thứ hai** của một bug thật: một
  logger nằm ngoài cây namespace của app không có handler nào và **lặng lẽ
  nuốt** mọi thứ dưới WARNING.)*
- **BỎ** những dòng chỉ chứng minh **một** giả thuyết về **một** bug cụ thể
  (in ra cặp `x, y` để xác nhận một phỏng đoán) và hết giá trị chẩn đoán khi
  bug đóng.
- **Cân nhắc vị trí trước khi giữ bất cứ gì trong hot path** (vòng render mỗi
  frame, tính toán chặt). Một dòng log ổn ở mức "mỗi thao tác" có thể là nhiễu
  thật hoặc gánh nặng thật ở 60 lần/giây — hạ độ mịn (mỗi thao tác, mỗi hành
  động) và hạ mức log. Nếu thật sự cần chi tiết mỗi frame, dùng mức verbose
  nhất (chỉ phát khi bật cờ debug) để không phải xoá nó chỉ vì nó đắt.

---

## 3. Viết regression test TRƯỚC, và xác nhận nó thật sự fail

- **Trước khi sửa code**, viết test tái hiện đúng điều kiện thất bại được báo,
  rồi **chạy nó và xác nhận nó fail ĐÚNG LÝ DO** — không chỉ xác nhận là nó
  tồn tại. Một test pass **trước** khi sửa thì không chứng minh gì và không
  được tin là bản tái hiện.
- **Chọn đúng tầng test cho nơi lỗi thật sự sống.** Nếu chỗ crash nằm trong
  một method mà mock/test-double của bạn thay thế, lần thử đó **không thể**
  tái hiện nó — một mock **không bao giờ chạy thân hàm thật**.

  > **Bằng chứng thật:** một bug được "tái hiện" bằng `Mock(spec=<host thật>)`
  > và **pass hai lần liên tiếp trong khi chưa hề có bản sửa nào**, trước khi
  > sai lầm bị phát hiện và test được viết lại ở tầng cao hơn, đối diện với
  > object thật.

- Chỉ **sau khi** test đã đỏ đúng lý do thì mới áp dụng bản sửa, rồi xác nhận
  chính test đó xanh — **và** xác nhận bằng chứng log ở bước 2 song song với
  nó, không phải test đứng một mình.

---

## 4. Giữ regression test vĩnh viễn

Regression test là **bản ghi thực thi được** của lỗi đã được báo. Nó MUST NOT
bị xoá, skip, làm yếu, hay viết lại thành thứ không còn chạm tới đường lỗi
gốc — trừ khi được thay bằng coverage **mạnh hơn** cho **đúng đường đó**.

---

## 5. Nội dung commit

- Commit sửa bug **PHẢI chứa** regression test ở bước 3 — không bao giờ sửa mà
  không kèm test, không bao giờ commit test thành một commit riêng sau đó.
- **Nêu rõ root cause trong thân commit.**
- Dùng type `fix:` theo [`commit-rule.md`](commit-rule.md), có nhắc root cause
  hoặc mã bug.

---

## 6. Lập bug report

Mọi bug đáng đi qua quy trình này đều có một file report (mã kế tiếp mã lớn
nhất đang tồn tại, tính trên **cả** thư mục đang mở lẫn đã đóng):

- **Header:** ngày báo cáo, mức nghiêm trọng, trạng thái (`Open`, hoặc
  `✅ Fixed <ngày>` kèm cách xử lý: đã root-cause / đã tái hiện / đã có
  regression test / đã verify).
- **Symptom:** quan sát được gì, **kèm bằng chứng thật** (traceback, log,
  ảnh) — không phải diễn giải lại.
- **Root cause:** cơ chế thật, kèm tham chiếu `file:line`.
- **Fix:** đã đổi gì và vì sao thế là đủ.
- **Regression test:** file nào, và xác nhận nó fail trước / pass sau.

Nếu report được lập **trước** khi sửa (bug đã tìm ra nhưng chưa ai làm), để
`Status: Open` với một mục **"Đề xuất bước tiếp theo"** — **đừng đoán một root
cause chưa verify chỉ để lấp đầy mục đó.**

Khi bản sửa đã xong: `git mv` report (và mọi ảnh nó nhúng) sang thư mục đã
đóng, cập nhật dòng `Status`, và **chuyển dòng của nó trong bảng bug** từ
bảng đang mở sang bảng đã sửa. Bảng bug là **nơi duy nhất** thấy được một bug
**đang mở**.
