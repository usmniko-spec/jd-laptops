#!/bin/bash
# Первичная загрузка пайплайна в GitHub. Использование:
#   ./push.sh https://github.com/USER/REPO.git ghp_ТОКЕН
set -euo pipefail
REPO="${1:?укажите URL репозитория}"
TOKEN="${2:?укажите токен}"
cd "$(dirname "$0")"
git init -q 2>/dev/null || true
git add -A
git -c user.name="jd-bot" -c user.email="jd-bot@users.noreply.github.com" commit -qm "jd laptops pipeline" || true
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO"
git push -u "https://x-access-token:${TOKEN}@${REPO#https://}" main
echo "загружено. Включите Actions: Settings → Actions → General → Workflow permissions → Read and write"
