from fastapi import FastAPI, HTTPException, status, Request
from pydantic import BaseModel
from typing import Optional
import uuid
import os
import httpx
from datetime import datetime
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
import time

app = FastAPI(title="Payment Service", version="1.0.0")

# URL order-service для отправки webhook
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8003")

# Prometheus метрики
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# Middleware для автоматического сбора метрик
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    method = request.method
    endpoint = request.url.path
    
    # Пропускаем сбор метрик для самого эндпоинта /metrics
    if endpoint == "/metrics":
        response = await call_next(request)
        return response
    
    try:
        response = await call_next(request)
        status_code = response.status_code
        duration = time.time() - start_time
        
        http_requests_total.labels(method=method, endpoint=endpoint, status=status_code).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
        
        return response
    except Exception as e:
        status_code = 500
        duration = time.time() - start_time
        http_requests_total.labels(method=method, endpoint=endpoint, status=status_code).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
        raise

payments_total = Counter(
    'payments_total',
    'Total payments processed',
    ['status']
)

class PaymentRequest(BaseModel):
    order_id: int
    amount: float

class PaymentResponse(BaseModel):
    success: bool
    payment_id: Optional[str] = None
    message: Optional[str] = None

@app.post("/payments", response_model=PaymentResponse, tags=["Payments"])
async def process_payment(payment: PaymentRequest):
    """
    Обработка платежа
    В реальной системе здесь была бы интеграция с платежными системами
    """
    # Простая симуляция: если сумма больше 0, платеж успешен
    if payment.amount <= 0:
        payments_total.labels(status='failed').inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment amount must be greater than 0"
        )
    
    # Генерируем ID платежа
    payment_id = str(uuid.uuid4())
    
    # В реальной системе здесь была бы проверка карты, обработка через платежный шлюз и т.д.
    # Для демонстрации всегда возвращаем успех
    payments_total.labels(status='success').inc()
    
    # Отправляем webhook в order-service для обновления статуса заказа
    # Это делается асинхронно, чтобы не блокировать ответ клиенту
    try:
        async with httpx.AsyncClient() as client:
            webhook_response = await client.post(
                f"{ORDER_SERVICE_URL}/orders/payment-webhook",
                json={
                    "order_id": payment.order_id,
                    "payment_id": payment_id,
                    "success": True,
                    "amount": float(payment.amount)
                },
                timeout=5.0
            )
            # Логируем результат, но не прерываем процесс, если webhook не удался
            if webhook_response.status_code != 200:
                print(f"Warning: Failed to notify order-service about payment: {webhook_response.status_code}")
    except Exception as e:
        # В реальной системе здесь должна быть retry логика или очередь сообщений
        print(f"Warning: Failed to send webhook to order-service: {e}")
    
    return PaymentResponse(
        success=True,
        payment_id=payment_id,
        message="Payment processed successfully"
    )

@app.get("/metrics", tags=["default"])
async def metrics():
    """Метрики Prometheus"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health", tags=["default"])
async def health():
    """Проверка здоровья сервиса"""
    # Метрики для /health собираются через middleware
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
