from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class ReviewCreate(BaseModel):
    userId: int
    productId: int
    orderId: Optional[int] = None
    rating: int
    title: Optional[str] = None
    body: Optional[str] = None
    is_anonymous: bool = False


class ReviewUpdate(BaseModel):
    userId: int
    rating: Optional[int] = None
    title: Optional[str] = None
    body: Optional[str] = None
    is_anonymous: Optional[bool] = None


class AdminReplyRequest(BaseModel):
    admin_reply: str
