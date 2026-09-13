from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, CheckConstraint, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    price = Column(Numeric(10, 2), nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связь с остатками
    inventories = relationship("Inventory", back_populates="product", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint('price >= 0', name='check_price_positive'),
    )

class Darkstore(Base):
    __tablename__ = "darkstores"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    address = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связь с остатками
    inventories = relationship("Inventory", back_populates="darkstore", cascade="all, delete-orphan")

class Inventory(Base):
    __tablename__ = "inventories"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    darkstore_id = Column(Integer, ForeignKey("darkstores.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    product = relationship("Product", back_populates="inventories")
    darkstore = relationship("Darkstore", back_populates="inventories")
    
    __table_args__ = (
        CheckConstraint('quantity >= 0', name='check_quantity_non_negative'),
        {'sqlite_autoincrement': True}
    )
