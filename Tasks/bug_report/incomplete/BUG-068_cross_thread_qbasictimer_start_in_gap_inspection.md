# BUG-068 — QBasicTimer::start: Timers cannot be started from another thread trong quá trình kiểm tra Database Gaps

**Reported date:** 2026-08-30  
**Severity:** 🟠 **P2**  
**Status:** 🔴 Open — chỉ ghi nhận hiện tượng và log bằng chứng theo yêu cầu.

---

## 1. Hiện tượng (Symptom)

Khi kích hoạt tính năng kiểm tra khoảng trống dữ liệu (Inspect Gaps) trên màn hình Data Management / Storage Vault, log ghi nhận 4 cảnh báo vi phạm Qt thread affinity:

```text
2026-08-30 17:33:14,602 - App - INFO - Executing query: GetDatabaseGapsQuery
QBasicTimer::start: Timers cannot be started from another thread
QBasicTimer::start: Timers cannot be started from another thread
QBasicTimer::start: Timers cannot be started from another thread
QBasicTimer::start: Timers cannot be started from another thread
```

## 2. Ghi nhận sơ bộ (Initial Observation)

- Lỗi xảy ra ngay sau khi `GetDatabaseGapsQuery` bắt đầu thực thi trên luồng nền của `ThreadManager`.
- Trong Qt/PySide6, `QTimer` và `QBasicTimer` có thread affinity gắn chặt với thread tạo ra nó. Nếu một phương thức chạy trên worker thread cố gắng gọi `start()` một timer (hoặc kích hoạt animation / transition có timer ngầm của Qt Quick / QtWidgets), Qt sẽ từ chối và in cảnh báo `Timers cannot be started from another thread`.
- Đây là biến thể của lớp lỗi `BUG-031` (từng làm đóng băng UI hoặc crash event loop).

## 3. Suggested next steps

1. Định vị thành phần UI / Model nào khởi động timer khi `GetDatabaseGapsQuery` chạy hoặc khi dữ liệu gap bắt đầu được chuẩn bị.
2. Đảm bảo toàn bộ thao tác kích hoạt timer/animation được chuyển về Qt Main Thread thông qua Queued Signal hoặc `QMetaObject.invokeMethod`.
