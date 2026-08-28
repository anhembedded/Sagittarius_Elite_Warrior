# SelectList

Component dùng chung cho hình A + B (`EPIC-015` §4c): "chọn 1 trong danh sách" và "danh sách chỉ
đọc" là **cùng một Repeater trên cùng một model**, khác nhau đúng một cờ `selectable`. Ban đầu
viết riêng cho `TimezonePicker` ở bậc 1; tổng quát hoá ở đây sau khi đếm lại thấy `strategy_picker`
và `limitations` là cùng hình dạng, không phải hai việc riêng.

Người dùng: `timezone_picker_dialog.py`, `strategy_picker_dialog.py`, `limitations_dialog.py`,
và nửa "preset" của `time_range_picker_dialog.py`.
