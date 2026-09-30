# 10. Jellyfin через отдельный Xray REALITY reverse tunnel

Это инструкция для изолированного экземпляра **Xray 26.2.6** в `/opt/xray-jellyfin` на VPS и Fedora. Она фиксирует работающую схему, а не устанавливает обновления автоматически. В существующей установке не заменяйте рабочие конфиги шаблонами: сначала выполните [проверки и проверку автозапуска](11-xray-operations.md).

По проверке владельца от 30 сентября 2026 года оба Xray-сервиса включены в автозапуск; запрос с VPS к `127.0.0.1:18096` вернул Jellyfin `302 Found`. Это зафиксированный результат, не постоянный мониторинг. Caddy/домен/HTTPS пока не считаются настроенными.

## Схема и границы доступа

```text
Браузер → SSH port forwarding → VPS 127.0.0.1:18096 (tunnel inbound)
                                          ↓ reverse-out
                               VLESS reverse / REALITY
                                          ↓ reverse-in
                               Fedora 127.0.0.1:8096 → Jellyfin

Само соединение устанавливает Fedora → VPS TCP 8443.
Будущий HTTPS: браузер → Caddy на VPS :443 → 127.0.0.1:18096.
```

| Параметр | VPS | Fedora |
| --- | --- | --- |
| Бинарник / рабочий конфиг | `/opt/xray-jellyfin/xray`, `/opt/xray-jellyfin/config.json` | Те же пути на другом компьютере |
| Сервис | `xray-jellyfin.service` | `xray-jellyfin-client.service` |
| REALITY | Вход TCP `8443`, target `www.bing.com:443` | Исходящее соединение к VPS:8443, SNI `www.bing.com` |
| Jellyfin | Вход только `127.0.0.1:18096` | Назначение только TCP `127.0.0.1:8096` |

Шаблоны находятся в [`deploy/xray-jellyfin`](../deploy/xray-jellyfin). Они используют VLESS `reverse.tag`, а не старые `reverse.bridges`/`reverse.portals`. На VPS `reverse-out` появляется при регистрации клиента; на Fedora `reverse-in` маршрутизируется в `jellyfin-local`. Внешний транспорт защищён REALITY: `encryption: none` / `decryption: none` относятся к дополнительному шифрованию VLESS.

В шаблонах первый outbound — `blackhole`: запросы без явного маршрута блокируются. Fedora переписывает назначение на Jellyfin и разрешает его через узкое `finalRules`; доступ ко всей домашней сети не разрешается. `show: false` и `loglevel: warning` исключают постоянный отладочный вывод. Реальные значения в шаблонах отсутствуют.

Amnezia, OpenVPN, AWG2, x-ui, их контейнеры, порты и существующие Xray в `/usr/local` обслуживаются отдельно. Не используйте общий установщик Xray, команды `restart xray`, сброс firewall или перезапуск Docker на VPS ради этого туннеля. Команды ниже относятся только к новому экземпляру.

## 1. Подготовка новой установки

Команды с относительными путями выполняются из корня клона этого репозитория на соответствующем компьютере. Для рабочей установки разделы 1–4 — справочник восстановления, не обязательная повторная установка.

На обеих машинах проверьте архитектуру (`uname -m`), время (`timedatectl status`) и установленную версию:

```bash
sudo /opt/xray-jellyfin/xray version
```

Если бинарника ещё нет, скачайте подходящий Linux-архив **v26.2.6** из [официального релиза](https://github.com/XTLS/Xray-core/releases/tag/v26.2.6), сверьте его контрольную сумму с опубликованной для этого архива и распакуйте вне репозитория. Для `x86_64` нужен `Xray-linux-64.zip`, для другой архитектуры выбирайте соответствующий архив. Затем установите проверенный бинарник (путь к распакованному файлу замените своим):

```bash
sudo install -d -o root -g root -m 700 /opt/xray-jellyfin
sudo install -o root -g root -m 755 /PATH/TO/VERIFIED/xray /opt/xray-jellyfin/xray
sudo /opt/xray-jellyfin/xray version
```

В этой схеме нет правил geosite/geoip, дополнительные базы ей не нужны. `26.2.6` — версия воспроизводимой исходной настройки, не обещание, что она последняя или не содержит уязвимостей. Обновление тестируйте отдельно на обеих сторонах с резервной копией.

Перед новой установкой на VPS проверьте занятость портов:

```bash
sudo ss -lntp '( sport = :8443 or sport = :18096 )'
```

Если порты уже заняты `xray-jellyfin`, это существующая установка; не запускайте второй процесс. Если занят другим сервисом, не останавливайте его — сначала согласуйте другой порт с клиентским конфигом. Для Fedora нужен исходящий TCP к VPS:8443; для VPS — доступный входящий TCP 8443 и исходящий TCP к REALITY target:443. Учитывайте firewall ОС и провайдера, добавляйте только нужное правило после проверки существующих правил. Не открывайте `18096` на VPS или `8096` на домашнем роутере, включая IPv6.

## 2. Параметры: заполнить только вне Git

В JSON используются буквальные маркеры `<...>`. Их нужно заменить в локальной копии; Xray не подставляет их из `.env`. Общий `.env.example` проекта относится к Compose и не содержит данных Xray.

| Маркер | Где нужен | Как получить |
| --- | --- | --- |
| `<VPS_HOST>` | Только Fedora | Публичный адрес или DNS-имя VPS, без протокола и порта |
| `<VLESS_UUID>` | Одинаковый на обеих сторонах | `sudo /opt/xray-jellyfin/xray uuid` |
| `<REALITY_PRIVATE_KEY>` | Только VPS | Поле `PrivateKey` из `sudo /opt/xray-jellyfin/xray x25519` |
| `<REALITY_PUBLIC_PASSWORD>` | Только Fedora | Поле `Password` из **той же** пары X25519; это публичная часть ключа, не `Hash32` и не приватный ключ |
| `<REALITY_SHORT_ID>` | Одинаковый на обеих сторонах | `openssl rand -hex 8` (16 шестнадцатеричных символов) |

Генерацию выполняйте на VPS в приватном терминале только для новой установки/запланированной ротации. Не генерируйте независимые пары ключей для клиента и сервера. В существующей установке используйте уже согласованные локальные значения. Не вставляйте их в команды shell, сообщения, скриншоты, issue или коммиты. Передавайте клиенту только UUID, публичный Password, shortId и адрес VPS через защищённый канал с проверкой SSH fingerprint. Приватный ключ остаётся на VPS. Домашний публичный IP этой схеме не нужен.

## 3. Установка конфигов

Сначала сохраните закрытую резервную копию существующего `/opt/xray-jellyfin/config.json` и unit-файла **вне Git**. При наличии файла не перезаписывайте его командами новой установки. Пример сохранения конфига с уникальным именем на каждой машине:

```bash
sudo sh -c 'umask 077; cp -p /opt/xray-jellyfin/config.json "/opt/xray-jellyfin/config.json.bak.$(date +%Y%m%d-%H%M%S)"'
```

На **новом VPS** скопируйте серверный шаблон в закрытый файл-кандидат:

```bash
sudo install -o root -g root -m 600 deploy/xray-jellyfin/vps/config.example.json /opt/xray-jellyfin/config.pending.json
sudoedit /opt/xray-jellyfin/config.pending.json
```

На **новой Fedora** скопируйте клиентский шаблон:

```bash
sudo install -o root -g root -m 600 deploy/xray-jellyfin/fedora/config.example.json /opt/xray-jellyfin/config.pending.json
sudoedit /opt/xray-jellyfin/config.pending.json
```

Замените все маркеры в файле-кандидате нужной машины; кавычки JSON сохраните. На обеих машинах проверьте, что маркеров не осталось (команда выводит только предупреждение), затем проверьте Xray:

```bash
if sudo grep -qE '<[A-Z_]+>' /opt/xray-jellyfin/config.pending.json; then
  echo 'ОСТАНОВИТЕСЬ: остались незаполненные маркеры'
else
  sudo /opt/xray-jellyfin/xray run -test -config /opt/xray-jellyfin/config.pending.json
fi
```

Только после `Configuration OK` установите проверенный файл:

```bash
sudo mv /opt/xray-jellyfin/config.pending.json /opt/xray-jellyfin/config.json
sudo chown root:root /opt/xray-jellyfin/config.json
sudo chmod 600 /opt/xray-jellyfin/config.json
```

Не публикуйте вывод неудачной проверки без очистки: сообщение об ошибке может содержать значение поля. Держите резервные копии под такими же ограничениями, как рабочий конфиг.

## 4. systemd и Jellyfin

Unit-файлы используют `User=root` для совместимости с закрытым каталогом исходной установки, убирают capabilities, запрещают запись в системные каталоги и пишут логи в journal. Высоким портам 8443/18096 дополнительные capabilities не нужны. Конфиг не должен содержать пути записи логов/данных в `/opt/xray-jellyfin` при таком `ProtectSystem=strict`. В рабочей установке сначала просмотрите локально `systemctl cat` нужного сервиса: существующие drop-in-файлы имеют приоритет над шаблоном. Не удаляйте их вслепую.

**VPS**, для новой установки:

```bash
sudo install -o root -g root -m 644 deploy/xray-jellyfin/systemd/xray-jellyfin.service /etc/systemd/system/xray-jellyfin.service
sudo systemd-analyze verify /etc/systemd/system/xray-jellyfin.service
sudo systemctl daemon-reload
sudo systemctl enable --now xray-jellyfin.service
```

**Fedora**: используется системный Docker Engine (`docker.service`), не rootless Docker/Podman. В существующем Compose у Jellyfin уже есть `restart: unless-stopped`. Из каталога медиасервера:

```bash
sudo systemctl enable --now docker.service
docker compose config -q
docker compose up -d jellyfin
curl --max-time 10 -I http://127.0.0.1:8096
sudo install -o root -g root -m 644 deploy/xray-jellyfin/systemd/xray-jellyfin-client.service /etc/systemd/system/xray-jellyfin-client.service
sudo systemd-analyze verify /etc/systemd/system/xray-jellyfin-client.service
sudo systemctl daemon-reload
sudo systemctl enable --now xray-jellyfin-client.service
```

При отсутствии доступа к Docker используйте `sudo docker compose` последовательно для того же проекта. `enable --now` не перезапускает уже работающий сервис: после осознанного изменения проверенного конфига/unit выполните `sudo systemctl restart xray-jellyfin.service` на VPS или `sudo systemctl restart xray-jellyfin-client.service` на Fedora. Не перезапускайте посторонние сервисы.

`After=network-online.target docker.service` задаёт порядок запуска, `Requires=docker.service` запускает Docker и связывает остановку клиента с ним. Готовность контейнера и наличие интернета этим не гарантируются. Повторные подключения Xray и `Restart=on-failure` помогают восстановлению; после запуска подтвердите весь путь HTTP-запросом, как описано в [эксплуатации](11-xray-operations.md).

## 5. Порты Fedora и будущий HTTPS

Ответ по `127.0.0.1:8096` доказывает локальную доступность, **но не привязку только к localhost**. В текущем `compose.yaml` строка `8096:8096` публикует порт на всех интерфейсах хоста; это сохраняет домашний доступ с ТВ. Проверьте реальные bindings через `docker compose port jellyfin 8096` и `docker inspect` из инструкции проверки. Следите, чтобы роутер, UPnP и публичный IPv6 не делали этот порт доступным из интернета; правила Docker также нужно учитывать при настройке firewall.

Если прямой доступ с ТВ по LAN не нужен, вручную замените **существующую** строку порта Jellyfin на `127.0.0.1:8096:8096` и пересоздайте только Jellyfin: `docker compose up -d jellyfin`. Не добавляйте вторую публикацию порта поверх старой. Это отдельное изменение режима доступа; текущий Compose этим руководством не меняется.

Пока HTTPS не настроен, используйте [SSH-туннель для браузера](11-xray-operations.md#просмотр-через-ssh). Будущий Caddy должен направлять запросы в `127.0.0.1:18096`. Сначала проверьте владельцев портов 80/443 — там могут быть существующие VPN/x-ui сервисы. DNS должен указывать на VPS; HTTPS и сертификат проверяются отдельно. REALITY на 8443 не является браузерным HTTPS для Jellyfin. Для публичного Jellyfin нужны актуальная версия, уникальный пароль и отдельный пользователь без административных прав; прокси-туннель не устраняет уязвимости самого приложения.

## Источники

- [VLESS reverse: направление тегов, redirect и finalRules](https://xtls.github.io/en/document/level-2/vless_reverse.html).
- [VLESS-конфигурация в исходниках именно v26.2.6](https://github.com/XTLS/Xray-core/blob/v26.2.6/infra/conf/vless.go) и [REALITY](https://github.com/XTLS/Xray-core/blob/v26.2.6/infra/conf/transport_internet.go).
- [Docker: политика перезапуска контейнеров](https://docs.docker.com/engine/containers/start-containers-automatically/).
