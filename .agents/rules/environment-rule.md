---
name: Environment Rule
description: Dựng môi trường là việc của agent — ranh giới giữa "cài thứ đã khai báo" (tự làm) và "thêm dependency mới" (phải hỏi).
trigger: always_on
---

# ENVIRONMENT & DEPENDENCY RULES

---

## 1. Dựng môi trường là việc của agent

Báo *"không verify được — thiếu X"* mà **chưa thử cài X** là dừng sớm một
lệnh, không phải đụng tường.

Thiếu công cụ, thiếu thư viện hệ thống, hay thiếu một dependency mà dự án
**đã khai báo** nhưng môi trường này chưa cài — đó là thứ để **cài**, không
phải lý do để bỏ qua cổng verification:

- **Gói hệ thống** mà stack của app cần để boot (thư viện đồ hoạ, font, D-Bus
  khi chạy GUI ở chế độ headless). Đừng tin một danh sách chép sẵn — để chính
  thông báo lỗi (`cannot open shared object file`) gọi tên thư viện thiếu.
- **Runtime/shell** mà script gate cần.
- **Thư viện nội bộ / repo anh em** mà dự án phụ thuộc.
- **Bất kỳ gói nào đã được ghim trong manifest** mà môi trường *này* chưa cài
  — cài **đúng phiên bản đã ghim**.

---

## 2. Ranh giới: cài ≠ thêm dependency

Đây **không phải** quyền thêm một dependency mới vào dự án.

> **Phép thử duy nhất: việc cài đó có làm đổi một file manifest được commit
> vào repo không?**
>
> - **Có** → đó là một quyết định thiết kế. **Hỏi trước.**
> - **Không** (chỉ đổi thứ đang có trên đĩa của môi trường này) → **cài và đi
>   tiếp.**

---

## 3. Chỉ báo "không verify được" khi chính lần cài đã thất bại

Và thất bại vì lý do **ngoài tầm kiểm soát của bạn**: không có mạng, registry/
proxy chặn gói, hoặc thiếu credential/quyền truy cập một repo riêng mà bạn
chưa từng được cấp.

Nói thẳng **lần cài nào đã fail và vì sao**, thay vì đi vòng qua khoảng trống
đó bằng cách bỏ qua cổng verification.

---

## 4. Phiên bản runtime: chạy CI **trên** mức sàn, không chỉ khai báo nó

Nếu dự án khai một phiên bản tối thiểu, hãy tạo môi trường và **chạy CI đúng
trên phiên bản đó** — kể cả khi phiên bản mới hơn cũng chạy được.

> **Vì sao:** một người phát triển trên phiên bản mới hơn có thể dùng cú pháp
> chỉ có ở phiên bản đó, thấy mọi test xanh trên máy mình, và để lại lời khai
> "hỗ trợ từ phiên bản N" **sai một cách lặng lẽ** — chỉ vỡ với người cài trên
> đúng mức sàn. Đây cùng hình dạng với một bug thật: một gói đã publish
> **không import được** trong khi CI của chính nó báo xanh.

Nếu không chạy CI trên mức sàn được, hãy có **một guard test** đọc mức sàn từ
manifest và **parse lại toàn bộ mã nguồn first-party ở phiên bản đó**. Nó bắt
được lỗi cú pháp, nhưng **không** bắt được API thư viện chuẩn chỉ có ở phiên
bản mới — chạy CI trên mức sàn mới bao được cả hai.

Nâng mức sàn phải là một hành động **có chủ đích**: sửa manifest, và guard đi
theo tự động.

---

## 5. Khi một API "không tồn tại", câu hỏi ĐẦU TIÊN là "bản đang cài có mới nhất không?"

Trước khi kết luận code của app tham chiếu sai:

> **Bằng chứng thật:** ba lỗi kiểu `AttributeError: type object 'X' has no
> attribute 'Y'` và `TypeError: __init__() got an unexpected keyword argument`
> **đều bị chẩn đoán sai** thành "app dùng API không tồn tại". Cả ba API đó
> **có thật** trong repo thư viện. Bản cài chỉ đơn giản là cũ hơn — **và cả
> hai bản đều báo cùng một số phiên bản**, nên lệnh xem version không giúp gì.

Kiểm bằng **chữ ký thật**, không bằng chuỗi phiên bản:

```bash
<python> -c "import inspect; from <pkg> import <Thing>; print(inspect.signature(<Thing>.__init__))"
```

Và kiểm cả **nguồn** cài, không chỉ phiên bản — một bản lỗi thời thường đến từ
một checkout cục bộ cũ (`file:///...`) chứ không phải từ registry:

```bash
<pip> list | grep <pkg>
```
