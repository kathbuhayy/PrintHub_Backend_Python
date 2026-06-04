from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class ComplaintCreate(BaseModel):
    userId: Optional[int] = None
    name: str
    order_number: Optional[str] = None
    orderId: Optional[int] = None
    description: str
    image_url: Optional[str] = None


class ComplaintUpdate(BaseModel):
    status: Optional[str] = None
    admin_notes: Optional[str] = None
    admin_reply: Optional[str] = None


class DeleteReviewRequest(BaseModel):
    userId: int
