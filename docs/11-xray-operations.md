# 11. Проверка, reboot и восстановление туннеля

[Схема, шаблоны и установка](10-xray-jellyfin.md).

## Будет ли работать после перезагрузки?

**Да, после обычного reboot цепочка должна восстановиться автоматически**, если системный Docker и оба Xray-сервиса включены, контейнер Jellyfin создан и не был остановлен вручную, сеть поднялась, а диски с конфигурацией и медиа доступны. Вход в графическую сессию и открытый терминал не нужны для системных сервисов. При шифровании диска может потребоваться разблокировка до загрузки ОС.

На Fedora порядок такой: systemd запускает Docker → Docker возвращает работающий до reboot Jellyfin по `restart: unless-stopped` → клиент Xray устанавливает исходящий reverse tunnel к VPS. Xray может начать подключение раньше готовности Jellyfin; проверять результат нужно после готовности обоих.

Если ПК выключен или спит, смотреть домашний Jellyfin через VPS нельзя. Обычный SSH-туннель для браузера тоже завершается после reboot — его нужно открыть заново. Будущий Caddy потребует собственного проверенного автозапуска.

## Проверка до и после reboot

На **Fedora**, из каталога `fedora-media-server`:

```bash
systemctl is-enabled docker.service xray-jellyfin-client.service
systemctl is-active docker.service xray-jellyfin-client.service
docker compose ps jellyfin
docker compose port jellyfin 8096
docker inspect --format '{{.HostConfig.RestartPolicy.Name}} {{json .HostConfig.PortBindings}}' "$(docker compose ps -aq jellyfin)"
curl --max-time 10 -I http://127.0.0.1:8096
sudo /opt/xray-jellyfin/xray run -test -config /opt/xray-jellyfin/config.json
```

Ожидаются `enabled`, `active`, работающий контейнер, политика `unless-stopped`, `Configuration OK` и HTTP-ответ Jellyfin. В исходной проверке это `302 Found`, `Server: Kestrel`, `Location: web/`. Код может отличаться после изменения Jellyfin/Base URL; важно проверить, что отвечает именно ваш Jellyfin. У `docker inspect` выше выводятся только политика и bindings, а не полное окружение контейнера. Если контейнер отсутствует, сначала создайте его командой ниже.

На **VPS**:

```bash
systemctl is-enabled xray-jellyfin.service
systemctl is-active xray-jellyfin.service
sudo /opt/xray-jellyfin/xray run -test -config /opt/xray-jellyfin/config.json
sudo ss -lntp '( sport = :8443 or sport = :18096 )'
curl --max-time 15 -I http://127.0.0.1:18096
```

Должны быть публичный TCP `8443` и **только** `127.0.0.1:18096`. В шаблоне 8443 слушает IPv4 (`0.0.0.0`); существующая установка может показывать `*:8443`. `0.0.0.0:18096` или `[::]:18096` — ошибочная публичная привязка: верните `listen: 127.0.0.1`, проверьте конфиг, перезапустите только серверный Xray. `18096` проверяется на VPS, `8096` — на Fedora.

Проверку reboot проводите в удобное время: сначала перезагрузите Fedora обычным способом, дождитесь загрузки/сети и повторите обе группы проверок. Затем при необходимости отдельно проверьте reboot VPS, учитывая, что он временно прервёт и другие размещённые там сервисы. Эта документация сама ничего не перезагружает.

## Если Jellyfin или туннель не вернулись

- После `docker compose stop jellyfin` / `docker stop` политика `unless-stopped` сохраняет ручную остановку и после reboot. Верните сервис командой `docker compose up -d jellyfin`.
- После `docker compose down` контейнер удалён, поэтому Docker нечего запускать. Восстановите Jellyfin командой `docker compose up -d jellyfin`; запуск всего стека — отдельное действие.
- После явной остановки/перезапуска Docker зависимый Xray-клиент может остаться остановленным из-за `Requires=`. После восстановления Docker выполните `sudo systemctl start xray-jellyfin-client.service`. `Restart=on-failure` не отменяет остановку по зависимости или `systemctl stop`.
- Если Docker не смог стартовать при загрузке, сначала исправьте его причину, затем запустите клиент. Не перезапускайте Docker на VPS для диагностики Jellyfin: контейнеры Amnezia обслуживаются независимо.
- Если система загрузилась до монтирования внешнего диска, проверьте пути `config/jellyfin` и `data/media`. Не запускайте контейнер с пустыми подменёнными каталогами. Для внешнего хранилища отдельно настройте монтирование до старта контейнеров.
- При временной потере сети Xray пытается переподключиться. Если после восстановления сети VPS всё ещё не получает HTTP-ответ, проверьте обе стороны; одного `active` недостаточно.

## Просмотр через SSH

На компьютере, где будет открыт браузер, задайте **свои** адрес VPS и SSH-логин вместо `VPS_HOST` / `SSH_USER`:

```bash
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
  -L 127.0.0.1:18096:127.0.0.1:18096 SSH_USER@VPS_HOST
```

Проверьте fingerprint SSH-сервера по доверенному каналу при первом подключении. Оставьте команду работающей и откройте `http://127.0.0.1:18096` в браузере **на том же компьютере**. HTTP здесь идёт внутри SSH и REALITY; порт на VPS не становится публичным. Если локальный 18096 занят, используйте, например, `-L 127.0.0.1:18097:127.0.0.1:18096` и адрес браузера с портом 18097. Закрытие SSH завершает этот способ просмотра, но не системный reverse tunnel.

## Диагностика

| Симптом | Что проверить |
| --- | --- |
| Fedora: нет ответа от `8096` | Docker, статус/логи только Jellyfin, публикацию порта и диски |
| VPS: `18096` не слушает | Сервис `xray-jellyfin`, путь конфига, проверку `run -test`, конфликт портов |
| VPS: reset / `non existing outTag: reverse-out` | Клиент ещё не зарегистрировался: сеть до VPS:8443, совпадение UUID/ключевой пары/shortId/SNI, логи обеих сторон |
| Reverse зарегистрирован, но Jellyfin не отвечает | Маршрут `reverse-in` → `jellyfin-local`, `redirect`, точное разрешение TCP `127.0.0.1:8096` в `finalRules` |
| REALITY handshake не проходит | Версию обеих сторон, время, `www.bing.com:443`, SNI `www.bing.com`, согласованные параметры |
| Сервис не стартует после установки unit | `systemctl cat` только нужного unit, старые drop-in, права root на каталог/бинарник, journal и SELinux AVC на Fedora |

Команды чтения логов (смотреть локально):

```bash
# Fedora
sudo journalctl -b -u xray-jellyfin-client.service -n 80 --no-pager
docker compose logs --tail=80 jellyfin

# VPS
sudo journalctl -b -u xray-jellyfin.service -n 80 --no-pager
sudo /opt/xray-jellyfin/xray tls ping www.bing.com
```

У TLS ping проверяйте успешный handshake **с SNI**. Доступность target может меняться; успешный TCP-коннект к 8443 сам по себе не подтверждает REALITY или reverse. При отказе SELinux разбирайте конкретный AVC и корректность контекста файла, не отключайте SELinux целиком. Не включайте `debug` / `show: true` постоянно. Перед передачей логов удаляйте адреса, UUID, privateKey, Password/publicKey, shortId, токены и пользовательские данные.

## Резервные копии и откат

Храните вне Git защищённые копии конфига каждой машины, соответствующего unit и его drop-in, а также состояния Jellyfin в `config/jellyfin`. Для согласованной копии базы Jellyfin остановите только Jellyfin на время копирования либо используйте поддерживаемую процедуру резервирования; после этого обязательно запустите контейнер снова. Не делайте `docker compose down` для всего стека ради бэкапа одного сервиса.

Для отката выберите локально предыдущий конфиг, проверьте его `xray run -test -config /PATH/TO/BACKUP`, восстановите `/opt/xray-jellyfin/config.json` с владельцем `root:root` и правами `600`. Если откатывался unit/drop-in, выполните `sudo systemctl daemon-reload`. Перезапустите только `xray-jellyfin` на VPS или `xray-jellyfin-client` на Fedora; повторите HTTP-проверки. Если менялись учётные данные, восстанавливайте согласованную пару сторон.

## Проверка перед коммитом

`.gitignore` исключает рабочие JSON, `.env`, ключи, логи, локальные каталоги и типовые бэкапы. Шаблоны `config.example.json` остаются разрешены. Это защита от случайного добавления, а не сканер: уже отслеживаемые файлы игнорированием не скрываются, `git add -f` его обходит.

Добавляйте конкретные файлы, а не весь каталог с рабочими настройками. Просмотрите staged diff локально:

```bash
git status --short
git diff --cached --check
git diff --cached --stat
git diff --cached
git check-ignore deploy/xray-jellyfin/vps/config.json deploy/xray-jellyfin/fedora/config.json .env client.env
```

В diff допустимы только маркеры вместо UUID, REALITY private/public Password, shortId и адреса VPS. Не допускаются домашний IP, токены, пароли, реальные домены вашей установки, дампы конфигов и вывод генерации ключей. Проверяйте новые файлы и неожиданные двоичные файлы, а не только изменённые строки README. Не сохраняйте секреты даже во временном коммите. При уже опубликованном секрете удаление строки недостаточно: замените скомпрометированные параметры и отдельно очистите историю.

Шаблоны JSON проверены Xray 26.2.6 с одноразовыми тестовыми параметрами; unit-файлы проверены `systemd-analyze verify`. Это проверка конфигурации, а не повторный тест вашего VPS или reboot. Проверки работающей системы выше выполняются на соответствующих машинах.
