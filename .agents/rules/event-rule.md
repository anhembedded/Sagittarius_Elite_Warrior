---
name: Event Placement Rule
description: Signal/callback nội bộ hay Event Bus — quyết theo "ai sở hữu sự thật này", không theo số đếm signal; và tách chuyện marshalling thread khỏi chuyện coupling.
trigger: on_demand
---

# ĐẶT CHỖ EVENT — signal nội bộ hay Event Bus?

Câu hỏi **không phải** "signal hay bus". Câu hỏi đúng là: **ai sở hữu sự thật
này?**

> **Sự thật riêng của MỘT màn/module** → signal/callback nội bộ.
> **Sự thật của HỆ THỐNG, hoặc ≥2 nơi cần** → Event Bus + đúng **một**
> subscriber chuẩn hoá.

## 1 Tách hai vấn đề đang hay bị gộp

| | Vấn đề | Cơ chế đúng |
| :-: | :--- | :--- |
| **A** | Đưa dữ liệu từ thread/context nền về main thread **an toàn** | Cơ chế queued signal / marshalling của framework — **đúng theo thiết kế** |
| **B** | **Ai được biết về ai**; một sự thật bị xử lý lặp ở nhiều nơi | Bus + đúng 1 subscriber chuẩn hoá, nhiều nơi *hiển thị* |

Cơ chế ở (A) **không** phải nợ kỹ thuật, không phải workaround, và **không**
phải thứ cần xoá. Thấy một signal bắc cầu worker → main thread thì đó là code
**đúng**, đừng "dọn" nó. Xoá nó là đẩy cập nhật UI sang thread nền — đúng lớp
lỗi mà cơ chế đó sinh ra để tránh.

## 2 Phân loại — hỏi đúng một câu

*"Nếu module khác cũng muốn biết chuyện này, nó có vô lý không?"*

- **Vô lý** → sự thật riêng tư (`load xong`, `stream của tôi start được`).
  Dùng signal nội bộ. Đẩy lên bus là **rò rỉ**: mọi nơi đều có thể nghe, bề
  mặt coupling phình ra, và nhìn code không còn biết ai phụ thuộc ai.
- **Hợp lý** → sự thật hệ thống (`health đổi`, `task nền chết`, `tiến độ
  sync`, `log`). Lên bus, **đúng một** nơi nghe và chuẩn hoá.

## 3 Thăng cấp khi consumer thứ hai xuất hiện THẬT — không thăng trước

- **Thăng cấp muộn thì rẻ:** worker vốn đã emit *một cái gì đó*; đổi chỗ nó
  emit tới là sửa cục bộ.
- **Đẩy hết lên bus trước thì đắt và gần như không lùi được** — sau đó không
  ai dám xoá subscriber nào vì không biết còn ai đang nghe.

> **Bằng chứng thật:** đếm trên 3 module — **48 signal, 46 cái có đúng 1 nơi
> nghe**; cái duy nhất fan-out đúng là sự thật hệ thống. Code đã tự phân loại
> đúng từ trước, chỉ chưa ai đặt tên cho quy tắc. Một task từng đặt chỉ tiêu
> "xoá 48 signal cầu nối" vì gộp nhầm (A) vào (B); đo thật thì **47/48 tồn tại
> vì (A)**, xoá được ≈1. **Đừng đặt chỉ tiêu theo số đếm.** Sai ranh giới thì
> con số chỉ dẫn tới việc phá code đúng.

---
