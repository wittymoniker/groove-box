#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -lt 1 ]; then
  echo "usage: $0 git@github.com:OWNER/REPO.git [branch]" >&2
  exit 2
fi
REMOTE="$1"
BRANCH="${2:-main}"
git init
git checkout -B "$BRANCH"
git add .
git commit -m "Bootstrap sCodeOS"
git remote add origin "$REMOTE"
echo "Repository prepared. Review the commit, then explicitly run:"
echo "  git push -u origin $BRANCH"
