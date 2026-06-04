from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class InquiryCreate(BaseModel):
    userId: Optional[int] = None
    product_title: Optional[str] = None
    subject: str
    name: str
    email: str
    quantity: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    material: Optional[str] = None
    finishing: Optional[str] = None
    printing: Optional[str] = None
    processing: Optional[str] = None
    delivery: Optional[str] = None
    other: Optional[str] = None


class InquiryUpdate(BaseModel):
    status: Optional[str] = None
    quoted_price: Optional[float] = None
    admin_notes: Optional[str] = None
