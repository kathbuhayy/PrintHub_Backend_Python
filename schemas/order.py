from __future__ import annotations
from typing import Optional, List, Any
from pydantic import BaseModel


class OrderItemInput(BaseModel):
    productId: int
    quantity: int
    unitPrice: float
    customizations: Optional[Any] = None
    imageUrl: Optional[str] = None


class OrderCreate(BaseModel):
    userId: Optional[int] = None
    items: List[OrderItemInput]
    shipping_address: Optional[str] = None
    billing_address: Optional[str] = None
    shippingCost: Optional[float] = 0


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    proofApproved: Optional[bool] = None
    due_date: Optional[str] = None
    shipping_address: Optional[str] = None
    billing_address: Optional[str] = None
