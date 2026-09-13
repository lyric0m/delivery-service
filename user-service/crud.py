from sqlalchemy.orm import Session
from sqlalchemy import or_
from models import User, Role
from schemas import UserCreate, RoleCreate
from auth import get_password_hash, verify_password

def get_user_by_id(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_phone(db: Session, phone: str):
    return db.query(User).filter(User.phone == phone).first()

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def get_user_by_phone_or_email(db: Session, phone: str, email: str):
    return db.query(User).filter(
        or_(User.phone == phone, User.email == email)
    ).first()

def create_user(db: Session, user: UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = User(
        phone=user.phone,
        email=user.email,
        password_hash=hashed_password,
        full_name=user.full_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, phone: str, password: str):
    user = get_user_by_phone(db, phone)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

def get_user_roles(db: Session, user_id: int):
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    return user.roles

def update_user_roles(db: Session, user_id: int, role_ids: list[int]):
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    
    roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
    user.roles = roles
    db.commit()
    db.refresh(user)
    return user

def get_role_by_id(db: Session, role_id: int):
    return db.query(Role).filter(Role.id == role_id).first()

def get_role_by_name(db: Session, name: str):
    return db.query(Role).filter(Role.name == name).first()

def create_role(db: Session, role: RoleCreate):
    db_role = Role(name=role.name, description=role.description)
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role

def get_all_roles(db: Session):
    return db.query(Role).all()

def has_admin_users(db: Session):
    """Проверка наличия пользователей с ролью администратора"""
    admin_role = get_role_by_name(db, "admin")
    if not admin_role:
        return False
    return len(admin_role.users) > 0

def get_all_users(db: Session):
    """Получение списка всех пользователей"""
    return db.query(User).all()
