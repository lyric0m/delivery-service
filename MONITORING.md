# Мониторинг и метрики

## Обзор

Система мониторинга включает:
- **Prometheus** - сбор и хранение метрик
- **Grafana** - визуализация метрик и дашборды

## Доступ к сервисам мониторинга

### Prometheus
- URL: http://localhost:9090
- Используется для:
  - Просмотра метрик в реальном времени
  - Выполнения PromQL запросов
  - Настройки алертов

### Grafana
- URL: http://localhost:3000
- Логин: `admin`
- Пароль: `admin`
- Используется для:
  - Визуализации метрик
  - Создания дашбордов
  - Настройки уведомлений

## Метрики сервисов

### User Service (http://localhost:8001/metrics)
- `http_requests_total` - общее количество HTTP запросов
- `http_request_duration_seconds` - длительность запросов

### Catalog Service (http://localhost:8002/metrics)
- `http_requests_total` - общее количество HTTP запросов
- `http_request_duration_seconds` - длительность запросов

### Order Service (http://localhost:8003/metrics)
- `http_requests_total` - общее количество HTTP запросов
- `http_request_duration_seconds` - длительность запросов
- `orders_created_total` - количество созданных заказов
- `orders_by_status` - количество заказов по статусам

### Payment Service (http://localhost:8004/metrics)
- `http_requests_total` - общее количество HTTP запросов
- `http_request_duration_seconds` - длительность запросов

## Полезные PromQL запросы

### Общее количество запросов по сервисам
```promql
sum(rate(http_requests_total[5m])) by (service)
```

### Процент успешных запросов
```promql
sum(rate(http_requests_total{status=~"2.."}[5m])) / sum(rate(http_requests_total[5m])) * 100
```

### Процент ошибок
```promql
sum(rate(http_requests_total{status=~"(4|5).."}[5m])) / sum(rate(http_requests_total[5m])) * 100
```

### Количество заказов по статусам
```promql
sum(orders_by_status) by (status)
```

### Статус доступности сервисов
```promql
up{job=~"(user-service|catalog-service|order-service|payment-service)"}
```

### P95 latency по сервисам
```promql
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))
```

## Дашборды Grafana

### Delivery Service - Overview
Основной дашборд с обзором всех сервисов:
- HTTP запросы по сервисам
- Время отклика (p95)
- Количество заказов
- Статусы заказов
- Коды ответов HTTP

### Services - Detailed Metrics
Детальный дашборд по каждому сервису:
- Requests/sec по каждому сервису
- Error rate
- Success rate

## Настройка алертов

В Prometheus можно настроить алерты через `prometheus/alerts.yml`:

```yaml
groups:
  - name: service_alerts
    rules:
      - alert: ServiceDown
        expr: up{job=~"(user-service|catalog-service|order-service|payment-service)"} == 0
        for: 1m
        annotations:
          summary: "Service {{ $labels.job }} is down"
      
      - alert: HighErrorRate
        expr: sum(rate(http_requests_total{status=~"(4|5).."}[5m])) / sum(rate(http_requests_total[5m])) > 0.1
        for: 5m
        annotations:
          summary: "High error rate detected"
```

## Проверка здоровья сервисов

Все сервисы предоставляют эндпоинт `/health`:
- http://localhost:8001/health - User Service
- http://localhost:8002/health - Catalog Service
- http://localhost:8003/health - Order Service
- http://localhost:8004/health - Payment Service

## Проверка работы мониторинга

### Шаг 1: Проверка доступности сервисов
Убедитесь, что все сервисы запущены и доступны:
```bash
docker-compose ps
```

### Шаг 2: Проверка метрик в Prometheus
1. Откройте Prometheus: http://localhost:9090
2. Перейдите в Status → Targets
3. Убедитесь, что все targets (user-service, catalog-service, order-service, payment-service) имеют статус "UP"

### Шаг 3: Проверка экспорта метрик
Проверьте, что сервисы экспортируют метрики:
- http://localhost:8001/metrics - User Service
- http://localhost:8002/metrics - Catalog Service
- http://localhost:8003/metrics - Order Service
- http://localhost:8004/metrics - Payment Service

Вы должны увидеть метрики в формате Prometheus (текстовый формат).

### Шаг 4: Проверка дашбордов в Grafana
1. Откройте Grafana: http://localhost:3000
2. Войдите: `admin` / `admin`
3. Перейдите в Dashboards (иконка слева)
4. Должны быть доступны два дашборда:
   - **Delivery Service - Overview** - обзор всех сервисов
   - **Services - Detailed Metrics** - детальные метрики

### Шаг 5: Проверка запросов в Grafana
Если графики пустые, проверьте:
1. Перейдите в Configuration → Data Sources
2. Убедитесь, что Prometheus datasource подключен и работает (кнопка "Test")
3. В дашборде откройте панель и проверьте запрос (Edit → Query)
4. Попробуйте выполнить запрос в Prometheus напрямую: http://localhost:9090/graph

### Частые проблемы

**Проблема: Нет данных в Grafana**
- Решение: Убедитесь, что Prometheus собирает метрики (Status → Targets)
- Решение: Проверьте, что сервисы экспортируют метрики (/metrics endpoint)
- Решение: Перезапустите Grafana: `docker-compose restart grafana`

**Проблема: Метрики не собираются**
- Решение: Проверьте, что все сервисы запущены: `docker-compose ps`
- Решение: Проверьте логи Prometheus: `docker logs prometheus`
- Решение: Проверьте сеть Docker: все сервисы должны быть в одной сети `delivery-network`

**Проблема: Дашборды не загружаются**
- Решение: Проверьте конфигурацию provisioning: `grafana/provisioning/dashboards/default.yml`
- Решение: Проверьте права доступа к файлам дашбордов
- Решение: Перезапустите Grafana: `docker-compose restart grafana`

## Рекомендации

1. **Регулярно проверяйте метрики** в Grafana для выявления проблем
2. **Настройте алерты** для критических метрик
3. **Мониторьте latency** - высокое время отклика может указывать на проблемы
4. **Отслеживайте error rate** - рост ошибок требует внимания
5. **Следите за количеством заказов** - это ключевой бизнес-метрика
