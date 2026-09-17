# 9. RuTracker.org и FlareSolverr

Эта глава — настройка Prowlarr для вашей учётной записи RuTracker.org и необязательного прокси FlareSolverr. Используйте только материалы, к которым у вас есть право доступа, и соблюдайте правила источника. Действующие логин, пароль, API-ключи и cookies храните только в локальных настройках приложений, не в Git.

## 1. Проверка контейнера

FlareSolverr входит в обычный запуск `docker compose up -d`. Убедитесь, что сервис запущен:

```bash
docker compose ps flaresolverr
docker compose logs --tail=50 flaresolverr
```

В сети Compose Prowlarr обращается к нему по `http://flaresolverr:8191`. Порт `8191` не опубликован на Fedora-хосте; открывать его в firewall не нужно.

## 2. Прокси в Prowlarr

Откройте `http://localhost:9696` → **Settings → Indexer Proxies** → **+** → **FlareSolverr**. Задайте:

| Поле | Значение |
| --- | --- |
| Name | `FlareSolverr` |
| Host | `http://flaresolverr:8191` |
| Tags | `rutracker` |
| Request Timeout | `60` секунд по умолчанию |

Нажмите **Test**, затем **Save**. Тег обязателен: без совпадающего тега индексатора Prowlarr отключает прокси. По [документации Prowlarr](https://wiki.servarr.com/prowlarr/settings#indexer-proxies), FlareSolverr вызывается только когда Prowlarr распознаёт защиту Cloudflare; успешный тест прокси сам по себе не гарантирует работу индексатора.

## 3. RuTracker.org в Prowlarr

Откройте **Indexers → Add Indexer**, найдите **RuTracker.org**. Prowlarr поддерживает этот индексатор [встроенным определением](https://github.com/Prowlarr/Prowlarr/blob/develop/src/NzbDrone.Core/Indexers/Definitions/RuTracker.cs). Введите данные своей учётной записи в поля формы; выберите доступный официальный адрес из списка самого Prowlarr. Добавьте тот же тег `rutracker`, нажмите **Test**, затем **Save**.

Не вводите `localhost:8191` в поле прокси: внутри Prowlarr `localhost` указывает на контейнер Prowlarr. Не копируйте cookies из браузера в проект. При сбое проверьте сначала вход на сайт и права учётной записи, затем совпадение тегов и журналы Prowlarr/FlareSolverr. Если Prowlarr не распознал Cloudflare или сайт требует иной способ доступа, FlareSolverr может не использоваться. Уважайте ограничения сайта; не меняйте зеркала и адреса ради обхода ограничений доступа.

## 4. Синхронизация с Radarr и Sonarr

Настройте приложения в **Settings → Apps** по [главе Prowlarr](03-prowlarr.md). После успешного теста индексатора выполните штатную синхронизацию индексаторов. Проверьте, что он появился в нужных приложениях. Prowlarr передаёт настройки источника; FlareSolverr остаётся внутренним сервисом Prowlarr.
