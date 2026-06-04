from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel


class ProductCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    description: Optional[str] = None
    price: float
    currency: str = "PHP"
    stock: int = 0
    width_mm: Optional[int] = None
    height_mm: Optional[int] = None
    depth_mm: Optional[int] = None
    material: Optional[str] = None
    color_options: List[str] = []
    size_options: List[str] = []
    material_options: List[str] = []
    side_options: List[str] = []
    finishing_options: List[str] = []
    processing_options: List[str] = []
    delivery_options: List[str] = []
    quantity_options: List[str] = []
    shipping_options: List[str] = []
    print_type: Optional[str] = None
    turnaround_hours: Optional[int] = None
    ai_prompt_rules: Optional[str] = None
    print_zones: List[str] = []
    category: Optional[str] = "other"
    images: List[str] = []
    quantity_mode: Optional[str] = None
    quantity_count: Optional[int] = None
    active: bool = True


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    stock: Optional[int] = None
    width_mm: Optional[int] = None
    height_mm: Optional[int] = None
    depth_mm: Optional[int] = None
    material: Optional[str] = None
    color_options: Optional[List[str]] = None
    size_options: Optional[List[str]] = None
    material_options: Optional[List[str]] = None
    side_options: Optional[List[str]] = None
    finishing_options: Optional[List[str]] = None
    processing_options: Optional[List[str]] = None
    delivery_options: Optional[List[str]] = None
    quantity_options: Optional[List[str]] = None
    shipping_options: Optional[List[str]] = None
    print_type: Optional[str] = None
    turnaround_hours: Optional[int] = None
    ai_prompt_rules: Optional[str] = None
    print_zones: Optional[List[str]] = None
    category: Optional[str] = None
    images: Optional[List[str]] = None
    quantity_mode: Optional[str] = None
    quantity_count: Optional[int] = None
    active: Optional[bool] = None


class AddStockRequest(BaseModel):
    add: int
    quantity_options: Optional[List[str]] = None
