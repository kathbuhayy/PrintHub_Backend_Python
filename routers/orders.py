import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from schemas.order import OrderCreate, OrderUpdate
from db import database as db
from core.utils import utcnow

router = APIRouter()


def _serialize_order(o: dict) -> dict:
    result = dict(o)
    for k, v in result.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
    for key in ("total", "unit_price", "total_price"):
        if result.get(key) is not None:
            result[key] = float(result[key])
    return result


@router.post("/orders")
async def create_order(body: OrderCreate):
    if not body.items:
        raise HTTPException(status_code=400, detail="Order must have at least one item")

    pool = db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            subtotal = 0.0
            item_rows = []
            for item in body.items:
                product = await conn.fetchrow(
                    'SELECT * FROM "Product" WHERE id = $1 AND deleted_at IS NULL FOR UPDATE',
                    item.productId,
                )
                if not product:
                    raise HTTPException(status_code=404, detail=f"Product {item.productId} not found")
                if product["stock"] < item.quantity:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient stock for {product['name']}",
                    )
                item_total = float(item.unitPrice) * item.quantity
                subtotal += item_total
                item_rows.append((item, product, item_total))
                await conn.execute(
                    'UPDATE "Product" SET stock = stock - $1 WHERE id = $2',
                    item.quantity, item.productId,
                )

            total = subtotal + float(body.shippingCost or 0)
            now = utcnow()
            order = await conn.fetchrow(
                '''INSERT INTO "Order" ("userId", total, currency, status, shipping_address, billing_address,
                   "proofApproved", payment_status, created_at, updated_at)
                   VALUES ($1,$2,'PHP','pending',$3,$4,false,'unpaid',$5,$5) RETURNING *''',
                body.userId, total, body.shipping_address, body.billing_address, now,
            )

            for item, product, item_total in item_rows:
                customizations = json.dumps(item.customizations) if item.customizations else None
                await conn.execute(
                    '''INSERT INTO "OrderItem" ("orderId", "productId", quantity, unit_price, total_price, customizations, "createdAt")
                       VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7)''',
                    order["id"], item.productId, item.quantity,
                    item.unitPrice, item_total,
                    customizations, now,
                )

    full_order = await db.fetch_one('SELECT * FROM "Order" WHERE id = $1', order["id"])
    items = await db.fetch_all('SELECT * FROM "OrderItem" WHERE "orderId" = $1', order["id"])
    result = _serialize_order(full_order)
    result["items"] = [_serialize_order(i) for i in items]
    return {"message": "Order created", "order": result}


@router.get("/orders/{order_id}")
async def get_order(order_id: int):
    order = await db.fetch_one(
        'SELECT * FROM "Order" WHERE id = $1 AND deleted_at IS NULL', order_id
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    items = await db.fetch_all(
        '''SELECT oi.*, p.name as product_name, p.images as product_images
           FROM "OrderItem" oi
           JOIN "Product" p ON p.id = oi."productId"
           WHERE oi."orderId" = $1''',
        order_id,
    )
    user = None
    if order.get("userId"):
        user = await db.fetch_one(
            'SELECT id, first_name, last_name, email FROM "User" WHERE id = $1',
            order["userId"],
        )

    result = _serialize_order(order)
    result["items"] = [_serialize_order(i) for i in items]
    result["user"] = dict(user) if user else None
    return result


@router.get("/user/{user_id}/orders")
async def get_user_orders(user_id: int):
    rows = await db.fetch_all(
        'SELECT * FROM "Order" WHERE "userId" = $1 AND deleted_at IS NULL ORDER BY id DESC',
        user_id,
    )
    result = []
    for order in rows:
        items = await db.fetch_all('SELECT * FROM "OrderItem" WHERE "orderId" = $1', order["id"])
        o = _serialize_order(order)
        o["items"] = [_serialize_order(i) for i in items]
        result.append(o)
    return result


@router.get("/admin/orders")
async def admin_list_orders():
    rows = await db.fetch_all(
        'SELECT * FROM "Order" WHERE deleted_at IS NULL ORDER BY id DESC'
    )
    result = []
    for order in rows:
        items = await db.fetch_all(
            '''SELECT oi.*, p.name as product_name FROM "OrderItem" oi
               JOIN "Product" p ON p.id = oi."productId" WHERE oi."orderId" = $1''',
            order["id"],
        )
        user = None
        if order.get("userId"):
            user = await db.fetch_one(
                'SELECT id, first_name, last_name, email FROM "User" WHERE id = $1',
                order["userId"],
            )
        o = _serialize_order(order)
        o["items"] = [_serialize_order(i) for i in items]
        o["user"] = dict(user) if user else None
        result.append(o)
    return result


@router.put("/orders/{order_id}")
async def update_order(order_id: int, body: OrderUpdate):
    existing = await db.fetch_one(
        'SELECT * FROM "Order" WHERE id = $1 AND deleted_at IS NULL', order_id
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Order not found")

    now = utcnow()
    due_date = None
    if body.due_date:
        try:
            due_date = datetime.fromisoformat(body.due_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid due_date format")

    row = await db.fetch_one(
        '''UPDATE "Order" SET
           status = COALESCE($2, status),
           "proofApproved" = COALESCE($3, "proofApproved"),
           due_date = COALESCE($4, due_date),
           shipping_address = COALESCE($5, shipping_address),
           billing_address = COALESCE($6, billing_address),
           updated_at = $7
           WHERE id = $1 RETURNING *''',
        order_id, body.status, body.proofApproved, due_date,
        body.shipping_address, body.billing_address, now,
    )
    return {"message": "Order updated", "order": _serialize_order(row)}


@router.patch("/orders/{order_id}/deliver")
async def deliver_order(order_id: int):
    existing = await db.fetch_one(
        'SELECT * FROM "Order" WHERE id = $1 AND deleted_at IS NULL', order_id
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Order not found")

    now = utcnow()
    row = await db.fetch_one(
        'UPDATE "Order" SET status = \'delivered\', delivered_at = $2, updated_at = $2 WHERE id = $1 RETURNING *',
        order_id, now,
    )
    return {"message": "Order marked as delivered", "order": _serialize_order(row)}


@router.delete("/orders/{order_id}")
async def delete_order(order_id: int):
    existing = await db.fetch_one(
        'SELECT * FROM "Order" WHERE id = $1 AND deleted_at IS NULL', order_id
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Order not found")

    items = await db.fetch_all('SELECT * FROM "OrderItem" WHERE "orderId" = $1', order_id)
    now = utcnow()

    pool = db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            for item in items:
                await conn.execute(
                    'UPDATE "Product" SET stock = stock + $1 WHERE id = $2',
                    item["quantity"], item["productId"],
                )
            await conn.execute(
                'UPDATE "Order" SET deleted_at = $1, updated_at = $1 WHERE id = $2',
                now, order_id,
            )

    row = await db.fetch_one('SELECT * FROM "Order" WHERE id = $1', order_id)
    return {"message": "Order deleted", "order": _serialize_order(row)}


@router.delete("/orders/{order_id}/items/{item_id}")
async def delete_order_item(order_id: int, item_id: int):
    order = await db.fetch_one(
        'SELECT * FROM "Order" WHERE id = $1 AND deleted_at IS NULL', order_id
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    item = await db.fetch_one(
        'SELECT * FROM "OrderItem" WHERE id = $1 AND "orderId" = $2', item_id, order_id
    )
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found")

    now = utcnow()
    pool = db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                'UPDATE "Product" SET stock = stock + $1 WHERE id = $2',
                item["quantity"], item["productId"],
            )
            await conn.execute('DELETE FROM "OrderItem" WHERE id = $1', item_id)
            new_total = await conn.fetchval(
                'SELECT COALESCE(SUM(total_price), 0) FROM "OrderItem" WHERE "orderId" = $1',
                order_id,
            )
            await conn.execute(
                'UPDATE "Order" SET total = $1, updated_at = $2 WHERE id = $3',
                new_total, now, order_id,
            )

    updated_order = await db.fetch_one('SELECT * FROM "Order" WHERE id = $1', order_id)
    remaining_items = await db.fetch_all('SELECT * FROM "OrderItem" WHERE "orderId" = $1', order_id)
    result = _serialize_order(updated_order)
    result["items"] = [_serialize_order(i) for i in remaining_items]
    return {"message": "Item removed", "order": result}
