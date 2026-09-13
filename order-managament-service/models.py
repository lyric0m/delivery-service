from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class OrderStatus(str, enum.Enum):
    """Статусы заказа"""
    CREATED = "created"  # Создан
    PENDING_PAYMENT = "pending_payment"  # Ожидание оплаты
    PAID = "paid"  # Оплачен
    ASSEMBLY = "assembly"  # Передан на сборку
    COMPLETED = "completed"  # Завершен
    CANCELLED = "cancelled"  # Отменен

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    darkstore_id = Column(Integer, nullable=False, index=True)
    status = Column(SQLEnum(OrderStatus), nullable=False, default=OrderStatus.CREATED, index=True)
    total_amount = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связь с элементами заказа
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    
    __table_args__ = (
        {'sqlite_autoincrement': True}
    )

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    product_name = Column(String, nullable=False)  # Сохраняем название товара на момент заказа
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)  # Сохраняем цену товара на момент заказа
    
    # Связь с заказом
    order = relationship("Order", back_populates="items")
    
    __table_args__ = (
        {'sqlite_autoincrement': True}
    )
