# Перенос пайплайна на VPS

Цель: сбор идёт без вашего ноутбука — 24/7 на сервере, отчёт забирается по расписанию.

## 1. Выбор бесплатного сервера

| Провайдер | Что бесплатно | Плюсы | Минусы |
|---|---|---|---|
| **Oracle Cloud Always Free** | 4 ARM-ядра / 24 ГБ или 2 AMD micro | бессрочно, не спит, регионы Токио/Осака/Сеул | нужна карта для верификации; ARM-инстансы часто «out of capacity» |
| **Google Cloud e2-micro** | 1 vCPU / 1 ГБ, 30 ГБ диск | бессрочно, стабильно выдаётся | только США (us-central1/us-west1/us-east1) |
| AWS / Azure | 750 ч/мес | просто | только 12 месяцев, потом платно |
| Render / Koyeb / Railway | «free» | быстро | засыпают или триал-кредит — для cron не годятся |

**Рекомендация:** Oracle Always Free, регион **Токио или Осака** (ближе к Китаю, ниже шанс блокировки и меньше задержка). Если ARM недоступен — берите AMD micro (1 ГБ хватает: пайплайн ест ~50 МБ).

⚠️ **Главный риск:** JD агрессивно проверяет IP дата-центров, особенно американских. Поэтому первый шаг после создания сервера — прогнать `check_jd.sh`. Если он пишет «JD ответил заглушкой» или «заблокировал» — меняйте регион (Токио/Сеул), а не боритесь с лимитами.

## 2. Создание сервера

1. Регистрация в Oracle Cloud (нужна карта, списаний на Always Free нет).
2. Compute → Instances → Create:
   - Image: **Ubuntu 24.04**
   - Shape: `VM.Standard.A1.Flex` (ARM, 1–4 ядра) или `VM.Standard.E2.1.Micro` (AMD)
   - Регион: Tokyo / Osaka / Seoul
   - SSH-ключ: сгенерируйте и сохраните приватный
3. Откройте только SSH (порт 22). Веб-порты не нужны.

## 3. Установка

На Mac соберите архив и залейте:

```bash
cd jd.com/deploy
./pack.sh                      # создаст jd-pipeline.tar.gz
scp jd-pipeline.tar.gz ubuntu@<IP>:~/
scp vps_setup.sh check_jd.sh ubuntu@<IP>:~/
```

На сервере:

```bash
ssh ubuntu@<IP>
sudo bash vps_setup.sh
bash check_jd.sh               # проверка доступа к JD
sudo systemctl list-timers jd-drip.timer
sudo tail -f /opt/jd-pipeline/logs/auto_$(date +%Y%m%d).log
```

`vps_setup.sh` ставит python3, распаковывает пайплайн в `/opt/jd-pipeline`,
создаёт таймер systemd на каждые 20 минут и включает его.

## 4. Забрать результат на Mac

```bash
cd jd.com/deploy
./sync_from_vps.sh ubuntu@<IP>
```

Отчёт появится в `jd.com/redmibook_pro_auto.xlsx`. Чтобы тянуть автоматически,
добавьте в cron на Mac:

```
0 9,21 * * * cd ~/Documents/Deepseek/jd.com/deploy && ./sync_from_vps.sh ubuntu@<IP> >> /tmp/jd-sync.log 2>&1
```

## 5. Управление

```bash
sudo systemctl status jd-drip.timer     # состояние
sudo systemctl stop jd-drip.timer       # пауза
sudo systemctl start jd-drip.timer      # возобновить
sudo journalctl -u jd-drip.service -n 50
```

Состояние сбора (паузы, бюджеты, тип блокировки) — в листе **«Статус сбора»** отчёта.
Локальный файл состояния: `/opt/jd-pipeline/data/auto_state.json`.

## 6. Если JD всё равно блокирует

- Сменить регион сервера (Токио → Сеул → Осака).
- Уменьшить частоту: в `drip.sh` заменить таймер на `OnUnitActiveSec=40min` в
  `/etc/systemd/system/jd-drip.timer` и `sudo systemctl daemon-reload`.
- Как крайний вариант — резидентный прокси в Китае (платный), прописать в
  `config.json` → `"proxy": "http://user:pass@host:port"`; формат `{url}`
  поддерживается для прокси-обёрток.

## 7. Безопасность

- Только SSH-ключ, пароль отключён.
- Порт 22 можно ограничить своим IP в Security List.
- В архиве нет ваших токенов и личных данных — только код и публичные данные JD.
