# EPIC-005A — Ghi lại vì sao đảo chiều, và điều kiện dừng

**Thuộc Epic:** [`EPIC-005`](../README.md)
**Trạng thái:** 🔴 Chưa làm
**Phụ thuộc:** Không — đây là cổng chặn cho toàn bộ epic

---

## 0. Vì sao task này tồn tại (không phải thủ tục hành chính)

Dự án **đã đảo chiều một lần rồi**. `.agents/rules/ui-architecture.md:10` (bên engine) ghi
framework hiện tại *"replaces the previous QtWidgets/QFrame/QSS"* — tức QtWidgets → QML là
một quyết định có chủ đích, và engine's `EPIC-001` vừa xây xong bộ kit QML để phục vụ nó.

Bây giờ đảo ngược lần hai. Nếu không nói rõ được **lý do nào của lần một đã sai hoặc không
còn đúng**, rủi ro thật không phải chọn sai công nghệ — mà là **đảo chiều lần ba**, sau khi
đã đốt vài nghìn dòng cho lần hai.

Task này không viết code. Nó tồn tại để lần sau ai đó muốn quay lại QML thì phải phản bác
được một văn bản, thay vì chỉ nêu cảm giác.

## 1. Yêu cầu

1. **Tìm và trích dẫn lý do gốc chọn QML.** Đọc engine's `EPIC-001` (cả 4 task con),
   `.agents/rules/ui-architecture.md`, `qml-rule.md`. Ghi lại từng lý do *bằng nguyên văn*,
   kèm đường dẫn `file:line`. Nếu không tìm thấy lý do nào được viết ra — **ghi đúng như
   vậy**, đó là phát hiện quan trọng chứ không phải thất bại của việc tìm kiếm.
2. **Đối chiếu từng lý do với hiện trạng**: còn đúng / không còn đúng / chưa bao giờ đúng.
   Mỗi kết luận phải có bằng chứng đo được, không phải ý kiến.
3. **Liệt kê bằng chứng chống QML đã có sẵn**, tối thiểu:
   - `AppDataTable` bắn ~75 dòng `TypeError ... of null` ra stderr lúc first paint, **bypass
     `qInstallMessageHandler`**, tốn rất nhiều thời gian điều tra, từng bị filed nhầm thành
     engine task rồi phải rút — nguồn:
     `Sagittarius_Engine/examples/student_management/docs/ui_extension_lifecycle.md:60-89`.
   - `qss/style.qss` chép hex tay, tự docstring `palette.py:15-17` thừa nhận phải sync thủ công.
   - Elite **không dùng** `AppDataTable` của engine — tự viết `Repeater`/`ListView` trong từng
     modal. Bộ kit dùng chung thực chất không được dùng chung.
4. **Viết điều kiện dừng (kill criteria)** — cụ thể, đo được, quyết định TRƯỚC khi bắt đầu:
   - Pilot `EPIC-005D` vượt bao nhiêu lần chi phí dự kiến thì dừng?
   - Bao nhiêu regression thị giác thì coi là không chấp nhận được?
   - Nếu gate không giữ được baseline (tự chụp, đừng chép số từ tài liệu) thì dừng hay sửa?

   Không có phần này thì epic sẽ chạy bằng quán tính chứ không bằng bằng chứng.

## 2. Sản phẩm

Một file `docs/decisions/2026-xx-xx_qml_to_qtwidgets.md` (hoặc chỗ tương đương theo quy ước
repo — kiểm tra trước, đừng tự đặt thư mục mới nếu đã có chỗ dành cho ADR).

## 3. Cổng chặn

`EPIC-005D` trở đi **không được bắt đầu** trước khi file này tồn tại và user đã đọc.
`EPIC-005B` được phép chạy song song (nó có lợi kể cả khi epic bị huỷ).

## 4. Kết cục có thể xảy ra: huỷ epic

Nếu đối chiếu ở mục 1.2 cho thấy lý do chọn QML **phần lớn vẫn đúng**, kết luận đúng đắn là
**huỷ EPIC-005 và mở lại EPIC-003D**. Đó là một kết quả thành công của task này, không phải
thất bại.
