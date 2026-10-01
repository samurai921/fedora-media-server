# 12. jellyfin.mediadima.ru и NVIDIA RTX 3060 Ti

## Действующая схема

```text
Телефон / ТВ / браузер
  → https://jellyfin.mediadima.ru:443
  → Caddy на VPS
  → 127.0.0.1:18096 на VPS
  → отдельный Xray REALITY reverse tunnel
  → 127.0.0.1:8096 на Fedora
  → контейнер Jellyfin → RTX 3060 Ti
```

Fedora сама устанавливает соединение с VPS по TCP 8443. Amnezia, `wdtt0`, существующий x-ui/Xray, firewall и swap не входят в эту настройку. Нельзя заменять их конфиги или перезапускать Docker целиком ради Jellyfin.

Проверено 1 октября 2026 года: локальный и публичный `/health` возвращают 200; сертификат публичного адреса проходит обычную проверку; обе точки возвращают Jellyfin 12.1.0. На Fedora `docker` и `xray-jellyfin-client` — `active` и `enabled`. RTX 3060 Ti доступна в контейнере, короткий тест H.264 NVENC завершён успешно. Эти проверки не заменяют проверку реального просмотра и reboot. SSH-проверка автозапуска Caddy/Xray на VPS не выполнена: требуется доступ владельца.

## Caddy на VPS

В [`deploy/caddy/jellyfin.caddy`](../deploy/caddy/jellyfin.caddy) хранится минимальный фрагмент для этого домена. Это воспроизводимый образец, а не выгрузка фактического `/etc/caddy/Caddyfile`. В действующий рабочий сервер он автоматически не устанавливается.

Если домен уже открывается, не создавайте второй блок. Для восстановления сначала сохраните существующий Caddyfile вне Git. На VPS проверьте, что `curl --fail --max-time 15 http://127.0.0.1:18096/health` возвращает `Healthy`, а порт 18096 слушает только `127.0.0.1`. DNS A/AAAA домена должны вести на нужный VPS; не добавляйте AAAA без работающего IPv6.

Добавьте только блок этого домена в существующую конфигурацию или импорт отдельного файла:

```caddyfile
import /etc/caddy/conf.d/jellyfin.caddy
```

Не заменяйте весь Caddyfile и не удаляйте другие сайты. Перед применением:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
systemctl is-active caddy xray-jellyfin
systemctl is-enabled caddy xray-jellyfin
curl --fail --max-time 15 https://jellyfin.mediadima.ru/health
```

Caddy обслуживает HTTPS и WebSocket через `reverse_proxy`; порт 18096 не нужно публиковать наружу. Для встроенного HTTPS внутри Jellyfin сертификат не нужен: TLS завершается на Caddy, Base URL остаётся пустым. Не используйте `curl -k` для приёмочной проверки.

Не включайте подробный access log постоянно: URL Jellyfin могут содержать токены. Секреты DNS API, SSH, TLS и Xray не входят в репозиторий.

## GPU в контейнере и NVENC в приложении

В Compose уже указаны `driver: nvidia`, `count: 1`, `capabilities: [gpu]` и `NVIDIA_DRIVER_CAPABILITIES=compute,video,utility`. Имя проекта `media-server` совпадает с работающими контейнерами. При восстановлении нужен установленный и настроенный NVIDIA Container Toolkit.

```bash
docker compose config -q
docker compose up -d --no-deps --pull never jellyfin
docker compose exec -T jellyfin nvidia-smi
```

`--pull never` использует уже установленный образ; обновление версии выполняйте отдельно после резервной копии. Не запускайте весь стек для изменения только Jellyfin.

В Jellyfin: **Панель управления → Воспроизведение → Транскодирование**:

- Аппаратное ускорение: **NVIDIA NVENC**.
- Аппаратное кодирование: включено.
- Для RTX 3060 Ti можно включить декодирование H.264, HEVC, MPEG-2, VC-1, VP9 и AV1, включая HEVC/VP9 10-bit.
- AV1-кодирование оставьте выключенным: эта карта поддерживает AV1-декодирование, но не AV1-кодирование.
- HEVC-кодирование и tone mapping не включаются автоматически; их проверяют отдельно с нужными клиентами и HDR-материалами.

Рабочие настройки Jellyfin хранятся в `config/jellyfin/encoding.xml`, который исключён из Git. Одного Compose недостаточно для выбора NVENC. Если редактируете XML вручную, сначала остановите только Jellyfin, сохраните копию файла, измените нужные поля и снова запустите контейнер. Не записывайте конфигурацию поверх работающего приложения.

## Проверки

Из корня проекта:

```bash
bash scripts/check-jellyfin.sh
bash scripts/check-jellyfin.sh --gpu
```

Второй вызов дополнительно выполняет двухсекундное кодирование синтетического видео через NVENC от пользователя `abc` внутри контейнера. Он не читает вашу медиатеку и не создаёт выходной файл.

Для проверки реального просмотра откройте публичный адрес на телефоне через мобильную сеть, выберите материал, к которому у вас есть доступ, и качество 10–20 Мбит/с, чтобы вызвать транскодирование. Убедитесь, что просмотр идёт плавно; на сервере проверьте `nvidia-smi` и активное транскодирование в панели Jellyfin. Direct Play не запускает NVENC. Успешный синтетический тест не доказывает работу HDR, субтитров или каждого видеоформата.

Если `/health` работает, а видео буферизуется, проверьте битрейт и скорость исходящего канала. NVENC уменьшает нагрузку CPU при перекодировании, но не увеличивает скорость сети.

## Адреса, локальная сеть и Seerr

`JELLYFIN_PUBLIC_URL` в `.env.example` задаёт адрес для объявления клиентам (`JELLYFIN_PublishedServerUrl`); эта переменная не настраивает DNS, Caddy, сертификат или Base URL. В этой конфигурации UDP autodiscovery не публикуется; вводите адрес в клиентах вручную.

Порт `8096:8096` пока сохраняет доступ из LAN как в действующей установке. Содержимое `config/`, `data/`, `.env` и `local/` не публикуется. Для общего медиакаталога используется SELinux `:z`; настройки отдельного сервиса остаются `:Z`.

Перед настройкой Known Proxies определите адрес непосредственного отправителя, который видит Jellyfin после Xray и Docker NAT. Он может отличаться от публичного IP VPS. Не добавляйте `0.0.0.0/0` или всю домашнюю сеть в доверенные прокси. Если NAT сводит прямые и проксированные запросы к одному адресу, сначала разделите эти пути: доверять такому адресу вслепую нельзя. Этот список автоматически не изменён.

В Seerr внутренний URL Jellyfin — `http://jellyfin:8096`, внешний URL — `https://jellyfin.mediadima.ru`. Если проверка соединения возвращает 401, повторно подключите Jellyfin через авторизованный интерфейс Seerr. Не публикуйте API-ключ и не копируйте рабочий `settings.json` в Git.

## Лимиты памяти и откат

Основной Compose сохраняет текущую установку без жёстких лимитов памяти. Прежние значения из GitHub сохранены в необязательном `compose.limits.yaml`. Они применяются только при явном `-f compose.yaml -f compose.limits.yaml`. Оцените транскодирование перед включением ограничения Jellyfin 2 ГБ; при OOM увеличьте его.

Локальные резервные копии перед правками находятся в `local/backups/` и исключены из Git. Для отката NVENC остановите только Jellyfin, восстановите сохранённый `encoding.xml` и запустите его снова. Для отката Compose восстановите сохранённый `compose.yaml`; применяйте только нужный сервис. Никогда не используйте `docker compose down -v`, `git clean` или `git reset --hard` для такого отката.

## Официальные инструкции

- [Jellyfin: Caddy](https://jellyfin.org/docs/general/post-install/networking/reverse-proxy/caddy/)
- [Jellyfin: NVIDIA](https://jellyfin.org/docs/general/post-install/transcoding/hardware-acceleration/nvidia/)
- [Jellyfin: доверенные прокси](https://jellyfin.org/docs/general/post-install/networking/reverse-proxy/)
- [LinuxServer: Jellyfin](https://docs.linuxserver.io/images/docker-jellyfin/)
