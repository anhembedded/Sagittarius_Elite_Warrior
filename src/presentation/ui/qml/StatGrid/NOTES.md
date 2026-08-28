# StatGrid

Hình C (`EPIC-015` §4c): lưới thẻ chỉ đọc, không tương tác. Duy nhất một dialog dùng:
`extended_metrics_dialog.py`. Vẫn tách VM riêng dù chỉ một consumer, vì luật §3.2 không đổi
theo số lượng consumer: state phải nằm ở nơi test với tới được.
