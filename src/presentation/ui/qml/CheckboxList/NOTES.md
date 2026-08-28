# CheckboxList

Hình D (`EPIC-015` §4c): danh sách checkbox độc lập. Hai consumer với hai luật khác nhau:

- `indicator_picker_dialog.py` — dòng đến từ `script_model` (một `QAbstractListModel` sống),
  không khoá, không luật chéo dòng.
- `order_execution_dialog.py` — 4 dòng cố định, một dòng khoá cứng ("On bar close"), và hai
  dòng loại trừ lẫn nhau (bật cái này tắt cái kia). **Luật loại trừ không nằm trong
  `checkbox_list_vm.py`** — nó là luật của `order_execution_dialog.py`, gọi `vm.refresh()` lại
  với state mới sau mỗi `toggled`, giống hệt `_sync()` bản widget cũ từng làm.
