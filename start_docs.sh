#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$DIR"

echo "🚀 Đang khởi động Server Tài Liệu (MkDocs)..."
echo "🌐 Vui lòng mở trình duyệt và truy cập: http://127.0.0.1:8000"
~/.local/bin/mkdocs serve
