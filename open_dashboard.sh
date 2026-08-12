#!/bin/bash
echo "🚀 Đang cập nhật lại dữ liệu Kanban Board..."
python3 scripts/generate_task_board.py

echo "🌐 Đang mở Dashboard trên trình duyệt..."
xdg-open Tasks/dashboard.html
