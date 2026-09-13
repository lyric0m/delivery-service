from sqlalchemy.orm import Session
from sqlalchemy import and_, text
from models import Product, Darkstore, Inventory
from schemas import ProductCreate, ProductUpdate, DarkstoreCreate, DarkstoreUpdate, InventoryCreate, InventoryUpdate

# Product CRUD
def get_product(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id).first()

def get_products(db: Session, skip: int = 0, limit: int = 100, category: str = None):
    query = db.query(Product)
    if category:
        query = query.filter(Product.category == category)
    return query.offset(skip).limit(limit).all()

def create_product(db: Session, product: ProductCreate):
    db_product = Product(
        name=product.name,
        category=product.category,
        price=product.price,
        description=product.description
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def update_product(db: Session, product_id: int, product_update: ProductUpdate):
    db_product = get_product(db, product_id)
    if not db_product:
        return None
    
    update_data = product_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_product, field, value)
    
    db.commit()
    db.refresh(db_product)
    return db_product

def delete_product(db: Session, product_id: int):
    db_product = get_product(db, product_id)
    if not db_product:
        return None
    db.delete(db_product)
    db.commit()
    
    # Сброс счетчика последовательности для переиспользования ID
    max_id_result = db.query(Product.id).order_by(Product.id.desc()).first()
    if max_id_result and max_id_result[0] is not None:
        max_id = max_id_result[0]
        db.execute(text("SELECT setval('products_id_seq', :max_id)"), {"max_id": max_id})
    else:
        db.execute(text("SELECT setval('products_id_seq', 1, false)"))
    db.commit()
    
    return db_product

# Darkstore CRUD
def get_darkstore(db: Session, darkstore_id: int):
    return db.query(Darkstore).filter(Darkstore.id == darkstore_id).first()

def get_darkstores(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Darkstore).offset(skip).limit(limit).all()

def create_darkstore(db: Session, darkstore: DarkstoreCreate):
    db_darkstore = Darkstore(
        name=darkstore.name,
        address=darkstore.address
    )
    db.add(db_darkstore)
    db.commit()
    db.refresh(db_darkstore)
    return db_darkstore

def update_darkstore(db: Session, darkstore_id: int, darkstore_update: DarkstoreUpdate):
    db_darkstore = get_darkstore(db, darkstore_id)
    if not db_darkstore:
        return None
    
    update_data = darkstore_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_darkstore, field, value)
    
    db.commit()
    db.refresh(db_darkstore)
    return db_darkstore

def delete_darkstore(db: Session, darkstore_id: int):
    db_darkstore = get_darkstore(db, darkstore_id)
    if not db_darkstore:
        return None
    db.delete(db_darkstore)
    db.commit()
    
    # Сброс счетчика последовательности для переиспользования ID
    max_id_result = db.query(Darkstore.id).order_by(Darkstore.id.desc()).first()
    if max_id_result and max_id_result[0] is not None:
        max_id = max_id_result[0]
        db.execute(text("SELECT setval('darkstores_id_seq', :max_id)"), {"max_id": max_id})
    else:
        db.execute(text("SELECT setval('darkstores_id_seq', 1, false)"))
    db.commit()
    
    return db_darkstore

# Inventory CRUD
def get_inventory(db: Session, inventory_id: int):
    return db.query(Inventory).filter(Inventory.id == inventory_id).first()

def get_inventory_by_product_and_darkstore(db: Session, product_id: int, darkstore_id: int):
    return db.query(Inventory).filter(
        and_(Inventory.product_id == product_id, Inventory.darkstore_id == darkstore_id)
    ).first()

def get_inventories_by_darkstore(db: Session, darkstore_id: int, skip: int = 0, limit: int = 100):
    # Проверка существования даркстора
    darkstore = get_darkstore(db, darkstore_id)
    if not darkstore:
        return None  # Возвращаем None, если даркстор не существует
    return db.query(Inventory).filter(Inventory.darkstore_id == darkstore_id).offset(skip).limit(limit).all()

def get_inventories_by_product(db: Session, product_id: int, skip: int = 0, limit: int = 100):
    return db.query(Inventory).filter(Inventory.product_id == product_id).offset(skip).limit(limit).all()

def create_inventory(db: Session, inventory: InventoryCreate):
    # Проверка существования товара и даркстора
    product = get_product(db, inventory.product_id)
    if not product:
        return None
    
    darkstore = get_darkstore(db, inventory.darkstore_id)
    if not darkstore:
        return None
    
    # Проверка, не существует ли уже запись
    existing = get_inventory_by_product_and_darkstore(db, inventory.product_id, inventory.darkstore_id)
    if existing:
        return None  # Уже существует
    
    db_inventory = Inventory(
        product_id=inventory.product_id,
        darkstore_id=inventory.darkstore_id,
        quantity=inventory.quantity
    )
    db.add(db_inventory)
    db.commit()
    db.refresh(db_inventory)
    return db_inventory

def update_inventory(db: Session, inventory_id: int, inventory_update: InventoryUpdate):
    db_inventory = get_inventory(db, inventory_id)
    if not db_inventory:
        return None
    
    db_inventory.quantity = inventory_update.quantity
    db.commit()
    db.refresh(db_inventory)
    return db_inventory

def update_inventory_quantity(db: Session, product_id: int, darkstore_id: int, quantity: int):
    """Обновление количества товара в дарксторе (для резервирования/освобождения)"""
    db_inventory = get_inventory_by_product_and_darkstore(db, product_id, darkstore_id)
    if not db_inventory:
        return None
    
    db_inventory.quantity = quantity
    db.commit()
    db.refresh(db_inventory)
    return db_inventory

def delete_inventory(db: Session, inventory_id: int):
    db_inventory = get_inventory(db, inventory_id)
    if not db_inventory:
        return None
    db.delete(db_inventory)
    db.commit()
    return db_inventory

def check_product_availability(db: Session, product_id: int, darkstore_id: int, required_quantity: int):
    """Проверка доступности товара в дарксторе"""
    inventory = get_inventory_by_product_and_darkstore(db, product_id, darkstore_id)
    if not inventory:
        return False
    return inventory.quantity >= required_quantity

def reserve_inventory_quantity(db: Session, product_id: int, darkstore_id: int, quantity: int):
    """Резервирование товара (уменьшение количества)"""
    db_inventory = get_inventory_by_product_and_darkstore(db, product_id, darkstore_id)
    if not db_inventory:
        return None
    
    # Проверяем, что достаточно товара
    if db_inventory.quantity < quantity:
        return None
    
    # Уменьшаем количество
    db_inventory.quantity -= quantity
    db.commit()
    db.refresh(db_inventory)
    return db_inventory

def release_inventory_quantity(db: Session, product_id: int, darkstore_id: int, quantity: int):
    """Освобождение товара (увеличение количества)"""
    db_inventory = get_inventory_by_product_and_darkstore(db, product_id, darkstore_id)
    if not db_inventory:
        return None
    
    # Увеличиваем количество
    db_inventory.quantity += quantity
    db.commit()
    db.refresh(db_inventory)
    return db_inventory
