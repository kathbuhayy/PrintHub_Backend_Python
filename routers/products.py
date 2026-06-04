import time
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from schemas.product import ProductCreate, ProductUpdate, AddStockRequest
from db import database as db
from core.utils import utcnow
from db.supabase import upload_file

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 3 * 1024 * 1024  # 3 MB


def _serialize_product(p: dict) -> dict:
    result = dict(p)
    for k, v in result.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
    if result.get("price") is not None:
        result["price"] = float(result["price"])
    return result


@router.get("/products")
async def list_products(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100)):
    offset = (page - 1) * limit
    total = await db.fetch_val(
        'SELECT COUNT(*) FROM "Product" WHERE active = true AND deleted_at IS NULL'
    )
    rows = await db.fetch_all(
        'SELECT * FROM "Product" WHERE active = true AND deleted_at IS NULL ORDER BY id DESC LIMIT $1 OFFSET $2',
        limit, offset,
    )
    return {
        "products": [_serialize_product(r) for r in rows],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if total else 0,
        },
    }


@router.get("/admin/low-stock")
async def low_stock(
    threshold: int = Query(10),
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
):
    offset = (page - 1) * limit
    rows = await db.fetch_all(
        'SELECT * FROM "Product" WHERE stock <= $1 AND deleted_at IS NULL ORDER BY stock ASC LIMIT $2 OFFSET $3',
        threshold, limit, offset,
    )
    return [_serialize_product(r) for r in rows]


@router.get("/products/{product_id}")
async def get_product(product_id: int):
    product = await db.fetch_one(
        'SELECT * FROM "Product" WHERE id = $1 AND deleted_at IS NULL', product_id
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _serialize_product(product)


@router.post("/products")
async def create_product(body: ProductCreate):
    now = utcnow()
    row = await db.fetch_one(
        '''INSERT INTO "Product" (
            name, sku, description, price, currency, stock,
            width_mm, height_mm, depth_mm, material,
            color_options, size_options, material_options, side_options,
            finishing_options, processing_options, delivery_options,
            quantity_options, shipping_options,
            print_type, turnaround_hours, ai_prompt_rules, print_zones,
            category, images, quantity_mode, quantity_count, active,
            created_at, updated_at
        ) VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
            $11,$12,$13,$14,$15,$16,$17,$18,$19,
            $20,$21,$22,$23,$24,$25,$26,$27,$28,
            $29,$29
        ) RETURNING *''',
        body.name, body.sku, body.description, body.price, body.currency, body.stock,
        body.width_mm, body.height_mm, body.depth_mm, body.material,
        body.color_options, body.size_options, body.material_options, body.side_options,
        body.finishing_options, body.processing_options, body.delivery_options,
        body.quantity_options, body.shipping_options,
        body.print_type, body.turnaround_hours, body.ai_prompt_rules, body.print_zones,
        body.category, body.images, body.quantity_mode, body.quantity_count, body.active,
        now,
    )
    return {"message": "Product created", "product": _serialize_product(row)}


@router.put("/products/{product_id}")
async def update_product(product_id: int, body: ProductUpdate):
    existing = await db.fetch_one(
        'SELECT * FROM "Product" WHERE id = $1 AND deleted_at IS NULL', product_id
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")

    fields = body.model_dump(exclude_none=True)
    if not fields:
        return {"message": "No changes", "product": _serialize_product(existing)}

    now = utcnow()
    fields["updated_at"] = now

    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(fields))
    values = list(fields.values())
    row = await db.fetch_one(
        f'UPDATE "Product" SET {set_clause} WHERE id = $1 RETURNING *',
        product_id, *values,
    )
    return {"message": "Product updated", "product": _serialize_product(row)}


@router.post("/products/{product_id}/add-stock")
async def add_stock(product_id: int, body: AddStockRequest):
    existing = await db.fetch_one(
        'SELECT * FROM "Product" WHERE id = $1 AND deleted_at IS NULL', product_id
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")

    now = utcnow()
    if body.quantity_options is not None:
        row = await db.fetch_one(
            'UPDATE "Product" SET stock = stock + $2, quantity_options = $3, updated_at = $4 WHERE id = $1 RETURNING *',
            product_id, body.add, body.quantity_options, now,
        )
    else:
        row = await db.fetch_one(
            'UPDATE "Product" SET stock = stock + $2, updated_at = $3 WHERE id = $1 RETURNING *',
            product_id, body.add, now,
        )

    return {"message": "Stock updated", "product": _serialize_product(row)}


@router.delete("/products/{product_id}")
async def delete_product(product_id: int):
    existing = await db.fetch_one(
        'SELECT * FROM "Product" WHERE id = $1 AND deleted_at IS NULL', product_id
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")

    now = utcnow()
    row = await db.fetch_one(
        'UPDATE "Product" SET deleted_at = $1, updated_at = $1 WHERE id = $2 RETURNING *',
        now, product_id,
    )
    return {"message": "Product deleted", "product": _serialize_product(row)}


@router.post("/products/upload")
async def upload_product_image(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: JPEG, PNG, WebP, GIF")

    data = await file.read()
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 3MB")

    ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "jpg"
    path = f"products/{int(time.time())}.{ext}"
    url = await upload_file(path, data, file.content_type)

    return {"url": url, "path": path, "size": len(data), "mimeType": file.content_type}
