#!/bin/sh
# Guard for the .agents/ set itself — runs in any project, language-agnostic.
#
#   sh .agents/check-agents-docs.sh
#
# Checks two things, both of which are failure classes that really happened:
#   1. Broken .md links — a prompt once pointed at a rule file that had never
#      existed and ran for months, because an unattended agent still reports
#      success.
#   2. Unreplaced placeholders — the rule set copied into a new project with
#      the blanks left unfilled.
#
# Wire it into the project's CI gate (see rules/ci-rule.md section 1).
# A non-zero exit means something is wrong.

set -eu
DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
rc=0

echo "== 1. Broken .md links in $DIR =="
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

echo "== 2. Unreplaced placeholders =="
# README.md is the lookup table itself and always self-matches — exclude it.
if grep -rn --exclude=README.md --exclude="$(basename "$0")" '<[A-Z_]\{2,\}>' "$DIR"; then
  echo "  ^ replace them per the table in .agents/README.md section 2, then re-run."
  rc=1
else
  echo "  ok"
fi

[ "$rc" -eq 0 ] && echo "== .agents OK ==" || echo "== .agents FAILED =="
exit "$rc"
