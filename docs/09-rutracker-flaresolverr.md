# RuTracker.org и FlareSolverr: настройка по шагам

Нужна действующая учётная запись RuTracker.org и право доступа к выбранным материалам. Логин, пароль и cookies вводите только в Prowlarr; не сохраняйте их в Git.

1. Проверьте запуск FlareSolverr: `docker compose ps flaresolverr`. Если сервис остановлен, посмотрите `docker compose logs --tail=50 flaresolverr`.
2. Откройте Prowlarr: `http://localhost:9696`.
3. Откройте **Settings → Indexer Proxies → + → FlareSolverr**. Укажите Host `http://flaresolverr:8191` и Tags `rutracker`. Нажмите **Test**, затем **Save**. Порт `8191` доступен внутри Docker; на хосте он не опубликован.
4. Откройте **Indexers → Add Indexer** и выберите **RuTracker.org**. Введите данные своей учётной записи в поля Prowlarr, выберите адрес из списка приложения и добавьте тег `rutracker`. Нажмите **Test**, затем **Save**.
5. Откройте **Settings → Apps**. Добавьте Radarr с URL `http://radarr:7878` и Sonarr с URL `http://sonarr:8989`. Введите их API-ключи из **Settings → General**, проверьте соединения и синхронизируйте индексаторы.
6. Проверьте результат: RuTracker появился в Radarr/Sonarr; тестовый поиск доступного вам материала работает. При ошибке проверьте вход на сайт, одинаковый тег у прокси и индексатора, затем журналы Prowlarr и FlareSolverr.

Prowlarr вызывает FlareSolverr только при обнаружении Cloudflare и совпадении тегов. Работа прокси не заменяет действующую учётную запись и не гарантирует доступность сайта. См. [настройки Prowlarr](https://wiki.servarr.com/prowlarr/settings#indexer-proxies) и [определение RuTracker.org](https://github.com/Prowlarr/Prowlarr/blob/develop/src/NzbDrone.Core/Indexers/Definitions/RuTracker.cs).
