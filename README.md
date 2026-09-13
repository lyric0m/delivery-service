# Delivery Service - Микросервисная архитектура

Проект представляет собой систему управления доставкой, состоящую из нескольких микросервисов.

## Сервисы

1. **User Management Service** - управление пользователями, аутентификация и авторизация
2. **Catalog Service** - управление каталогом и товарами (в разработке)
3. **Order Service** - управление заказами (в разработке)
4. **Prometheus** - система мониторинга

## Технологии

- Python 3.11
- FastAPI
- PostgreSQL
- Docker & Docker Compose
- Prometheus

## Запуск проекта

### Предварительные требования

- Docker
- Docker Compose

### Запуск всех сервисов

```bash
docker-compose up --build
```

### Запуск отдельного сервиса

```bash
cd user-service
docker-compose up --build user-service
```

## User Management Service

### Система ролей

Сервис поддерживает 4 роли:
- **admin** - Администратор (может управлять ролями других пользователей)
- **manager** - Менеджер (может управлять заказами и каталогом)
- **courier** - Курьер (работает в конкретном дакрсторе)
- **client** - Клиент (обычный пользователь)

**Важно**: Один пользователь может иметь несколько ролей. Например, курьер может быть также клиентом в зависимости от дакрстора.

Роли автоматически создаются при первом запуске сервиса.

### API Endpoints

- `POST /users/register` - Регистрация нового пользователя
- `POST /users/login` - Аутентификация пользователя
- `GET /users/{user_id}` - Получение информации о пользователе (требуется авторизация)
- `GET /users/{user_id}/roles` - Получение ролей пользователя (требуется авторизация)
- `GET /roles` - Получение списка всех доступных ролей
- `POST /users/{user_id}/roles/init-admin` - Инициализация первого администратора (работает только если в системе нет администраторов)
- `PUT /users/{user_id}/roles` - Назначение ролей пользователю (только для администраторов)
- `GET /health` - Проверка здоровья сервиса
- `GET /metrics` - Метрики Prometheus

### Тестирование через Swagger

Подробная инструкция по тестированию доступна в файле [user-service/SWAGGER_TESTING.md](user-service/SWAGGER_TESTING.md)

Swagger UI доступен по адресу: **http://localhost:8001/docs**

### Примеры запросов

#### Регистрация пользователя

```bash
curl -X POST "http://localhost:8001/users/register" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+1234567890",
    "email": "user@example.com",
    "password": "password123",
    "full_name": "John Doe"
  }'
```

#### Вход в систему

```bash
curl -X POST "http://localhost:8001/users/login" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+1234567890",
    "password": "password123"
  }'
```

#### Получение информации о пользователе (требуется токен)

```bash
curl -X GET "http://localhost:8001/users/1" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

#### Получение всех ролей

```bash
curl -X GET "http://localhost:8001/roles"
```

#### Инициализация первого администратора

```bash
curl -X POST "http://localhost:8001/users/1/roles/init-admin"
```

#### Назначение ролей пользователю (требуется токен администратора)

```bash
curl -X PUT "http://localhost:8001/users/2/roles" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role_ids": [2, 4]
  }'
```

## Мониторинг

Prometheus доступен по адресу: http://localhost:9090

Метрики User Service доступны по адресу: http://localhost:8001/metrics
