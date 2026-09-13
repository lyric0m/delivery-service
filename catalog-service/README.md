# Catalog & Inventory Service

Микросервис управления каталогом и складскими остатками.

## Описание

Сервис предназначен для:
- Управления каталогом товаров (Product)
- Управления дарксторами (Darkstore)
- Учета складских остатков (Inventory) по каждому даркстору

## Структура данных

### Product (Товар)
- `id` - идентификатор
- `name` - наименование
- `category` - категория
- `price` - цена
- `description` - описание (опционально)

### Darkstore (Даркстор)
- `id` - идентификатор
- `name` - название
- `address` - адрес (опционально)

### Inventory (Складской остаток)
- `id` - идентификатор
- `product_id` - идентификатор товара
- `darkstore_id` - идентификатор даркстора
- `quantity` - количество товара

## API Endpoints

### Products (Товары)

- `GET /products` - Получение списка товаров (доступно всем)
- `GET /products/{product_id}` - Получение информации о товаре (доступно всем)
- `POST /products` - Создание товара (только менеджер/админ)
- `PUT /products/{product_id}` - Обновление товара (только менеджер/админ)
- `DELETE /products/{product_id}` - Удаление товара (только менеджер/админ)

### Darkstores (Дарксторы)

- `GET /darkstores` - Получение списка дарксторов (доступно всем)
- `GET /darkstores/{darkstore_id}` - Получение информации о дарксторе (доступно всем)
- `POST /darkstores` - Создание даркстора (только менеджер/админ)
- `PUT /darkstores/{darkstore_id}` - Обновление даркстора (только менеджер/админ)
- `DELETE /darkstores/{darkstore_id}` - Удаление даркстора (только менеджер/админ)

### Inventory (Складские остатки)

- `GET /inventory/darkstore/{darkstore_id}` - Получение остатков по даркстору (доступно всем)
- `GET /inventory/product/{product_id}` - Получение остатков по товару (доступно всем)
- `GET /inventory/{product_id}/{darkstore_id}` - Получение конкретного остатка (доступно всем)
- `GET /inventory/{product_id}/{darkstore_id}/check?quantity={qty}` - Проверка доступности (доступно всем)
- `POST /inventory` - Создание остатка (только менеджер/админ)
- `PUT /inventory/{inventory_id}` - Обновление остатка (только менеджер/админ)
- `PUT /inventory/{product_id}/{darkstore_id}/quantity` - Обновление количества (только менеджер/админ)
- `DELETE /inventory/{inventory_id}` - Удаление остатка (только менеджер/админ)

### Default

- `GET /health` - Проверка здоровья сервиса
- `GET /metrics` - Метрики Prometheus

## Аутентификация

Сервис использует JWT токены из user-service. Для операций создания/обновления/удаления требуется роль `manager` или `admin`.

## Переменные окружения

- `DATABASE_URL` - URL базы данных PostgreSQL
- `USER_SERVICE_URL` - URL user-service (по умолчанию: http://user-service:8001)
- `SECRET_KEY` - Секретный ключ для декодирования JWT токенов

## Запуск

```bash
docker-compose up -d --build catalog-service
```

Сервис доступен по адресу: http://localhost:8002

Swagger UI: http://localhost:8002/docs
