from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import timedelta
import time

from database import get_db, engine, Base
from models import User, Role
from schemas import (
    UserCreate, UserResponse, UserWithRoles, UserLogin, Token,
    RoleResponse, UserRolesUpdate
)
from crud import (
    create_user, get_user_by_id, get_user_by_phone_or_email,
    authenticate_user, get_user_roles, update_user_roles,
    get_all_roles, get_role_by_name, create_role, has_admin_users,
    get_all_users
)
from auth import create_access_token, decode_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

# Создание таблиц
Base.metadata.create_all(bind=engine)

app = FastAPI(title="User Management Service", version="1.0.0")

# Инициализация ролей при старте приложения
@app.on_event("startup")
async def init_roles():
    from database import SessionLocal
    db = SessionLocal()
    try:
        roles_to_create = [
            {"name": "admin", "description": "Администратор - может управлять ролями пользователей"},
            {"name": "manager", "description": "Менеджер - может управлять заказами и каталогом"},
            {"name": "courier", "description": "Курьер - работает в конкретном дакрсторе"},
            {"name": "client", "description": "Клиент - обычный пользователь"}
        ]
        
        for role_data in roles_to_create:
            existing_role = get_role_by_name(db, role_data["name"])
            if not existing_role:
                from schemas import RoleCreate
                role_create = RoleCreate(**role_data)
                create_role(db, role_create)
                print(f"Created role: {role_data['name']}")
    finally:
        db.close()

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
        
        # Нормализуем endpoint (убираем параметры из пути)
        normalized_endpoint = endpoint
        if "/users/" in endpoint and endpoint != "/users/register" and endpoint != "/users/login":
            # Для путей типа /users/{user_id} используем шаблон
            if endpoint.startswith("/users/") and endpoint.count("/") == 2:
                normalized_endpoint = "/users/{user_id}"
            elif endpoint.startswith("/users/") and "/roles" in endpoint:
                normalized_endpoint = "/users/{user_id}/roles"
            elif endpoint.startswith("/admin/users/") and "/roles" in endpoint:
                normalized_endpoint = "/admin/users/{user_id}/roles"
            elif endpoint.startswith("/users/") and "/roles/init-admin" in endpoint:
                normalized_endpoint = "/users/{user_id}/roles/init-admin"
        
        http_requests_total.labels(method=method, endpoint=normalized_endpoint, status=status_code).inc()
        http_request_duration_seconds.labels(method=method, endpoint=normalized_endpoint).observe(duration)
        
        return response
    except Exception as e:
        status_code = 500
        duration = time.time() - start_time
        normalized_endpoint = endpoint
        http_requests_total.labels(method=method, endpoint=normalized_endpoint, status=status_code).inc()
        http_request_duration_seconds.labels(method=method, endpoint=normalized_endpoint).observe(duration)
        raise

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: int = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = get_user_by_id(db, user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def require_admin(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Проверка, что текущий пользователь является администратором"""
    admin_role = get_role_by_name(db, "admin")
    if not admin_role or admin_role not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action"
        )
    return current_user

# ==================== USERS SECTION ====================
# Эндпоинты для обычных пользователей

@app.post("/users/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Users"])
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """Регистрация нового пользователя"""
    # Проверка уникальности телефона и email
    existing_user = get_user_by_phone_or_email(db, user.phone, user.email)
    if existing_user:
        if existing_user.phone == user.phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )
        if existing_user.email == user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    db_user = create_user(db, user)
    http_requests_total.labels(method='POST', endpoint='/users/register', status=201).inc()
    return db_user

@app.post("/users/login", response_model=Token, tags=["Users"])
async def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    """Авторизация пользователя"""
    user = authenticate_user(db, user_credentials.phone, user_credentials.password)
    if not user:
        http_requests_total.labels(method='POST', endpoint='/users/login', status=401).inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user.id}, expires_delta=access_token_expires
    )
    http_requests_total.labels(method='POST', endpoint='/users/login', status=200).inc()
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/{user_id}", response_model=UserResponse, tags=["Users"])
async def get_my_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Просмотр информации о себе (пользователь может видеть только свою информацию)"""
    # Проверка, что пользователь запрашивает свою информацию или является администратором
    admin_role = get_role_by_name(db, "admin")
    is_admin = admin_role and admin_role in current_user.roles
    
    if not is_admin and current_user.id != user_id:
        http_requests_total.labels(method='GET', endpoint=f'/users/{user_id}', status=403).inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own information"
        )
    
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        http_requests_total.labels(method='GET', endpoint=f'/users/{user_id}', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    http_requests_total.labels(method='GET', endpoint=f'/users/{user_id}', status=200).inc()
    return db_user

@app.get("/users/{user_id}/roles", response_model=List[RoleResponse], tags=["Users"])
async def get_my_roles(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Просмотр своих ролей (пользователь может видеть только свои роли)"""
    # Проверка, что пользователь запрашивает свои роли или является администратором
    admin_role = get_role_by_name(db, "admin")
    is_admin = admin_role and admin_role in current_user.roles
    
    if not is_admin and current_user.id != user_id:
        http_requests_total.labels(method='GET', endpoint=f'/users/{user_id}/roles', status=403).inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own roles"
        )
    
    roles = get_user_roles(db, user_id)
    if roles is None:
        http_requests_total.labels(method='GET', endpoint=f'/users/{user_id}/roles', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    http_requests_total.labels(method='GET', endpoint=f'/users/{user_id}/roles', status=200).inc()
    return roles

# ==================== ADMIN SECTION ====================
# Эндпоинты только для администраторов

@app.get("/users", response_model=List[UserResponse], tags=["Admin"])
async def get_all_users_endpoint(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Просмотр всех пользователей (только для администраторов)"""
    users = get_all_users(db)
    http_requests_total.labels(method='GET', endpoint='/users', status=200).inc()
    return users

@app.get("/admin/roles", response_model=List[RoleResponse], tags=["Admin"])
async def get_all_roles_admin(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Просмотр списка всех ролей (только для администраторов)"""
    roles = get_all_roles(db)
    http_requests_total.labels(method='GET', endpoint='/admin/roles', status=200).inc()
    return roles

@app.put("/admin/users/{user_id}/roles", response_model=UserWithRoles, tags=["Admin"])
async def update_user_roles_endpoint(
    user_id: int,
    roles_update: UserRolesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Назначение ролей пользователю (только для администраторов)"""
    # Проверка существования всех ролей
    all_roles = get_all_roles(db)
    role_ids_set = set(roles_update.role_ids)
    existing_role_ids = {role.id for role in all_roles}
    
    if not role_ids_set.issubset(existing_role_ids):
        http_requests_total.labels(method='PUT', endpoint=f'/admin/users/{user_id}/roles', status=400).inc()
        missing_roles = role_ids_set - existing_role_ids
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Roles with IDs {missing_roles} do not exist"
        )
    
    user = update_user_roles(db, user_id, roles_update.role_ids)
    if user is None:
        http_requests_total.labels(method='PUT', endpoint=f'/admin/users/{user_id}/roles', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    http_requests_total.labels(method='PUT', endpoint=f'/admin/users/{user_id}/roles', status=200).inc()
    return user

# ==================== INTERNAL/INIT ENDPOINTS ====================
# Скрытые эндпоинты для инициализации (не отображаются в основной документации)

@app.post("/users/{user_id}/roles/init-admin", response_model=UserWithRoles, tags=["Internal"], include_in_schema=False)
async def init_first_admin(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Инициализация первого администратора системы.
    Работает только если в системе еще нет администраторов.
    Скрыт из основной документации.
    """
    # Проверка, есть ли уже администраторы
    if has_admin_users(db):
        http_requests_total.labels(method='POST', endpoint=f'/users/{user_id}/roles/init-admin', status=403).inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrators already exist. Use PUT /admin/users/{user_id}/roles with admin privileges."
        )
    
    # Проверка существования пользователя
    user = get_user_by_id(db, user_id)
    if user is None:
        http_requests_total.labels(method='POST', endpoint=f'/users/{user_id}/roles/init-admin', status=404).inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Получение роли администратора
    admin_role = get_role_by_name(db, "admin")
    if not admin_role:
        http_requests_total.labels(method='POST', endpoint=f'/users/{user_id}/roles/init-admin', status=500).inc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin role not found. Please restart the service."
        )
    
    # Назначение роли администратора
    user = update_user_roles(db, user_id, [admin_role.id])
    http_requests_total.labels(method='POST', endpoint=f'/users/{user_id}/roles/init-admin', status=200).inc()
    return user

# ==================== DEFAULT ENDPOINTS ====================

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
    uvicorn.run(app, host="0.0.0.0", port=8001)
