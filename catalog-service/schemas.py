from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

# Product schemas
class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)
    price: Decimal = Field(..., gt=0)
    description: Optional[str] = None
    
    @field_validator('price')
    @classmethod
    def validate_price_decimal_places(cls, v: Decimal) -> Decimal:
        """Validate that price has at most 2 decimal places"""
        if v is not None:
            # Use as_tuple() to get the exponent (number of decimal places)
            sign, digits, exponent = v.as_tuple()
            # exponent is negative for decimal places (e.g., -2 means 2 decimal places)
            if exponent < -2:
                raise ValueError('Price must have at most 2 decimal places')
        return v

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    price: Optional[Decimal] = Field(None, gt=0)
    description: Optional[str] = None
    
    @field_validator('price')
    @classmethod
    def validate_price_decimal_places(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate that price has at most 2 decimal places"""
        if v is not None:
            # Use as_tuple() to get the exponent (number of decimal places)
            sign, digits, exponent = v.as_tuple()
            # exponent is negative for decimal places (e.g., -2 means 2 decimal places)
            if exponent < -2:
                raise ValueError('Price must have at most 2 decimal places')
        return v

class ProductResponse(ProductBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Darkstore schemas
class DarkstoreBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: Optional[str] = None

class DarkstoreCreate(DarkstoreBase):
    pass

class DarkstoreUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = None

class DarkstoreResponse(DarkstoreBase):
    id: int
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Inventory schemas
class InventoryBase(BaseModel):
    product_id: int
    darkstore_id: int
    quantity: int = Field(..., ge=0)

class InventoryCreate(InventoryBase):
    pass

class InventoryUpdate(BaseModel):
    quantity: int = Field(..., ge=0)

class InventoryResponse(InventoryBase):
    id: int
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Extended schemas with relationships
class InventoryWithDetails(InventoryResponse):
    product: ProductResponse
    darkstore: DarkstoreResponse
    
    class Config:
        from_attributes = True

class ProductWithInventory(ProductResponse):
    inventories: List[InventoryResponse] = []
    
    class Config:
        from_attributes = True

class DarkstoreWithInventory(DarkstoreResponse):
    inventories: List[InventoryResponse] = []
    
    class Config:
        from_attributes = True

# Internal schemas for inventory operations
class InventoryReserveItem(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)

class InventoryReserveRequest(BaseModel):
    items: List[InventoryReserveItem]
    darkstore_id: int

class InventoryReleaseItem(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)

class InventoryReleaseRequest(BaseModel):
    items: List[InventoryReleaseItem]
    darkstore_id: int
