#!/usr/bin/env bash
# Commit de tout le travail en cours, sans jamais embarquer liens.txt (fichier personnel).
# Usage : outils/commit.sh "message"
set -euo pipefail
cd "$(dirname "$0")/.."
# Jamais de commit qui ne passe pas les linters et le typage.
.venv/bin/ruff check . -q
.venv/bin/mypy --no-error-summary
(cd frontend && npx eslint . --max-warnings=0 && npx tsc -p tsconfig.json)
git add -A -- . ':!liens.txt'
git -c user.name="${GIT_AUTHOR_NAME:-GuillaudRemy}" commit -q -m "$1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- . ':!liens.txt'
git log --oneline -1
