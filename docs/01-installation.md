# 1. Установка на Fedora 44

## Docker Engine и Compose

Следуйте [официальной инструкции Docker для Fedora](https://docs.docker.com/engine/install/fedora/). Для новой установки через RPM-репозиторий:

```bash
sudo dnf config-manager addrepo --from-repofile https://download.docker.com/linux/fedora/docker-ce.repo
sudo dnf install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker compose version
```

Если установлены конфликтующие пакеты Docker, сначала выполните шаг их удаления из официальной инструкции. Команды Docker требуют `sudo`, пока пользователь не получил доступ к сокету Docker. Членство в группе `docker` даёт права уровня root; решайте это по своей модели доступа. Не смешивайте rootless Docker с приведёнными инструкциями, не проверив работу портов и SELinux отдельно.

## Подготовка каталога

В каталоге репозитория:

```bash
cp .env.example .env
id -u
id -g
mkdir -p config/{qbittorrent,radarr,sonarr,prowlarr,jellyfin,jellyseerr} data/torrents/{movies,tv} data/media/{movies,tv}
docker compose config -q
docker compose up -d
docker compose ps
```

Значения `PUID` и `PGID` в `.env` должны соответствовать владельцу файлов. По умолчанию — `1000:1000`. `TZ` задан как `Europe/Berlin`; при необходимости измените. Если команды Docker работают только через `sudo`, используйте `sudo docker compose ...` последовательно; следите, чтобы папки данных оставались доступны заданным UID/GID.

На Fedora SELinux обычно включён. Конфигурации подключены с `:Z` (частные метки), общий каталог данных — с `:z`. Метки меняют атрибуты файлов хоста; используйте только выделенные каталоги проекта. Проверка: `getenforce`, затем `ls -Zd config/qbittorrent data` после запуска.

## Сеть

Для доступа с другого устройства в домашней сети разрешите только нужный порт в активной зоне firewalld, например Jellyfin:

```bash
sudo firewall-cmd --get-active-zones
sudo firewall-cmd --permanent --add-port=8096/tcp
sudo firewall-cmd --reload
```

Проверьте, что правило относится к нужной зоне. Адрес Jellyfin на ТВ: `http://<LAN-IP-сервера>:8096`. Локально на Fedora: `http://localhost:8096`. Для поиска IP: `hostname -I`. Порт qBittorrent `6881/tcp` и `6881/udp` опубликован на хосте; открывать его в firewall и маршрутизаторе нужно только по вашей схеме сети.

## Дальше

Настраивайте сервисы в порядке из [README](../README.md#порядок-настройки). Не сохраняйте пароли, токены и API-ключи в Git. Реальные настройки приложений останутся в `config/`, исключённом из Git.
