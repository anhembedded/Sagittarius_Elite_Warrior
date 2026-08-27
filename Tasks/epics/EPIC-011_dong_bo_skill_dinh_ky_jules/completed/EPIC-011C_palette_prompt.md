# EPIC-011C — `palette.prompt.md`: chuyển bãi săn từ QML sang QtWidgets

**Trạng thái:** ✅ Xong 2026-08-26
**Repo:** Elite
**Phụ thuộc:** `EPIC-011A`

## Vấn đề — nặng nhất về mặt "meaningful"

Palette là agent UX. **Toàn bộ** bãi săn của nó viết bằng QML:

- ví dụ code: `Button { Accessible.role; Accessible.name; ToolTip.visible: hovered }`
- component mẫu: `StatefulButton`
- file mẫu: `Sidebar.qml`, `SettingsScreen.qml`, `BotParamsDialog.qml`
- cách verify: `quick_widget.errors() == []`
- danh sách "favorite enhancement": 10/10 mục là API Qt Quick

`EPIC-006` đóng 2026-08-25 và app hết sạch `.qml` (`find src -name '*.qml' | wc -l`
→ `0`). Từ đó tới nay, mỗi lần Palette chạy định kỳ, nó đi tìm một tầng công
nghệ không còn tồn tại — hoặc không tìm ra gì, hoặc tệ hơn, tự bịa ra việc.

## Đã làm

1. Mở đầu bằng cảnh báo thẳng: prompt cũ sai ở đâu, và **3 lệnh tự kiểm** thay
   vì bắt tin lời cảnh báo đó.
2. Đổi API sang QtWidgets thật: `setAccessibleName()`/`setAccessibleDescription()`,
   `setToolTip()`, `setFocusPolicy()`/`setTabOrder()`, `setCursor()`,
   `setWhatsThis()`. Ví dụ ✅/❌ viết lại bằng Python.
3. Thêm mục *"What is already machine-enforced"* dựa trên
   `src/presentation/ui/kit/guards.py`: 3 lớp lỗi đã fail CI sẵn (colour literal
   ngoài `kit/style.py`; `setStyleSheet()` dạng property list trần trên widget có
   layout — chính là `BUG-008` và 4 lần tái phát; subclass `QFrame`/`QDialog`/
   `QWidget` trần ngoài kit). Nói rõ: gặp vi phạm nghĩa là **guard hỏng**, báo
   chứ đừng vá tay.
4. Bãi săn mới, tự làm mới bằng `ls`: kit (`controls/`, `surfaces/`,
   `overlays/`) → screens → `preview.py` của từng UI package (bắt buộc theo
   `ui-presentation-rule.md`) → `apply_role()`/`StyleRole`.
5. Bước verify thêm: đổi giao diện thì phải **nhìn** — `find src/presentation/ui
   -name preview.py` cho các entry point standalone không cần boot cả app.
6. Giữ lại đúng một bài học thật của agent này (QSS không hỗ trợ `cursor:`,
   phải `setCursor()`), nhưng chuyển sang mục Journal kèm nói rõ journal **chưa
   tồn tại** — thay vì khẳng định "đã có entry, đừng khám phá lại".

## Acceptance

- [x] Không còn API Qt Quick nào được nêu như thứ agent có thể dùng.
- [x] Bãi săn dẫn ra bằng lệnh `ls`/`find`, không phải danh sách file viết cứng.
- [x] Chuỗi UI trong ví dụ là tiếng Việt (đúng `CLAUDE.md`).
- [x] Guard xanh.
