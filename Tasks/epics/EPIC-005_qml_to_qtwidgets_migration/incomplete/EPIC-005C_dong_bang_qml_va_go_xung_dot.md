# EPIC-005C — Đóng băng QML cho UI mới + gỡ xung đột với EPIC-003D

**Thuộc Epic:** [`EPIC-005`](../README.md)
**Trạng thái:** 🔴 Chưa làm
**Phụ thuộc:** [`EPIC-005A`](EPIC-005A_quyet_dinh_va_dieu_kien_dung.md) (cần kết luận đi tiếp hay huỷ)

---

## 0. Vì sao làm trước khi migrate

Migrate 7.078 dòng mất nhiều đợt. Trong lúc đó nếu vẫn có màn hình QML mới ra đời thì epic
không bao giờ về đích. Đóng băng **không tốn gì** và chặn được chảy máu ngay.

## 1. Yêu cầu

1. **Sửa `.agents/rules/qml-rule.md`**: nêu rõ QML từ nay chỉ dành cho chart
   (`NativeChartItem`) và các file đang tồn tại; UI mới viết bằng QtWidgets. Giữ nguyên phần
   quy tắc QML hiện có — file QML cũ vẫn sống lâu dài, người sửa chúng vẫn cần luật.
   **Không xoá luật, chỉ giới hạn phạm vi áp dụng.**
2. Ghi ngày, lý do, và trỏ tới ADR của `EPIC-005A`. Rule không giải thích được vì sao thì lần
   sau sẽ bị lật lại bằng cảm tính, đúng như cách chúng ta đang lật cái trước.
3. **Chốt xung đột với EPIC-003D** — chọn một, ghi vào file EPIC-003D:
   - **Hoãn**: đánh dấu ⏸️, ghi rõ "hoãn tới khi EPIC-005 xong, khi đó phần lớn `components/`
     đã biến mất"; hoặc
   - **Huỷ EPIC-005** (nếu `EPIC-005A` kết luận vậy) và mở lại EPIC-003D bình thường.

   **Không được để cả hai cùng 🔴 mở** — đó là cách chắc chắn để hai phiên làm việc đá nhau.
4. Trích xuất dữ liệu còn giá trị từ EPIC-003D: danh sách **9/18 file `components/` chỉ dùng
   bởi 1 màn hình**. Đó chính là danh sách "migrate cùng màn hình, không cần làm widget dùng
   chung" — chép sang epic này để không mất khi EPIC-003D bị hoãn.

## 2. Sản phẩm

- `.agents/rules/qml-rule.md` đã sửa.
- `EPIC-003D` có trạng thái dứt khoát.
- Bảng phân loại `components/`: dùng-chung-thật vs thuộc-về-một-màn-hình.

## 3. Không làm gì ở task này

Không đụng file `.qml` nào, không đụng code. Đây thuần là rule + điều phối.
