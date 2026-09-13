# Быстрое решение проблемы с отсутствующими эндпоинтами

## Проблема
Эндпоинты `GET /roles` и `POST /users/{user_id}/roles/init-admin` не отображаются в Swagger UI.

## Решение

### Вариант 1: Пересборка контейнера (рекомендуется)

```bash
cd c:\DeliveryService
docker-compose up -d --build user-service
```

Эта команда:
- Пересоберет образ с новым кодом
- Перезапустит контейнер
- Применит все изменения

### Вариант 2: Полная пересборка

```bash
cd c:\DeliveryService
docker-compose down
docker-compose up -d --build
```

### Вариант 3: Если используете локальный запуск (без Docker)

```bash
cd c:\DeliveryService\user-service
python main.py
```

## Проверка

После пересборки:

1. Откройте http://localhost:8001/docs
2. Обновите страницу (Ctrl+F5)
3. Проверьте наличие эндпоинтов:
   - `GET /roles` - должен быть в разделе "Roles"
   - `POST /users/{user_id}/roles/init-admin` - должен быть в разделе "Roles" или "Admin"

## Проверка через curl

```bash
# Проверка эндпоинта /roles
curl http://localhost:8001/roles

# Должен вернуть список ролей или пустой массив []
```

## Если проблема сохраняется

1. Проверьте логи:
   ```bash
   docker-compose logs user-service --tail=100
   ```

2. Убедитесь, что файл `main.py` содержит эндпоинты:
   - Строка ~165: `@app.get("/roles", ...)`
   - Строка ~172: `@app.post("/users/{user_id}/roles/init-admin", ...)`

3. Проверьте, что нет синтаксических ошибок:
   ```bash
   cd c:\DeliveryService\user-service
   python -m py_compile main.py
   ```
