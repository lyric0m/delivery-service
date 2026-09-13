# Order Management Service

Микросервис управления заказами.

## Описание

Сервис предназначен для:
- Создания заказов на основе выбранных товаров
- Управления жизненным циклом заказа
- Взаимодействия с другими сервисами (catalog-service, payment-service)
- Отслеживания статусов заказов

## Статусы заказа

- `created` - Создан
- `pending_payment` - Ожидание оплаты
- `paid` - Оплачен
- `assembly` - Передан на сборку
- `completed` - Завершен
- `cancelled` - Отменен

## API Endpoints

### Orders (Заказы)

- `POST /orders` - Создание нового заказа (требуется аутентификация)
- `GET /orders` - Получение списка заказов (требуется аутентификация)
  - Обычные пользователи видят только свои заказы
  - Менеджеры и админы видят все заказы
  - Параметр `status_filter` для фильтрации по статусу
- `GET /orders/{order_id}` - Получение информации о заказе (требуется аутентификация)
- `POST /orders/{order_id}/pay` - Оплата заказа (требуется аутентификация)
- `POST /orders/{order_id}/cancel` - Отмена заказа (требуется аутентификация)
- `PUT /orders/{order_id}/status` - Обновление статуса заказа (только менеджер/админ)
- `DELETE /orders/{order_id}` - Удаление заказа (только админ)

### Default

- `GET /health` - Проверка здоровья сервиса
- `GET /metrics` - Метрики Prometheus

## Аутентификация

Сервис использует JWT токены из user-service. Для всех операций требуется аутентификация.

## Взаимодействие с другими сервисами

### Catalog Service
- Проверка доступности товаров в дарксторе
- Получение информации о товарах (название, цена)

### Payment Service
- Обработка платежей за заказы

## Переменные окружения

- `DATABASE_URL` - URL базы данных PostgreSQL
- `USER_SERVICE_URL` - URL user-service (по умолчанию: http://user-service:8001)
- `CATALOG_SERVICE_URL` - URL catalog-service (по умолчанию: http://catalog-service:8002)
- `PAYMENT_SERVICE_URL` - URL payment-service (по умолчанию: http://payment-service:8004)
- `SECRET_KEY` - Секретный ключ для декодирования JWT токенов

## Метрики Prometheus

- `http_requests_total` - Общее количество HTTP запросов
- `http_request_duration_seconds` - Длительность HTTP запросов
- `orders_created_total` - Общее количество созданных заказов
- `orders_by_status` - Количество заказов по статусам
