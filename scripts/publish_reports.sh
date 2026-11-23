#!/bin/sh
# Commit finished daily market reports (UTC days before today) to main and push them. Runs once a
# day in the deployment checkout, which stays on main and is the only writer of reports/market/.
# Today's report is still rewritten every hour; it is published the next day. Local main never keeps
# a commit of its own: each run starts from origin/main and a failed push is undone, so the only
# commit this script can push is the one it just made from finished reports.
set -u
cd "$(dirname "$0")/.." || exit 1
[ "$(git branch --show-current)" = main ] || { echo "not on main: nothing published"; exit 1; }
git fetch -q origin main || { echo "cannot fetch origin/main: nothing published"; exit 1; }
if ! git merge-base --is-ancestor HEAD origin/main || ! git merge -q --ff-only origin/main; then
    echo "local main has commits of its own or cannot fast-forward to origin/main: nothing published"
    exit 1
fi
today=$(date -u +%Y%m%d)
set --
for f in reports/market/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md; do
    if [ -f "$f" ] && [ ! -L "$f" ] && [ "$(basename "$f" .md | tr -d -)" -lt "$today" ]; then set -- "$@" "$f"; fi
done
[ $# -gt 0 ] || { echo "no finished report to publish"; exit 0; }
git add -- "$@" || { echo "cannot stage the finished reports: nothing published"; exit 1; }
if git diff --cached --quiet -- "$@"; then
    echo "no finished report to publish"
    exit 0
fi
# only these files go into the commit, whatever else the checkout holds
git commit -q -m "Market reports through $(date -u -d yesterday +%F)" -- "$@" || exit 1
if ! git push -q origin main; then
    git reset -q --soft origin/main
    echo "push failed: the reports stay uncommitted for the next run"
    exit 1
fi
git log -1 --format='published %h %s'
