#!/bin/sh
# Commit finished daily market reports (UTC days before today) to main and push them. Runs once a
# day in the deployment checkout, which stays on main and is the only writer of reports/market/.
# Today's report is still rewritten every hour; it is published the next day.
set -u
cd "$(dirname "$0")/.." || exit 1
[ "$(git branch --show-current)" = main ] || { echo "not on main: nothing published"; exit 1; }
today=$(date -u +%Y%m%d)
set --
for f in reports/market/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md; do
    if [ -f "$f" ] && [ ! -L "$f" ] && [ "$(basename "$f" .md | tr -d -)" -lt "$today" ]; then set -- "$@" "$f"; fi
done
if [ $# -gt 0 ] && git add -- "$@" && ! git diff --cached --quiet -- "$@"; then
    # only these files go into the commit, whatever else the checkout holds
    git commit -q -m "Market reports through $(date -u -d yesterday +%F)" -- "$@" || exit 1
fi
# rebase on merged work, so a commit an earlier failed push left behind is retried instead of blocking
git pull -q --rebase --autostash origin main || { echo "cannot rebase on origin/main: nothing pushed"; exit 1; }
if git diff --name-only origin/main HEAD | grep -qv '^reports/market/'; then
    echo "local main holds changes outside reports/market/: nothing pushed"
    exit 1
fi
git push -q origin main && git log -1 --format='main at %h %s'
