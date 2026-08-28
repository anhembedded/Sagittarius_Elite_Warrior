# TimezonePicker

Pilot #1 của `EPIC-015` bậc 1. Chọn vì nó là **modal nhỏ nhất và độc lập nhất**
(`timezone_picker_dialog.py`, 66 dòng) — cửa sổ riêng, không lồng vào chart, không
phụ thuộc màn nào.

Nó đo được đúng một câu hỏi: *một danh sách chọn viết bằng QML + VM riêng thì tốn bao nhiêu,
và test có với tới không?*

**Luật đáng nhớ:** `selected` được tính trong `timezone_picker_vm.py`, **không** trong delegate
của `Repeater`. Một delegate hỏi "tôi có phải dòng đang chọn không" là một **luật**, và luật nằm
trong `.qml` là luật mà `mypy`/`ruff`/`pytest` không nhìn thấy.
