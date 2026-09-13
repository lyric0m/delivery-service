from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from models import OrderStatus

# Order Item schemas
class OrderItemBase(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)

class OrderItemCreate(OrderItemBase):
    pass

class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    price: Decimal
    
    class Config:
        from_attributes = True

# Order schemas
class OrderBase(BaseModel):
    darkstore_id: int
    items: List[OrderItemCreate]

class OrderCreate(OrderBase):
    pass

class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None

class OrderResponse(BaseModel):
    id: int
    user_id: int
    darkstore_id: int
    status: OrderStatus
    total_amount: Decimal
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    items: List[OrderItemResponse] = []
    
    class Config:
        from_attributes = True

class OrderSummary(BaseModel):
    """Краткая информация о заказе"""
    id: int
    user_id: int
    darkstore_id: int
    status: OrderStatus
    total_amount: Decimal
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Payment schemas
class PaymentRequest(BaseModel):
    order_id: int
    amount: Decimal

class PaymentResponse(BaseModel):
    success: bool
    payment_id: Optional[str] = None
    message: Optional[str] = None

class PaymentWebhook(BaseModel):
    """Webhook от payment-service для уведомления об успешном платеже"""
    order_id: int
    payment_id: str
    success: bool
    amount: Decimal
