# DOCTOR-002 — `EPIC-003F` đang bị chặn bởi một rủi ro không còn tồn tại

**Nguồn:** chạy `.jules/doctor.prompt.md` (quét brief thường trực `EPIC-003`)
**Ưu tiên:** P2 — không phải lỗi runtime, nhưng đang **chặn** việc phân rã file lớn thứ 2 trong repo
**Trạng thái:** 🔴 Chưa làm — cần user quyết
**Liên quan:** [`EPIC-003F`](../epics/EPIC-003_presenter_and_god_file_decomposition/incomplete/EPIC-003F_backtest_viewmodel_composite_design_review.md), [`EPIC-006`](../epics/EPIC-006_drop_qml/README.md)

---

## 1. Phát hiện

`EPIC-003F` (tách `BacktestViewModel`, 1.368 dòng) bị **cố ý chặn lại**, không
phải vì thiếu người làm mà vì một đánh giá rủi ro cụ thể. Nguyên văn §1 của nó:

> *"mọi file `.qml` đang bind `viewModel.xxx` trực tiếp — tách ViewModel gốc
> thành nhiều `QObject` con nghĩa là mọi điểm bind đó phải đổi cách viết […]
> một thay đổi lan rộng tới gần như mọi `.qml` của màn Backtest cùng lúc."*

Và §2 bắt trả lời 3 câu hỏi thiết kế trước khi được code — **cả 3 đều là câu
hỏi về QML**: cơ chế bind lồng `Property(QObject)` trong QML, chiến lược migrate
từng file `.qml`, và bao nhiêu test binding QML là đủ để không lặp lại
`BUG-018`/`BUG-019`.

**Toàn bộ tiền đề đó đã chết cùng `EPIC-006`.** Kiểm bằng cây thư mục, không
bằng trí nhớ:

```bash
find src -name '*.qml' | wc -l                          # → 0
grep -rn "setContextProperty\|rootContext" src --include='*.py'   # → không có dòng nào
```

Không còn file `.qml` nào trong app, và **không chỗ nào expose ViewModel vào
context QML nữa**. `BacktestViewModel` giờ chỉ được đọc từ code QtWidgets bằng
Python — nơi "blast radius" là các lời gọi thuộc tính mà `mypy` nhìn thấy được,
chứ không phải chuỗi binding chỉ nổ lúc chạy.

## 2. Vì sao đáng mở task riêng thay vì sửa lặng lẽ

Đây đúng loại lệch mà `EPIC-011` vừa dọn ở `.jules/`, lần này nằm trong bảng
task: **một quyết định đúng tại thời điểm viết, không ai đo lại sau khi thế giới
đổi.** Hậu quả cụ thể ở đây không phải câu chữ sai — mà là file lớn thứ 2 trong
`src/` bị treo sau một cánh cổng thiết kế đã không còn ý nghĩa.

Nhưng **"rủi ro cũ chết" không tự động bằng "làm ngay"**. Có thể rủi ro mới đã
thế chỗ (ví dụ: giờ ai đọc `viewModel.xxx` từ widget nào, `mypy` phủ được bao
nhiêu phần trong khi `src/presentation/` vẫn đang bị loại trừ nguyên khối). Đó
là việc của task này: **đo lại rủi ro thật rồi mới đề xuất**, không phải mở khoá
theo quán tính.

## 3. Việc cần làm

- [ ] Viết lại §1 và §2 của `EPIC-003F` theo thực tế QtWidgets: 3 câu hỏi thiết
      kế cũ đều đã moot, ghi rõ **vì sao** (kèm 2 lệnh kiểm ở trên) thay vì xoá
      lặng lẽ — để lần sau không ai mở lại đúng câu hỏi đó.
- [ ] Đo blast radius thật: đếm và liệt kê mọi chỗ đọc `viewModel.` của màn
      Backtest ở tầng widget, phân loại theo sub-ViewModel dự kiến.
- [ ] Nêu rõ rủi ro **mới** (nếu có) thay cho rủi ro QML cũ — đặc biệt: `mypy`
      hiện **không** kiểm `src/presentation/` (loại trừ nguyên khối vì
      false-positive `@Property` của PySide6), nên "trình biên dịch sẽ bắt được"
      **không phải** một đảm bảo dùng được ở tầng này.
- [ ] Đề xuất: greenlight, giữ chặn, hay huỷ — kèm lý do. **Quyết định cuối là
      của user**, giống cách `EPIC-003D` được huỷ.

## 4. Ngoài phạm vi

**Không** code tách `BacktestViewModel` trong task này. Đây là task đo lại và
viết lại brief, đúng tinh thần "vòng thiết kế trước" mà `EPIC-003F` đặt ra —
chỉ là đo đúng thế giới hiện tại thay vì thế giới năm ngoái.
