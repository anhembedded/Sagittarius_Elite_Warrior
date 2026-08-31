---
name: Design Intent Rule
description: Cái gì hoãn lại hoặc là một cái giá đã chấp nhận trả thì phải có type/test đại diện trong code — không được chỉ nằm trong tài liệu; và class là một hợp đồng, không phải một cục code.
trigger: always_on
---

# CODE PHẢI TỰ NÓI LÊN CHÍNH NÓ

> **Nếu một thứ sẽ được phát triển sau, hoặc là một cái giá đã chấp nhận trả,
> thì trong code phải có một interface / kiểu dữ liệu / test đại diện cho nó.
> Không được để nó chỉ nằm trong tài liệu.**

Lý do: tài liệu là thứ agent phải **đi tìm mới thấy**; kiểu dữ liệu là thứ
**đập vào mắt khi đọc code**. Một quyết định chỉ ghi trong `.agents/` hoặc
trong task file thì lần sau người khác sẽ làm sai — không phải vì họ ẩu, mà vì
code không hề gợi ý gì cả.

> **Bằng chứng thật:** một task đặt chỉ tiêu "xoá 48 signal cầu nối" ([`event-rule.md`](event-rule.md) §3).
> Người viết nó **có đủ** rule trong tay. Vẫn đặt sai, vì chỗ khai báo signal
> trong code **không nói một chữ nào** về việc chúng là cầu nối thread và xoá
> đi thì hỏng gì. Luật đúng mà code câm thì luật vô dụng.

## 1 Hai dạng, hai cách thể hiện

| Dạng | Bắt buộc phải có trong code |
| :--- | :--- |
| **Sẽ phát triển sau** (điểm mở rộng đã biết) | Một **type/interface/base class** đóng vai điểm hạ cánh, kèm docstring ghi công thức mở rộng. Agent sau `grep` ra được và bắt chước được |
| **Cái giá đã chấp nhận trả** (đánh đổi có chủ đích) | Một **test khoá hành vi hiện tại** + docstring nói rõ mất gì, vì sao chấp nhận, điều kiện khôi phục. Không phải chỉ một dòng ghi chú |

> **Bằng chứng thật (đánh đổi):** một thay đổi phải bỏ tính bất biến của mấy
> kiểu dữ liệu để kế thừa được base class dùng chung. Cách xử lý đúng: **không
> xoá test bất biến — đổi nó thành test khoá hành vi mới**, kèm lý do và điều
> kiện khôi phục. Mất mát nằm trong test suite, không nằm trong một dòng ghi
> chú ai cũng lướt qua.

## 2 Luôn khuyến khích abstraction — class là một **hợp đồng**

Khi viết một class, **đánh giá khả năng mở rộng và API của nó trước**, rồi mới
viết thân. Mặc định là **có abstraction**: class phải là một **hợp đồng** với
các class khác, không phải một khối implementation mà nơi khác phải biết ruột
gan mới dùng được.

Khi thêm một class mới, hỏi theo thứ tự:

1. **Ai sẽ gọi nó, và họ cần thấy gì?** Đó chính là API — thiết kế trước,
   không phải rút ra sau khi đã viết xong thân hàm.
2. **Chỗ nào có khả năng mở rộng?** (đổi backend, đổi nguồn dữ liệu, thêm biến
   thể). Chỗ đó phải là một interface, để người sau thay được mà không phải
   sửa consumer.
3. **Consumer có buộc phải biết chi tiết bên trong không?** Có → hợp đồng chưa
   đủ, siết lại.

Abstraction ở đây **không** có nghĩa "đẻ thêm lớp trung gian cho có". Nó có
nghĩa: **bề mặt công khai của class phải là thứ người khác lập trình vào
được**.

> **Bài học ngược, vẫn còn giá trị:** 4 stub class từng được sinh ra từ suy
> đoán, 0 instance thật. Chúng sai **không** phải vì thiếu abstraction, mà vì
> **đoán sai hình dạng** của thứ chưa tồn tại. Khuyến khích abstraction là
> khuyến khích **thiết kế API cho cái đang viết**, không phải khuyến khích
> đoán trước cái chưa ai cần.

## 3 Không được lách bằng docstring

Docstring/comment là **bổ sung**, không phải thay thế. Comment giải thích *vì
sao*; type và test mới là thứ **buộc** người sau đi đúng đường, và là thứ **vỡ
ra** khi thực tế đổi. Một quyết định chỉ sống trong prose thì không có gì phát
hiện khi nó hết đúng.
