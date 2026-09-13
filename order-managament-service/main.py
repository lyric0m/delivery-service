from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from decimal import Decimal

from database import get_db, engine, Base
from models import Order, OrderStatus
from schemas import (
    OrderCreate, OrderResponse, OrderUpdate, OrderSummary,
    PaymentRequest, PaymentResponse, PaymentWebhook
)
from crud import (
    get_order, get_orders_by_user, get_orders_by_status, get_all_orders,
    create_order, update_order_status, cancel_order, delete_order
)
from auth import get_user_id, get_user_roles
from external_services import (
    check_products_availability, get_product_info,
    process_payment, reserve_products, release_products
)

# Создание таблиц
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Order Management Service", version="1.0.0")

security = HTTPBearer()

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

orders_created_total = Counter(
    'orders_created_total',
    'Total orders created'
)

orders_by_status = Counter(
    'orders_by_status',
    'Orders by status',
    ['status']
)

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> int:
    """Получение ID текущего пользователя"""
    token = credentials.credentials
    user_id = await get_user_id(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id

async def get_current_user_roles(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> List[str]:
    """Получение ролей текущего пользователя"""
    token = credentials.credentials
    roles = await get_user_roles(token)
    if not roles:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return roles

# ==================== ORDERS SECTION ====================

@app.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED, tags=["Orders"])
async def create_order_endpoint(
    order: OrderCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Создание нового заказа"""
    # Проверка доступности всех товаров
    items_data = [{"product_id": item.product_id, "quantity": item.quantity} for item in order.items]
    is_available, error_message = await check_products_availability(items_data, order.darkstore_id)
    
    if not is_available:
        http_requests_total.labels(method='POST', endpoint='/orders', status=400).inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message or "Products not available"
        )
    
    # Получение информации о товарах и расчет общей суммы
    total_amount = Decimal('0.00')
    items_with_info = []
    
    for item in order.items:
        product_info = await get_product_info(item.product_id)
        if not product_info:
            http_requests_total.labels(method='POST', endpoint='/orders', status=404).inc()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {item.product_id} not found"
            )
        
        product_price = Decimal(str(product_info["price"]))
        item_total = product_price * item.quantity
        total_amount += item_total
        
        items_with_info.append({
            "product_id": item.product_id,
            "product_name": product_info["name"],
            "quantity": item.quantity,
            "price": product_price
        })
    
    # Создание заказа
    order_data = {
        "user_id": user_id,
        "darkstore_id": order.darkstore_id,
        "total_amount": total_amount,
        "items": items_with_info
    }
    
    db_order = create_order(db, order_data)
    
    # Переводим заказ в статус ожидания оплаты
    update_order_status(db, db_order.id, OrderStatus.PENDING_PAYMENT)
    db.refresh(db_order)
    
    orders_created_total.inc()
    orders_by_status.labels(status=OrderStatus.PENDING_PAYMENT.value).inc()
    http_requests_total.labels(method='POST', endpoint='/orders', status=201).inc()
    
    return db_order

@app.get("/orders", response_model=List[OrderSummary], tags=["Orders"])
async def list_orders(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[OrderStatus] = None,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Получение списка заказов"""
    # Админы и менеджеры могут видеть все заказы, обычные пользователи - только свои
    if "admin" in roles or "manager" in roles:
        if status_filter:
            orders = get_orders_by_status(db, status_filter, skip=skip, limit=limit)
        else:
            orders = get_all_orders(db, skip=skip, limit=limit)
    else:
        orders = get_orders_by_user(db, user_id, skip=skip, limit=limit)
    
    http_requests_total.labels(method='GET', endpoint='/orders', status=200).inc()
    return orders

@app.get("/orders/{order_id}", response_model=OrderResponse, tags=["Orders"])
async def get_order_endpoint(
    order_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Получение информации о заказе"""
    db_order = get_order(db, order_id)
    if not db_order:
        http_requests_total.labels(method='GET', endpoint=f'/orders/{order_id}', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Проверка прав доступа: пользователь может видеть только свои заказы, админы и менеджеры - все
    if "admin" not in roles and "manager" not in roles and db_order.user_id != user_id:
        http_requests_total.labels(method='GET', endpoint=f'/orders/{order_id}', status=403).inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own orders"
        )
    
    http_requests_total.labels(method='GET', endpoint=f'/orders/{order_id}', status=200).inc()
    return db_order

@app.post("/orders/{order_id}/pay", response_model=OrderResponse, tags=["Orders"])
async def pay_order_endpoint(
    order_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Оплата заказа"""
    db_order = get_order(db, order_id)
    if not db_order:
        http_requests_total.labels(method='POST', endpoint=f'/orders/{order_id}/pay', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Проверка прав доступа
    if db_order.user_id != user_id:
        http_requests_total.labels(method='POST', endpoint=f'/orders/{order_id}/pay', status=403).inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only pay for your own orders"
        )
    
    # Проверка статуса заказа
    if db_order.status != OrderStatus.PENDING_PAYMENT:
        http_requests_total.labels(method='POST', endpoint=f'/orders/{order_id}/pay', status=400).inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order is in {db_order.status.value} status, cannot be paid"
        )
    
    # Обработка платежа
    success, payment_result = await process_payment(order_id, db_order.total_amount)
    
    if not success:
        http_requests_total.labels(method='POST', endpoint=f'/orders/{order_id}/pay', status=402).inc()
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=payment_result or "Payment failed"
        )
    
    # Обновление статуса заказа на "Оплачен"
    db_order = update_order_status(db, order_id, OrderStatus.PAID)
    
    # Резервирование товаров
    items_data = [{"product_id": item.product_id, "quantity": item.quantity} for item in db_order.items]
    await reserve_products(items_data, db_order.darkstore_id)
    
    orders_by_status.labels(status=OrderStatus.PAID.value).inc()
    http_requests_total.labels(method='POST', endpoint=f'/orders/{order_id}/pay', status=200).inc()
    
    return db_order

@app.post("/orders/payment-webhook", response_model=dict, tags=["Orders"], include_in_schema=False)
async def payment_webhook_endpoint(
    webhook: PaymentWebhook,
    db: Session = Depends(get_db)
):
    """
    Webhook для получения уведомлений от payment-service об успешных платежах
    Этот эндпоинт вызывается payment-service после успешной обработки платежа
    """
    if not webhook.success:
        http_requests_total.labels(method='POST', endpoint='/orders/payment-webhook', status=400).inc()
        return {"status": "ignored", "reason": "Payment was not successful"}
    
    db_order = get_order(db, webhook.order_id)
    if not db_order:
        http_requests_total.labels(method='POST', endpoint='/orders/payment-webhook', status=404).inc()
        return {"status": "error", "reason": "Order not found"}
    
    # Проверяем, что заказ еще не оплачен
    if db_order.status == OrderStatus.PAID:
        http_requests_total.labels(method='POST', endpoint='/orders/payment-webhook', status=200).inc()
        return {"status": "already_paid", "order_id": db_order.id}
    
    # Обновляем статус заказа на "Оплачен"
    db_order = update_order_status(db, webhook.order_id, OrderStatus.PAID)
    
    # Резервирование товаров
    items_data = [{"product_id": item.product_id, "quantity": item.quantity} for item in db_order.items]
    await reserve_products(items_data, db_order.darkstore_id)
    
    orders_by_status.labels(status=OrderStatus.PAID.value).inc()
    http_requests_total.labels(method='POST', endpoint='/orders/payment-webhook', status=200).inc()
    
    return {"status": "success", "order_id": db_order.id, "new_status": db_order.status.value}

@app.post("/orders/{order_id}/cancel", response_model=OrderResponse, tags=["Orders"])
async def cancel_order_endpoint(
    order_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Отмена заказа"""
    db_order = get_order(db, order_id)
    if not db_order:
        http_requests_total.labels(method='POST', endpoint=f'/orders/{order_id}/cancel', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Проверка прав доступа
    if "admin" not in roles and "manager" not in roles and db_order.user_id != user_id:
        http_requests_total.labels(method='POST', endpoint=f'/orders/{order_id}/cancel', status=403).inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel your own orders"
        )
    
    # Проверка статуса заказа (можно отменить только созданные или ожидающие оплаты заказы)
    if db_order.status in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
        http_requests_total.labels(method='POST', endpoint=f'/orders/{order_id}/cancel', status=400).inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel order in {db_order.status.value} status"
        )
    
    # Если заказ был оплачен, освобождаем товары
    if db_order.status == OrderStatus.PAID:
        items_data = [{"product_id": item.product_id, "quantity": item.quantity} for item in db_order.items]
        await release_products(items_data, db_order.darkstore_id)
    
    db_order = cancel_order(db, order_id)
    orders_by_status.labels(status=OrderStatus.CANCELLED.value).inc()
    http_requests_total.labels(method='POST', endpoint=f'/orders/{order_id}/cancel', status=200).inc()
    
    return db_order

@app.put("/orders/{order_id}/status", response_model=OrderResponse, tags=["Orders"])
async def update_order_status_endpoint(
    order_id: int,
    order_update: OrderUpdate,
    db: Session = Depends(get_db),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Обновление статуса заказа (только для менеджеров и администраторов)"""
    if "admin" not in roles and "manager" not in roles:
        http_requests_total.labels(method='PUT', endpoint=f'/orders/{order_id}/status', status=403).inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers and administrators can update order status"
        )
    
    if not order_update.status:
        http_requests_total.labels(method='PUT', endpoint=f'/orders/{order_id}/status', status=400).inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status is required"
        )
    
    db_order = update_order_status(db, order_id, order_update.status)
    if not db_order:
        http_requests_total.labels(method='PUT', endpoint=f'/orders/{order_id}/status', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    orders_by_status.labels(status=order_update.status.value).inc()
    http_requests_total.labels(method='PUT', endpoint=f'/orders/{order_id}/status', status=200).inc()
    
    return db_order

@app.delete("/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Orders"])
async def delete_order_endpoint(
    order_id: int,
    db: Session = Depends(get_db),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Удаление заказа (только для администраторов)"""
    if "admin" not in roles:
        http_requests_total.labels(method='DELETE', endpoint=f'/orders/{order_id}', status=403).inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete orders"
        )
    
    db_order = delete_order(db, order_id)
    if not db_order:
        http_requests_total.labels(method='DELETE', endpoint=f'/orders/{order_id}', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    http_requests_total.labels(method='DELETE', endpoint=f'/orders/{order_id}', status=204).inc()
    return None

# ==================== DEFAULT ENDPOINTS ====================

@app.get("/metrics", tags=["default"])
async def metrics():
    """Метрики Prometheus"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health", tags=["default"])
async def health():
    """Проверка здоровья сервиса"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
