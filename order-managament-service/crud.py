from sqlalchemy.orm import Session
from sqlalchemy import text
from models import Order, OrderItem, OrderStatus
from schemas import OrderCreate, OrderUpdate
from datetime import datetime

# Order CRUD
def get_order(db: Session, order_id: int):
    return db.query(Order).filter(Order.id == order_id).first()

def get_orders_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(Order).filter(Order.user_id == user_id).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()

def get_orders_by_status(db: Session, status: OrderStatus, skip: int = 0, limit: int = 100):
    return db.query(Order).filter(Order.status == status).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()

def get_all_orders(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Order).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()

def create_order(db: Session, order_data: dict):
    """Создание заказа с элементами"""
    db_order = Order(
        user_id=order_data["user_id"],
        darkstore_id=order_data["darkstore_id"],
        status=OrderStatus.CREATED,
        total_amount=order_data["total_amount"]
    )
    db.add(db_order)
    db.flush()  # Получаем ID заказа
    
    # Создаем элементы заказа
    for item_data in order_data["items"]:
        db_item = OrderItem(
            order_id=db_order.id,
            product_id=item_data["product_id"],
            product_name=item_data["product_name"],
            quantity=item_data["quantity"],
            price=item_data["price"]
        )
        db.add(db_item)
    
    db.commit()
    db.refresh(db_order)
    return db_order

def update_order_status(db: Session, order_id: int, new_status: OrderStatus):
    """Обновление статуса заказа"""
    db_order = get_order(db, order_id)
    if not db_order:
        return None
    
    db_order.status = new_status
    db_order.updated_at = datetime.utcnow()
    
    # Устанавливаем дополнительные временные метки в зависимости от статуса
    if new_status == OrderStatus.PAID:
        db_order.paid_at = datetime.utcnow()
    elif new_status == OrderStatus.COMPLETED:
        db_order.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_order)
    return db_order

def cancel_order(db: Session, order_id: int):
    """Отмена заказа"""
    return update_order_status(db, order_id, OrderStatus.CANCELLED)

def delete_order(db: Session, order_id: int):
    """Удаление заказа"""
    db_order = get_order(db, order_id)
    if not db_order:
        return None
    db.delete(db_order)
    db.commit()
    
    # Сброс счетчика последовательности для переиспользования ID
    max_id_result = db.query(Order.id).order_by(Order.id.desc()).first()
    if max_id_result and max_id_result[0] is not None:
        max_id = max_id_result[0]
        db.execute(text("SELECT setval('orders_id_seq', :max_id)"), {"max_id": max_id})
    else:
        db.execute(text("SELECT setval('orders_id_seq', 1, false)"))
    db.commit()
    
    return db_order
