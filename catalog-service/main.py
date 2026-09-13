from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from database import get_db, engine, Base
from models import Product, Darkstore, Inventory
from schemas import (
    ProductCreate, ProductResponse, ProductUpdate,
    DarkstoreCreate, DarkstoreResponse, DarkstoreUpdate,
    InventoryCreate, InventoryResponse, InventoryUpdate, InventoryWithDetails,
    InventoryReserveRequest, InventoryReleaseRequest
)
from crud import (
    get_product, get_products, create_product, update_product, delete_product,
    get_darkstore, get_darkstores, create_darkstore, update_darkstore, delete_darkstore,
    get_inventory, get_inventories_by_darkstore, get_inventories_by_product,
    create_inventory, update_inventory, delete_inventory,
    check_product_availability, update_inventory_quantity,
    get_inventory_by_product_and_darkstore,
    reserve_inventory_quantity, release_inventory_quantity
)
from auth import get_user_roles, require_manager_or_admin

# Создание таблиц
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Catalog & Inventory Service", version="1.0.0")

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

# ==================== PRODUCTS SECTION ====================

@app.get("/products", response_model=List[ProductResponse], tags=["Products"])
async def list_products(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Получение списка товаров (доступно всем)"""
    products = get_products(db, skip=skip, limit=limit, category=category)
    http_requests_total.labels(method='GET', endpoint='/products', status=200).inc()
    return products

@app.get("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
async def get_product_by_id(product_id: int, db: Session = Depends(get_db)):
    """Получение информации о товаре (доступно всем)"""
    product = get_product(db, product_id)
    if not product:
        http_requests_total.labels(method='GET', endpoint=f'/products/{product_id}', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    http_requests_total.labels(method='GET', endpoint=f'/products/{product_id}', status=200).inc()
    return product

@app.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED, tags=["Products"])
async def create_product_endpoint(
    product: ProductCreate,
    db: Session = Depends(get_db),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Создание товара (только для менеджеров и администраторов)"""
    require_manager_or_admin(roles)
    db_product = create_product(db, product)
    if not db_product:
        http_requests_total.labels(method='POST', endpoint='/products', status=400).inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create product"
        )
    http_requests_total.labels(method='POST', endpoint='/products', status=201).inc()
    return db_product

@app.put("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
async def update_product_endpoint(
    product_id: int,
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Обновление товара (только для менеджеров и администраторов)"""
    require_manager_or_admin(roles)
    db_product = update_product(db, product_id, product_update)
    if not db_product:
        http_requests_total.labels(method='PUT', endpoint=f'/products/{product_id}', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    http_requests_total.labels(method='PUT', endpoint=f'/products/{product_id}', status=200).inc()
    return db_product

@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Products"])
async def delete_product_endpoint(
    product_id: int,
    db: Session = Depends(get_db),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Удаление товара (только для менеджеров и администраторов)"""
    require_manager_or_admin(roles)
    db_product = delete_product(db, product_id)
    if not db_product:
        http_requests_total.labels(method='DELETE', endpoint=f'/products/{product_id}', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    http_requests_total.labels(method='DELETE', endpoint=f'/products/{product_id}', status=204).inc()
    return None

# ==================== DARKSTORES SECTION ====================

@app.get("/darkstores", response_model=List[DarkstoreResponse], tags=["Darkstores"])
async def list_darkstores(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Получение списка дарксторов (доступно всем)"""
    darkstores = get_darkstores(db, skip=skip, limit=limit)
    http_requests_total.labels(method='GET', endpoint='/darkstores', status=200).inc()
    return darkstores

@app.get("/darkstores/{darkstore_id}", response_model=DarkstoreResponse, tags=["Darkstores"])
async def get_darkstore_by_id(darkstore_id: int, db: Session = Depends(get_db)):
    """Получение информации о дарксторе (доступно всем)"""
    darkstore = get_darkstore(db, darkstore_id)
    if not darkstore:
        http_requests_total.labels(method='GET', endpoint=f'/darkstores/{darkstore_id}', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Darkstore not found"
        )
    http_requests_total.labels(method='GET', endpoint=f'/darkstores/{darkstore_id}', status=200).inc()
    return darkstore

@app.post("/darkstores", response_model=DarkstoreResponse, status_code=status.HTTP_201_CREATED, tags=["Darkstores"])
async def create_darkstore_endpoint(
    darkstore: DarkstoreCreate,
    db: Session = Depends(get_db),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Создание даркстора (только для менеджеров и администраторов)"""
    require_manager_or_admin(roles)
    db_darkstore = create_darkstore(db, darkstore)
    if not db_darkstore:
        http_requests_total.labels(method='POST', endpoint='/darkstores', status=400).inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create darkstore"
        )
    http_requests_total.labels(method='POST', endpoint='/darkstores', status=201).inc()
    return db_darkstore

@app.put("/darkstores/{darkstore_id}", response_model=DarkstoreResponse, tags=["Darkstores"])
async def update_darkstore_endpoint(
    darkstore_id: int,
    darkstore_update: DarkstoreUpdate,
    db: Session = Depends(get_db),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Обновление даркстора (только для менеджеров и администраторов)"""
    require_manager_or_admin(roles)
    db_darkstore = update_darkstore(db, darkstore_id, darkstore_update)
    if not db_darkstore:
        http_requests_total.labels(method='PUT', endpoint=f'/darkstores/{darkstore_id}', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Darkstore not found"
        )
    http_requests_total.labels(method='PUT', endpoint=f'/darkstores/{darkstore_id}', status=200).inc()
    return db_darkstore

@app.delete("/darkstores/{darkstore_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Darkstores"])
async def delete_darkstore_endpoint(
    darkstore_id: int,
    db: Session = Depends(get_db),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Удаление даркстора (только для менеджеров и администраторов)"""
    require_manager_or_admin(roles)
    db_darkstore = delete_darkstore(db, darkstore_id)
    if not db_darkstore:
        http_requests_total.labels(method='DELETE', endpoint=f'/darkstores/{darkstore_id}', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Darkstore not found"
        )
    http_requests_total.labels(method='DELETE', endpoint=f'/darkstores/{darkstore_id}', status=204).inc()
    return None

# ==================== INVENTORY SECTION ====================

@app.get("/inventory/darkstore/{darkstore_id}", response_model=List[InventoryWithDetails], tags=["Inventory"])
async def get_inventory_by_darkstore(
    darkstore_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Получение складских остатков по даркстору (доступно всем)"""
    inventories = get_inventories_by_darkstore(db, darkstore_id, skip=skip, limit=limit)
    if inventories is None:
        http_requests_total.labels(method='GET', endpoint=f'/inventory/darkstore/{darkstore_id}', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Darkstore not found"
        )
    http_requests_total.labels(method='GET', endpoint=f'/inventory/darkstore/{darkstore_id}', status=200).inc()
    return inventories

@app.get("/inventory/product/{product_id}", response_model=List[InventoryWithDetails], tags=["Inventory"])
async def get_inventory_by_product(
    product_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Получение складских остатков по товару (доступно всем)"""
    inventories = get_inventories_by_product(db, product_id, skip=skip, limit=limit)
    http_requests_total.labels(method='GET', endpoint=f'/inventory/product/{product_id}', status=200).inc()
    return inventories

@app.get("/inventory/{product_id}/{darkstore_id}", response_model=InventoryWithDetails, tags=["Inventory"])
async def get_inventory_item(
    product_id: int,
    darkstore_id: int,
    db: Session = Depends(get_db)
):
    """Получение информации о конкретном складском остатке (доступно всем)"""
    inventory = get_inventory_by_product_and_darkstore(db, product_id, darkstore_id)
    if not inventory:
        http_requests_total.labels(method='GET', endpoint=f'/inventory/{product_id}/{darkstore_id}', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory not found"
        )
    http_requests_total.labels(method='GET', endpoint=f'/inventory/{product_id}/{darkstore_id}', status=200).inc()
    return inventory

@app.post("/inventory", response_model=InventoryResponse, status_code=status.HTTP_201_CREATED, tags=["Inventory"])
async def create_inventory_endpoint(
    inventory: InventoryCreate,
    db: Session = Depends(get_db),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Создание складского остатка (только для менеджеров и администраторов)"""
    require_manager_or_admin(roles)
    db_inventory = create_inventory(db, inventory)
    if not db_inventory:
        http_requests_total.labels(method='POST', endpoint='/inventory', status=400).inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create inventory. Product or darkstore not found, or inventory already exists."
        )
    http_requests_total.labels(method='POST', endpoint='/inventory', status=201).inc()
    return db_inventory

@app.put("/inventory/{inventory_id}", response_model=InventoryResponse, tags=["Inventory"])
async def update_inventory_endpoint(
    inventory_id: int,
    inventory_update: InventoryUpdate,
    db: Session = Depends(get_db),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Обновление складского остатка (только для менеджеров и администраторов)"""
    require_manager_or_admin(roles)
    db_inventory = update_inventory(db, inventory_id, inventory_update)
    if not db_inventory:
        http_requests_total.labels(method='PUT', endpoint=f'/inventory/{inventory_id}', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory not found"
        )
    http_requests_total.labels(method='PUT', endpoint=f'/inventory/{inventory_id}', status=200).inc()
    return db_inventory

@app.put("/inventory/{product_id}/{darkstore_id}/quantity", response_model=InventoryResponse, tags=["Inventory"])
async def update_inventory_quantity_endpoint(
    product_id: int,
    darkstore_id: int,
    quantity: int,
    db: Session = Depends(get_db),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Обновление количества товара в дарксторе (только для менеджеров и администраторов)"""
    require_manager_or_admin(roles)
    db_inventory = update_inventory_quantity(db, product_id, darkstore_id, quantity)
    if not db_inventory:
        http_requests_total.labels(method='PUT', endpoint=f'/inventory/{product_id}/{darkstore_id}/quantity', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory not found"
        )
    http_requests_total.labels(method='PUT', endpoint=f'/inventory/{product_id}/{darkstore_id}/quantity', status=200).inc()
    return db_inventory

@app.delete("/inventory/{inventory_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Inventory"])
async def delete_inventory_endpoint(
    inventory_id: int,
    db: Session = Depends(get_db),
    roles: List[str] = Depends(get_current_user_roles)
):
    """Удаление складского остатка (только для менеджеров и администраторов)"""
    require_manager_or_admin(roles)
    db_inventory = delete_inventory(db, inventory_id)
    if not db_inventory:
        http_requests_total.labels(method='DELETE', endpoint=f'/inventory/{inventory_id}', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory not found"
        )
    http_requests_total.labels(method='DELETE', endpoint=f'/inventory/{inventory_id}', status=204).inc()
    return None

@app.get("/inventory/{product_id}/{darkstore_id}/check", tags=["Inventory"])
async def check_availability(
    product_id: int,
    darkstore_id: int,
    quantity: int,
    db: Session = Depends(get_db)
):
    """Проверка доступности товара в дарксторе (доступно всем)"""
    is_available = check_product_availability(db, product_id, darkstore_id, quantity)
    http_requests_total.labels(method='GET', endpoint=f'/inventory/{product_id}/{darkstore_id}/check', status=200).inc()
    return {"available": is_available, "product_id": product_id, "darkstore_id": darkstore_id, "required_quantity": quantity}

# ==================== INTERNAL ENDPOINTS ====================
# Внутренние эндпоинты для использования другими сервисами (без аутентификации)

@app.post("/internal/inventory/reserve", tags=["Internal"], include_in_schema=False)
async def reserve_inventory_internal(
    request: InventoryReserveRequest,
    db: Session = Depends(get_db)
):
    """
    Внутренний эндпоинт для резервирования товаров (уменьшение остатков)
    Используется order-service при оплате заказа
    """
    results = []
    for item in request.items:
        db_inventory = reserve_inventory_quantity(db, item.product_id, request.darkstore_id, item.quantity)
        if db_inventory:
            results.append({
                "product_id": item.product_id,
                "darkstore_id": request.darkstore_id,
                "quantity": item.quantity,
                "remaining_quantity": db_inventory.quantity,
                "success": True
            })
        else:
            results.append({
                "product_id": item.product_id,
                "success": False,
                "error": "Inventory not found or insufficient quantity"
            })
    
    http_requests_total.labels(method='POST', endpoint='/internal/inventory/reserve', status=200).inc()
    return {"results": results, "darkstore_id": request.darkstore_id}

@app.post("/internal/inventory/release", tags=["Internal"], include_in_schema=False)
async def release_inventory_internal(
    request: InventoryReleaseRequest,
    db: Session = Depends(get_db)
):
    """
    Внутренний эндпоинт для освобождения товаров (увеличение остатков)
    Используется order-service при отмене оплаченного заказа
    """
    results = []
    for item in request.items:
        db_inventory = release_inventory_quantity(db, item.product_id, request.darkstore_id, item.quantity)
        if db_inventory:
            results.append({
                "product_id": item.product_id,
                "darkstore_id": request.darkstore_id,
                "quantity": item.quantity,
                "new_quantity": db_inventory.quantity,
                "success": True
            })
        else:
            results.append({
                "product_id": item.product_id,
                "success": False,
                "error": "Inventory not found"
            })
    
    http_requests_total.labels(method='POST', endpoint='/internal/inventory/release', status=200).inc()
    return {"results": results, "darkstore_id": request.darkstore_id}

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
    uvicorn.run(app, host="0.0.0.0", port=8002)
