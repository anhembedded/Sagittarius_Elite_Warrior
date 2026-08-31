---
name: Logging Rule
description: Đặt log ở đâu để một bug report tự chỉ ra root cause của chính nó, và giữ log đọc được.
trigger: always_on
---

# LOGGING RULES

Thước đo của logging **không phải** nó ghi được bao nhiêu. Là: **một vòng
"tái hiện rồi gửi log" có đủ để định vị root cause hay không.** Nếu người đọc
phải đoán, hoặc phải xin người báo lỗi chạy lại với nhiều log hơn, thì logging
đã thất bại — bất kể nó sinh ra bao nhiêu dòng.

> **Bằng chứng thật:** ba vòng "tái hiện rồi gửi log" bị tiêu phí cho một lỗi
> hiển thị, vì log **không nói gì** về backend nào đang chạy, lớp tương tác có
> đang bật không, và cái gì thật sự đã được vẽ ra.

---

## 1. Mọi logger PHẢI nằm dưới một namespace gốc

Handler (console/file/viewer) được gắn vào **một** logger gốc
`<LOG_NAMESPACE>`, và logger gốc của hệ thống thì **không** gắn gì.

```python
logger = logging.getLogger("<LOG_NAMESPACE>.ChartCard")   # đúng
logger = logging.getLogger(__name__)                      # IM LẶNG dưới WARNING
```

Một logger nằm ngoài cây đó **không có handler nào trong toàn bộ chuỗi**:
`info()` và `debug()` phát ra **không gì cả**, và chỉ cơ chế dự phòng cuối
cùng của thư viện mới hiện WARNING trở lên, không định dạng.

**Đây là kiểu im lặng do thiết kế — code trông đúng và lời gọi vẫn thành
công.** Phải có **guard test** khoá luật này; ngoại lệ duy nhất là gọi
`getLogger(name)` thuần tuý để `addHandler`/`removeHandler` lên một logger của
người khác.

---

## 2. Log **quyết định**, không chỉ log kết quả

Log **mọi nhánh** nơi hệ thống **chọn** giữa các implementation, **fallback**,
hay **suy giảm lặng lẽ** — kèm **lý do**. Người đọc phải biết được đường code
nào đã chạy mà không cần đọc code.

- Backend/adapter/host nào được chọn, **cái gì đã được yêu cầu**, và vì sao hai
  cái đó khác nhau (`backend 'python' (requested: 'auto')`, kèm lý do
  fallback).
- Cơ chế tuỳ chọn nào đang bật cho phiên này (cache, overlay, tăng tốc phần
  cứng) — **và log cả trường hợp TẮT**. "Không có dòng nào" không phải bằng
  chứng của "đang tắt"; nó không phân biệt được với "logging hỏng".
- **Cái gì thật sự đang có hiệu lực** so với cái gì đã được cấu hình. Ý định
  trong cấu hình không phải bằng chứng về trạng thái runtime.

---

## 3. Dòng môi trường một lần là bắt buộc với code phụ thuộc máy chủ

Một defect tái hiện trên máy người báo lỗi mà không tái hiện trên máy dev là
**chuyện thường**, không phải ngoại lệ. Mọi component có hành vi phụ thuộc máy
đang chạy PHẢI log **một lần, lúc khởi tạo**: backend thật đang dùng, lý do
fallback nếu có, tỷ lệ pixel của thiết bị, nền tảng, và kích thước/hình học
liên quan.

---

## 4. Tóm tắt theo thao tác, không bao giờ theo từng event

Một cú kéo chuột phát ra hàng trăm event. Log mỗi event ở mức INFO làm báo cáo
không đọc nổi và tự đánh bại chính nó. Hãy log:

- **một dòng khi tương tác bắt đầu**, mang theo hình học và ngưỡng nó sẽ dùng;
- **một dòng cho mỗi chuyển biến có ý nghĩa** bên trong (render lại, fallback,
  huỷ);
- **một dòng tóm tắt khi kết thúc**, mang theo số đếm, giá trị tệ nhất đo
  được, và trạng thái cuối.

Đặt **con số người đọc hành động được** vào dòng tóm tắt: kích thước theo pixel
**cũng như** theo phần trăm, thời gian đã trôi qua, và một giá trị cách ngưỡng
của nó bao xa. *(Báo cáo chỉ bằng `%` đã che một dải trắng 333px sau con số
"15%".)*

---

## 5. Log trạng thái đủ để LOẠI một tầng ra khỏi diện nghi

Đo nhiều tầng cùng lúc, không chỉ tầng đang nghi. Với **mỗi** tầng, log thứ mà
người đọc cần để **minh oan** cho nó: nó được yêu cầu làm gì, nó thật sự đã áp
dụng gì, và cái gì **còn đang chờ**.

Công việc bị **hoãn hoặc gộp** PHẢI báo cáo là nó **đã được áp dụng hay chưa**
— một khung hình chụp lúc một cập nhật đang chờ sẽ hiển thị dữ liệu mới cạnh
lớp phủ cũ, và **không gì khác trong log** cho thấy điều đó.

---

## 6. Sáu mức, theo thứ tự — chọn mức hẹp nhất còn vừa

`TRACE < DEBUG < INFO < WARNING < ERROR < CRITICAL`

- **`TRACE`** — chi tiết quá dày cả với một phiên dev bình thường: mỗi frame,
  mỗi pixel, mỗi tick. Dành riêng cho đúng những hot path mà §4 đã cấm log
  theo từng event. *Nếu bạn ngần ngại để một dòng log bật suốt một phiên chẩn
  đoán vì lượng của nó, thì nó là `TRACE`, không phải `DEBUG`.*
- **`DEBUG`** — chi tiết theo từng event như §4 mô tả: chẩn đoán bình thường,
  an toàn để bật suốt một lần tái hiện.
- **`INFO`** — quyết định, môi trường, tóm tắt theo thao tác (§2-3).
- **`WARNING`** — một đường chạy **suy giảm nhưng đã phục hồi** (fallback đã
  bật, retry đã thành công).
- **`ERROR`** — một thao tác thất bại nhưng tiến trình vẫn lành lặn.
- **`CRITICAL`** — chính tiến trình đã hỏng (khởi động thất bại không phục hồi
  được, một trạng thái hỏng mà không gì phía sau tin được). Hiếm theo thiết
  kế; đừng dùng cho một exception đã bắt được mà `ERROR` đã bao.

Ngưỡng là **một** key cấu hình duy nhất; lời gọi dưới ngưỡng bị bỏ **lặng
lẽ**, bất kể gọi bằng method nào.

---

## 7. Phiên của người phát triển tự động có nhiều log hơn

| Cờ | Ngưỡng | File |
| :--- | :--- | :--- |
| `--dev` | `DEBUG` | `logs/dev-<timestamp>.log` |
| `--debug` | `TRACE` | `logs/debug-<timestamp>.log` |

Cả hai ghi **toàn bộ phiên** ra file có dấu thời gian. `--debug` **bao hàm**
`--dev` — nó chỉ verbose hơn, không phải một chế độ khác.

**Không bao giờ bắt người dùng sửa file cấu hình để lấy được thông tin chẩn
đoán**, và **không bao giờ** dựa vào việc người báo lỗi chép tay scrollback của
terminal — chi tiết mất đúng ở chỗ nó quan trọng. **Xin FILE log.**

---

## 8. Tiền tố log bằng một tag ổn định, và giữ format lọc được

Dùng một tag subsystem trong ngoặc vuông làm token đầu tiên — `[chart-env]`,
`[chart-data]`, `[cached-frame]` — hoặc một kiểu `KEY=value` nhất quán. Người
báo lỗi dán cả phiên; người đọc cần **đúng một** lệnh lọc để cô lập một
subsystem.

Formatter phải **cố định trường**, ví dụ:

```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

— chính là để một file log đã lưu lọc được **hai chiều** mà không phải động
vào app:

- **theo mức:** `grep -E '\- (WARNING|ERROR|CRITICAL) \-' session.log` — vì
  trường mức được bao bởi ` - ` ở cả hai phía, cách này không bao giờ vô tình
  khớp một tên mức xuất hiện **bên trong** một message;
- **theo subsystem:** `grep '\[chart-data\]' session.log` — kết hợp cả hai để
  cô lập output verbose của đúng một subsystem.

**Không đổi thứ tự trường hay ký tự phân tách** mà không kiểm xem có filter/
regex nào đang phụ thuộc vào nó (trong tài liệu task, trong script, hay trong
chính các bước tái hiện của một bug report). Cổng CI ở
[`ci-rule.md`](ci-rule.md) §5 **quét log bằng đúng matcher này** — đổi format
là làm hỏng cổng đó một cách lặng lẽ.

---

## 9. Một dòng chẩn đoán chưa ai thấy phát ra thì coi như không tồn tại

Sau khi thêm log, **chạy đường code đó và xác nhận các dòng thật sự xuất
hiện**, qua **cấu hình logging THẬT** — không phải qua một cấu hình mặc định
nhanh trong script nháp, vốn gắn một handler gốc mà app thật không bao giờ có.

Một vòng debug trọn vẹn đã bị mất vì instrumentation **không thể phát ra**.
