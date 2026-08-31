---
name: UI Presentation Rule
description: Tầng presentation — view thuần khai báo, binding phản ứng, responsive sizing, single source of truth cho layout dùng chung, injection defense, icon, và quy ước preview.
trigger: on_file_change
patterns:
  - <SRC_DIR>/presentation/**
---

# UI & PRESENTATION RULES

Coordinator Pattern và mọi thứ về tác vụ nền **không** nằm ở đây — xem
[`async-action-rule.md`](async-action-rule.md): đó là luật về sở hữu tác vụ,
không phải về trình bày.

---

## 1. Tách logic khỏi UI — tuyệt đối

- **View là thuần khai báo.** File view (template/markup/QML/JSX) chỉ định
  nghĩa bố cục, binding theo theme, micro-animation, và signal tương tác.
- **Không nhúng logic phức tạp trong view.** Tính toán, biến đổi dữ liệu,
  validate domain, state machine đều thuộc ViewModel / Presenter / Domain.
  Helper cục bộ của view (xử lý focus, gọi một slot, reset một input đã render)
  chỉ được phép khi nó **không** nhân bản một luật nghiệp vụ và **không** trở
  thành nguồn state thứ hai.
- **Điều phối một chiều:** UI kích hoạt hành động bằng cách gọi method của
  ViewModel; Presenter xử lý nghiệp vụ rồi cập nhật property của ViewModel.

## 2. Binding phản ứng, không gán tay

Bind thẳng property của phần tử UI vào property của ViewModel và vào theme.
**Không bao giờ phá binding bằng phép gán mệnh lệnh trong signal handler** —
đó là cách một giá trị lặng lẽ tách khỏi nguồn sự thật của nó.

## 3. Chia nhỏ component

- Coi **300 dòng** là ngưỡng review bắt buộc cho một file view, không phải một
  con số máy móc để fail.
- **Cái gì dùng chung được thì phải dựng dùng chung**, không viết bản sao "gần
  giống". Component dùng chung sống ở thư mục dùng chung; component chỉ một
  màn hình dùng thì ở ngay màn hình đó (xem "không chung thư mục",
  [`architecture-rule.md`](architecture-rule.md) §5).
- **Thêm tính năng vào một widget đã có thì luôn tự hỏi trước:** design hiện
  tại còn chịu được không, hay đây là lúc phải redesign?

## 4. Đặt tên & khả năng test

- **Mọi phần tử tương tác PHẢI có một định danh ổn định** (`objectName`,
  `data-testid`…). Đó thường là thứ **duy nhất** test tích hợp/E2E bám vào
  được. **Không bao giờ** dùng chỉ số sinh tự động làm định danh test duy
  nhất.
- Quy ước tên property và signal nhất quán trong toàn repo; signal đặt tên
  theo **cụm động từ** mô tả việc đã xảy ra (`runRequested`, `chosen`).

## 5. Responsive — không có kích thước cứng

- **Không hard-code `width`/`height` cứng** cho modal, dialog, popup, card.
  Dùng kích thước ưu tiên, clamp theo biên khả dụng.
- Dùng layout manager của framework thay vì đặt toạ độ tay.
- Container cuộn bên trong phải khai báo **clip** và chiều rộng nội dung
  responsive.

## 6. Bảng/grid: độ rộng cột là single source of truth

Với mọi bảng có header, độ rộng cột PHẢI được khai báo **tập trung một chỗ**
và bind vào **cả** header lẫn delegate của dòng — đó là cách duy nhất bảo đảm
căn cột khớp 100% khi resize cửa sổ hay kéo splitter.

## 7. Injection defense

Luôn ép chế độ **plain text** cho mọi phần tử hiển thị dữ liệu động hoặc đến
từ bên ngoài (log, thông báo lỗi, tên do người dùng nhập, dữ liệu từ API).
Bất kỳ chỗ nào render rich text/HTML từ dữ liệu không kiểm soát là một lỗ
injection UI.

## 8. Icon & theme

- Icon là **vector chuẩn hoá** trong một thư mục asset, không phải emoji thô.
- Render icon qua **một** cơ chế tô màu theo theme tập trung, để đổi theme
  không phải sửa từng chỗ dùng.

## 9. Micro-animation

Chuyển cảnh mượt bằng animation ngắn (150–250ms) trên màu/opacity/kích thước.
Không bao giờ chặn UI thread để chạy animation.

## 10. Quy ước preview — bắt buộc cho mọi package UI

Mỗi package UI (mỗi màn hình, mỗi component dùng chung) PHẢI có một điểm vào
preview độc lập (`preview.py` với `build_preview()`, story, hoặc tương đương)
để render nhanh **không cần boot toàn bộ ứng dụng**.

Kèm theo:
- một cách chạy preview bằng một lệnh, có `--list` để biết có những target nào;
- một **guard test** kiểm mọi package UI đều có preview — nếu không, quy ước
  này sẽ mục ruỗng trong vài tuần.

## 11. Test UI

- **Test ViewModel không cần GUI** — phần lớn coverage của một widget nên nằm
  ở đây, không nằm trong test render.
- **Test render mỏng, có chủ đích:** chỉ chứng minh view **load được** và các
  binding trỏ vào property mà ViewModel thật sự có — đúng lớp lỗi mà linter và
  type checker không thấy. Đừng nhân bản assert logic của ViewModel vào đó.
- **Không bao giờ giữ tham chiếu tới một delegate/child qua một lần refresh.**
  Nhiều framework huỷ và tạo lại toàn bộ delegate khi model đổi — tra cứu lại
  sau mỗi lần refresh.
- **Mô phỏng input thật** (API test input của framework) thay vì tự gọi tay
  một signal với chữ ký đoán mò.
- **Load lỗi phải ném lỗi, không render hộp trắng.** Host của mỗi view phải
  biến một lần load thất bại thành exception rõ ràng — "render-and-hope" biến
  một lỗi cú pháp thành một màn hình trống không ai điều tra.
