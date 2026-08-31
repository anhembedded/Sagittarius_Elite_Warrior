#!/bin/sh
# Guard cho chính bộ .agents/ — chạy được ở mọi dự án, không phụ thuộc ngôn ngữ.
#
#   sh .agents/check-agents-docs.sh
#
# Kiểm 2 thứ, cả 2 đều là lớp lỗi đã xảy ra thật:
#   1. Link .md gãy — một prompt từng trỏ vào file rule chưa bao giờ tồn tại
#      và chạy hàng tháng, vì agent chạy không người trông vẫn báo thành công.
#   2. Placeholder chưa thay — bộ rule copy sang dự án mới mà quên điền.
#
# Nối nó vào cổng CI của dự án (xem rules/ci-rule.md §1). Exit != 0 là có lỗi.

set -eu
DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
rc=0

echo "== 1. Link .md gãy trong $DIR =="
found_link=0
for f in $(find "$DIR" -name '*.md'); do
  d=$(dirname "$f")
  grep -oh '](\.[^)]*\.md[^)]*)' "$f" 2>/dev/null | sed 's/^](//; s/)$//' | while read -r raw; do
    target="${raw%%#*}"
    [ -f "$d/$target" ] || echo "  BROKEN  ${f#"$DIR"/}  ->  $raw"
  done
done > /tmp/_agents_links.$$ || true
if [ -s /tmp/_agents_links.$$ ]; then cat /tmp/_agents_links.$$; found_link=1; else echo "  ok"; fi
rm -f /tmp/_agents_links.$$
[ "$found_link" -eq 0 ] || rc=1

echo "== 2. Placeholder chưa thay =="
# README.md là bảng tra cứu, luôn tự khớp — loại ra.
if grep -rn --exclude=README.md --exclude="$(basename "$0")" '<[A-Z_]\{2,\}>' "$DIR"; then
  echo "  ^ thay hết theo bảng ở .agents/README.md §2 rồi chạy lại."
  rc=1
else
  echo "  ok"
fi

[ "$rc" -eq 0 ] && echo "== .agents OK ==" || echo "== .agents FAILED =="
exit "$rc"
