#!/bin/bash
# Установка пайплайна на Ubuntu 22.04/24.04 (запускать под sudo после распаковки архива).
set -euo pipefail
APP=/opt/jd-pipeline
USER_NAME=${SUDO_USER:-$USER}

apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip python3-openpyxl sqlite3 >/dev/null

mkdir -p "$APP"
if [ -f ./jd-pipeline.tar.gz ]; then
  tar -xzf ./jd-pipeline.tar.gz -C "$APP"
fi
chown -R "$USER_NAME":"$USER_NAME" "$APP"

# systemd: запуск каждые 20 минут
cat > /etc/systemd/system/jd-drip.service <<EOF
[Unit]
Description=JD laptops pipeline (auto cycle)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$USER_NAME
WorkingDirectory=$APP
ExecStart=/bin/bash $APP/drip.sh
Nice=10
EOF

cat > /etc/systemd/system/jd-drip.timer <<EOF
[Unit]
Description=Run JD pipeline every 20 min

[Timer]
OnBootSec=3min
OnUnitActiveSec=20min
AccuracySec=1min
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now jd-drip.timer
systemctl list-timers jd-drip.timer --no-pager || true
echo "готово: логи в $APP/logs/, отчёт в $APP/../redmibook_pro_auto.xlsx"
