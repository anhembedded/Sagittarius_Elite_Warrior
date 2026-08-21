# EPIC-003F — `BacktestViewModel` → Composite ViewModel: vòng thiết kế trước, CHƯA code

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** 🔴 Chưa làm — **chưa greenlight code**, chỉ mở khi có quyết định thiết kế.
**Phụ thuộc:** Không phụ thuộc kỹ thuật task nào, nhưng cố tình tách khỏi `EPIC-003E` — không tự động làm sau khi `E` xong.

---

## 1. Vì Sao Task Này Bị Chặn Lại, Khác Các Task Coordinator

`PRO-002` §2.2 đề xuất tách `BacktestViewModel` (1350 dòng, hơn 80
`@Property` + 40 `Signal`) thành `BacktestConfigViewModel`/
`BacktestMetricsViewModel`/`BacktestChartViewModel`. Về giấy tờ nhìn giống
`EPIC-003B`/`E` (cũng là "tách 1 file Presentation quá tải"), nhưng **bản
chất rủi ro khác hẳn**: mọi Coordinator chỉ đổi cấu trúc **phía Python**,
không ai ngoài Presenter gọi tới nó trực tiếp. Ngược lại, **mọi file `.qml`
đang bind `viewModel.xxx` trực tiếp** — tách ViewModel gốc thành nhiều
`QObject` con nghĩa là **mọi điểm bind đó phải đổi cách viết**
(`viewModel.config.xxx` hoặc tương đương lồng nhau), một thay đổi lan rộng
tới gần như mọi `.qml` của màn Backtest cùng lúc.

Đây đúng lớp lỗi mà phiên này đã gặp nhiều lần khi đổi cách binding QML:
`BUG-018`, `BUG-019` (`import Sagittarius.Theme` không tồn tại làm cả modal
không dựng được), `BOT-070` (chuẩn hoá giá trị qua ranh giới QML→Python).
Không nên bắt đầu code trước khi có câu trả lời rõ ràng cho mục 2.

## 2. Câu Hỏi Thiết Kế Bắt Buộc Trả Lời Trước Khi Mở Task Này Để Code

1. **Cơ chế bind lồng**: PySide6 `Property(QObject)` trả về `QObject` con có
   `@Property` riêng — QML có đọc được `viewModel.config.someProp` phản ứng
   đúng (`notify` signal của property con) hay cần cơ chế khác (ví dụ mỗi
   sub-ViewModel expose qua context property riêng thay vì lồng trong 1
   root)? Cần 1 bài test tối thiểu (spike) xác nhận trước khi cam kết thiết
   kế, không suy đoán.
2. **Chiến lược migrate**: đổi toàn bộ `.qml` "big bang" 1 lần, hay giữ
   `BacktestViewModel` cũ làm facade proxy sang 3 sub-ViewModel trong 1 giai
   đoạn chuyển tiếp (mỗi `@Property` cũ forward sang đúng sub-ViewModel),
   cho phép từng file `.qml` migrate dần? Ảnh hưởng trực tiếp độ rủi ro và
   thời gian task con thật sự (khi được mở) sẽ mất bao lâu.
3. **Phạm vi test cần có trước khi bắt đầu**: cần bao nhiêu ảnh chụp UI/
   test binding thật (không phải chỉ test Python logic) để tự tin đổi mà
   không lặp lại `BUG-018`/`BUG-019`?

## 3. Việc Cần Làm Ở Chính Task Này (chỉ thiết kế, không code)

- Trả lời 3 câu hỏi ở mục 2, viết thành 1 mục "Quyết định" trong chính file
  này.
- Chỉ sau khi có quyết định, đổi `Trạng thái` sang cho phép mở task con thật
  (`EPIC-003F1` chẳng hạn) để triển khai code theo đúng thiết kế đã chốt.
