# 13. Домены Radarr, Sonarr, Prowlarr и Jellyseerr

Подготовлены адреса, согласованные с владельцем. **Пока не опубликованы**: на момент проверки 1 октября 2026 года DNS-записей нет, SSH-доступ к VPS из рабочей среды недоступен. Наличие этих файлов в Git само по себе не включает домены.

| Сервис | Внешний адрес после включения | Loopback на VPS | Назначение на Fedora |
| --- | --- | --- | --- |
| Radarr | https://radarr.mediadima.ru | 127.0.0.1:17878 | 127.0.0.1:7878 |
| Sonarr | https://sonarr.mediadima.ru | 127.0.0.1:18989 | 127.0.0.1:8989 |
| Prowlarr | https://prowlarr.mediadima.ru | 127.0.0.1:19696 | 127.0.0.1:9696 |
| Jellyseerr / Seerr | https://requests.mediadima.ru | 127.0.0.1:15055 | 127.0.0.1:5055 |

Jellyfin остаётся на `https://jellyfin.mediadima.ru` через VPS `127.0.0.1:18096` → Fedora `127.0.0.1:8096`.

## Что подготовлено

- `deploy/caddy/media-apps.caddy` — четыре блока Caddy. Их добавляют к существующей конфигурации на VPS, не вместо неё.
- `scripts/prepare-media-access.py` — создаёт отдельный кандидат Xray с правами `0600`, сохраняя ключи и параметры REALITY из локального входного файла. Он не устанавливает конфигурацию, не перезапускает службы, не печатает секреты и не перезаписывает существующий выходной файл.
- `scripts/check-media-access.py` — проверяет доступность страниц входа и отказ анонимному доступу к защищённым API. По умолчанию проверяет Fedora, с `--public` — HTTPS-домены с проверкой сертификатов.

Используется только **выделенный** `/opt/xray-jellyfin` и его сервисы. Amnezia, `wdtt0`, существующий x-ui/Xray в других каталогах, firewall и swap не меняются. Исходные шаблоны Jellyfin-only в `deploy/xray-jellyfin` сохранены.

## 1. DNS

В зоне `mediadima.ru` добавьте четыре записи:

| Тип | Имя | Значение |
| --- | --- | --- |
| CNAME | radarr | jellyfin.mediadima.ru |
| CNAME | sonarr | jellyfin.mediadima.ru |
| CNAME | prowlarr | jellyfin.mediadima.ru |
| CNAME | requests | jellyfin.mediadima.ru |

TTL — стандартный у провайдера. У каждого имени должна быть только одна подходящая запись: не создавайте CNAME поверх существующей A/AAAA. Это обычные DNS-записи без URL, `https://` и номера порта. Для схемы прямого подключения к Caddy используйте DNS-only, если у провайдера есть отдельное проксирование. Не добавляйте неработающий IPv6.

CNAME выбирает сервер через DNS, но не перенаправляет браузер на Jellyfin: имя исходного сервиса сохраняется, и Caddy выбирает нужный backend.

## 2. Вход в приложения

На Fedora проверено: Radarr, Sonarr и Prowlarr используют `Forms`, `AuthenticationRequired=Enabled`, корень перенаправляется на `/login`, защищённые API возвращают `401`. Seerr инициализирован, `/api/v1/auth/me` без входа возвращает `401`.

Не отключайте обязательный вход для локальных адресов: после reverse tunnel запрос может выглядеть локальным. Не выбирайте `External`, пока отдельная система аутентификации перед приложением не установлена. Пароли и API-ключи не входят в эти файлы.

```bash
python3 scripts/check-media-access.py
```

При отдельном поддомене URL Base у Radarr/Sonarr/Prowlarr остаётся пустым. Внутренние подключения приложений сохраняют Docker-адреса `http://radarr:7878`, `http://sonarr:8989`, `http://prowlarr:9696`, `http://jellyfin:8096`. Не заменяйте их публичными доменами.

## 3. Подготовка кандидатов Xray

Следующие команды выполняются владельцем с административным доступом отдельно на Fedora и VPS. На обеих машинах должен быть доступен `scripts/prepare-media-access.py` из этой версии проекта. На VPS достаточно скопировать этот скрипт и фрагмент Caddy, без `config/`, `data/` и секретов.

На **Fedora**, из проекта:

```bash
sudo python3 scripts/prepare-media-access.py --side fedora \
  --input /opt/xray-jellyfin/config.json \
  --output /opt/xray-jellyfin/config.media-candidate.json
sudo /opt/xray-jellyfin/xray run -test \
  -config /opt/xray-jellyfin/config.media-candidate.json
```

На **VPS**, из каталога со скопированным проектом/скриптом:

```bash
sudo python3 scripts/prepare-media-access.py --side vps \
  --input /opt/xray-jellyfin/config.json \
  --output /opt/xray-jellyfin/config.media-candidate.json
sudo /opt/xray-jellyfin/xray run -test \
  -config /opt/xray-jellyfin/config.media-candidate.json
sudo ss -lntp '( sport = :17878 or sport = :18989 or sport = :19696 or sport = :15055 )'
```

До применения новые порты должны быть свободны. Скрипт ожидает структуру выделенного Jellyfin-туннеля из репозитория. При дополнительных правилах, совпадении тегов/портов или повторном запуске на уже расширенном конфиге он останавливается для ручной проверки. Не удаляйте неизвестные правила ради прохождения проверки.

На Fedora маршруты ограничены точными TCP-портами `8096`, `7878`, `8989`, `9696`, `5055` на `127.0.0.1`; остальной reverse-трафик блокируется. На VPS новые входы слушают только loopback. Новый публичный порт туннеля не требуется.

## 4. Применение в согласованное время

Этот этап кратко прервёт выделенный медиатуннель, включая Jellyfin. Он не выполнялся при подготовке файлов. Не применяйте, пока обе конфигурации не прошли `run -test` и не проверены резервные копии.

На **каждой** машине сохраните оригинал с новым уникальным именем и установите проверенный кандидат:

```bash
backup_dir=$(sudo mktemp -d /opt/xray-jellyfin/backup-media-XXXXXXXX)
sudo cp -a /opt/xray-jellyfin/config.json "$backup_dir/config.json"
printf 'Резервная копия: %s\n' "$backup_dir/config.json"
sudo install -o root -g root -m 600 \
  /opt/xray-jellyfin/config.media-candidate.json /opt/xray-jellyfin/config.json
```

Затем перезапустите только `xray-jellyfin-client.service` на Fedora и `xray-jellyfin.service` на VPS. Дождитесь восстановления соединения и проверьте на VPS каждый backend: `curl --max-time 10 -I http://127.0.0.1:17878/` и аналогично `18989`, `19696`, `15055`. Ответы `200`, `302` или `307` зависят от приложения; `401` у защищённого API ожидаем. `502`, reset и отсутствие ответа требуют диагностики до подключения Caddy. Jellyfin `http://127.0.0.1:18096/health` должен по-прежнему возвращать `200`.

## 5. Caddy и приёмка

На VPS сохраните резервную копию Caddyfile. Установите `deploy/caddy/media-apps.caddy` как `/etc/caddy/conf.d/media-apps.caddy` и добавьте один импорт в существующий `/etc/caddy/Caddyfile`:

```caddyfile
import /etc/caddy/conf.d/media-apps.caddy
```

Если уже есть `import /etc/caddy/conf.d/*.caddy`, второй импорт не нужен. Не удаляйте блок Jellyfin и другие сайты.

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
```

После выдачи сертификатов, из проекта на Fedora:

```bash
python3 scripts/check-media-access.py --public
bash scripts/check-jellyfin.sh
```

Затем войдите в каждый сервис из браузера через мобильную сеть. Для Seerr задайте Application URL `https://requests.mediadima.ru`, а External Jellyfin URL — `https://jellyfin.mediadima.ru`, сохраняя внутреннее подключение к `http://jellyfin:8096`. Проверка 401 подтверждает запрет анонимного API, но не проверяет правильность пользовательского пароля и работу всех интеграций.

Не публикуйте порты `17878/18989/19696/15055` на внешнем интерфейсе и не добавляйте подробный access log с токенами в URL. Caddy проксирует WebSocket штатно.

## Откат

Если туннель перестал работать, восстановите на обеих машинах их собственные сохранённые `config.json` с правами `600`, проверьте `xray run -test` и перезапустите только соответствующий выделенный сервис. Уберите только новый импорт/четыре блока Caddy, выполните `caddy validate` и reload. Исходный блок Jellyfin сохраняется.

Кандидаты, резервные копии и рабочие JSON содержат секреты и остаются вне Git. Не присылайте их содержимое в чат. Новые файлы репозитория и DNS-имена секретов не содержат.

Источники: [Xray routing](https://xtls.github.io/en/config/routing.html), [Freedom](https://xtls.github.io/en/config/outbounds/freedom.html), [Caddy reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy), [Radarr settings](https://wiki.servarr.com/radarr/settings).
