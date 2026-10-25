#!/bin/bash
# На Mac: забрать отчёт и данные с VPS. Запуск: ./sync_from_vps.sh user@host
set -euo pipefail
HOST="${1:?укажите user@host}"
DEST="$(cd "$(dirname "$0")/.." && pwd)"
rsync -avz --progress "$HOST:/opt/jd-pipeline/../redmibook_pro_auto.xlsx" "$DEST/" 2>/dev/null || \
  rsync -avz --progress "$HOST:/opt/redmibook_pro_auto.xlsx" "$DEST/"
rsync -avz "$HOST:/opt/jd-pipeline/data/" "$DEST/pipeline/data/"
echo "готово: $DEST/redmibook_pro_auto.xlsx"
