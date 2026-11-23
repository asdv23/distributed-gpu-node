#!/bin/sh
# Commit finished daily market reports (UTC days before today) to main and push them. Runs once a
# day in the deployment checkout, which stays on main and is the only writer of reports/market/.
# Today's report is still rewritten every hour; it is published the next day.
set -u
cd "$(dirname "$0")/.." || exit 1
if [ "$(git branch --show-current)" != main ] || ! git pull -q --ff-only origin main; then
    echo "not on main, or cannot fast-forward to origin/main: nothing published"
    exit 1
fi
today=$(date -u +%Y%m%d)
set --
for f in reports/market/*.md; do
    if [ "$(basename "$f" .md | tr -d -)" -lt "$today" ] 2>/dev/null; then set -- "$@" "$f"; fi
done
if [ $# -eq 0 ] || { git add -- "$@" && git diff --cached --quiet -- "$@"; }; then
    echo "no finished report to publish"
    exit 0
fi
# only these files go into the commit, whatever else the checkout holds
git commit -q -m "Market reports through $(date -u -d yesterday +%F)" -- "$@" &&
    git push -q origin main && git log -1 --format='published %h %s'
