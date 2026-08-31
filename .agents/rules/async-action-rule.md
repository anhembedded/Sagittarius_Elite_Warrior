---
name: Async Action Ownership Rule
description: Sở hữu action, chặn stale callback, cancellation hợp tác cho mọi tác vụ nền do người dùng khởi tạo, và Coordinator Pattern khi một controller quá tải.
trigger: on_demand
---

# ASYNC ACTION OWNERSHIP & CANCELLATION

Đọc file này khi: sửa controller/presenter, submit việc lên thread/task pool,
xử lý cancellation token, viết callback nhận kết quả từ worker nền, hoặc tách
một controller quá tải.

Đây là mảng sinh ra nhiều bug thật nhất trong các dự án có UI — đọc hết trước
khi sửa, đừng đọc lướt.

---

## 1. Action ownership & cancellation

- **Mọi tác vụ nền do người dùng khởi tạo** có thể làm đổi trạng thái vòng đời
  của UI (chạy, sync, load, render) PHẢI có một **action context bất biến**:
  `action_id`/generation duy nhất, loại action, snapshot input bất biến, thời
  điểm bắt đầu, và kết cục cuối cùng tường minh.
- **Signal của worker và callback hoàn tất PHẢI mang theo danh tính action.**
  Trước khi đổi state, đổi dữ liệu hiển thị, hay khởi động một action tiếp
  theo, phía nhận PHẢI verify action đó **còn đang active**. Callback cũ
  (stale) thì **bỏ qua và ghi log** — không bao giờ được ghi đè lên ý định mới
  hơn của người dùng.
- **Cancellation phải hợp tác và idempotent.** Một action đã huỷ **không được
  phép** phát ra trạng thái thành công/thất bại sau đó, và chuyển trạng thái
  cuối của nó phải khôi phục đúng trạng thái trước-action, chứ không mù quáng
  ép về `IDLE`.
- **Use case chạy dài PHẢI kiểm cancellation ở mọi pha tính toán**, kể cả pha
  validate/chia dữ liệu. Sự kiện tiến độ phải được **throttle hoặc gộp** trước
  khi tới UI thread.

---

## 2. Coordinator Pattern cho một controller quá tải

Khi logic tác vụ nền của một controller vượt quá một file, tách **theo lát
feature** thành một class:

- **do controller sở hữu, inject qua constructor** (thread manager,
  dispatcher, và đúng những signal nó xử lý) — **không** phải thứ tự resolve
  container của chính nó, không tự đăng ký vào DI, không tự khám phá được từ
  bên ngoài;
- đây là một nhóm **riêng biệt** so với `logic/`/`helpers/` thuần hàm: helper
  là hàm thuần / biến đổi không state, còn Coordinator **được phép giữ state**
  và tự submit việc nền.

**Một Coordinator KHÔNG ĐƯỢC sở hữu state machine riêng hay sổ sách
action-ownership/cancellation riêng** (`action_id`/generation, chặn stale,
hợp đồng huỷ hợp tác ở §1). Sổ sách đó có **đúng một** chủ sở hữu — controller
(hoặc **một** tracker dùng chung do controller sở hữu và phát cho mọi
Coordinator) — không bao giờ được implement lại ở từng Coordinator.

Tách một controller thành nhiều Coordinator mà mỗi cái giữ bộ đếm action-id
riêng chính là vi phạm **Single-Scope Cohesion**
([`code-quality-rule.md`](code-quality-rule.md)): một vòng đời bị xé thành
nhiều nguồn sự thật có thể lặng lẽ mâu thuẫn nhau.

**Trước khi tách** một controller đã có sẵn cỗ máy action-ownership riêng:
**rút cỗ máy đó ra thành một tracker dùng chung, tái sử dụng được, trước** —
đừng nhân bản nó sang các file Coordinator mới.

Controller sở hữu màn hình vẫn giữ FSM, giữ việc nối dây signal UI và signal
hệ thống, và giữ tiếng nói cuối cùng về state hiển thị. Coordinator **làm
việc và báo cáo lại qua nó** — không trở thành các mini-controller song song
với ý kiến riêng về UI mode.

---

## 3. FSM và decorator nuốt exception — hai cái bẫy đi cùng nhau

- **Đừng chuyển state machine sang đúng state nó đang đứng.** Ma trận chuyển
  trạng thái thường không khai cạnh tự thân, nên lời gọi đó **ném lỗi**.
- **Hệ quả nguy hiểm hơn nằm ở decorator bắt lỗi** (`@safe_ui_action` hoặc
  tương đương) mà nhiều codebase bọc quanh handler UI: app **không chết**,
  nhưng handler **chết giữa chừng** — mọi dòng phía sau lời gọi đó **không bao
  giờ chạy**, và không có gì nổi lên bề mặt.

Hai luật rút ra:

1. **Không đặt việc quan trọng (refresh dữ liệu, phát tín hiệu hoàn tất) SAU
   một lời gọi có thể ném lỗi** trong một handler được bọc bởi decorator nuốt
   exception.
2. **Một worker nền chưa từng khoá UI thì không được phát tín hiệu mở khoá.**
   Tín hiệu mở khoá không tương ứng với một lần khoá là một chuyển trạng thái
   không hợp lệ đang chờ xảy ra.

