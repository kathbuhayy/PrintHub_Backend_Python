from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from schemas.inquiry import InquiryCreate, InquiryUpdate
from db import database as db

router = APIRouter()


def _serialize(i: dict) -> dict:
    result = dict(i)
    for k, v in result.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
    if result.get("quoted_price") is not None:
        result["quoted_price"] = float(result["quoted_price"])
    return result


@router.post("/inquiries")
async def create_inquiry(body: InquiryCreate):
    now = datetime.now(timezone.utc)
    row = await db.fetch_one(
        """INSERT INTO inquiries (user_id, product_title, subject, name, email, quantity,
           size, color, material, finishing, printing, processing, delivery, other, status, created_at, updated_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,'new',$15,$15) RETURNING *""",
        body.userId, body.product_title, body.subject, body.name, body.email,
        body.quantity, body.size, body.color, body.material, body.finishing,
        body.printing, body.processing, body.delivery, body.other, now,
    )
    return {"message": "Inquiry submitted", "inquiry": _serialize(row)}


@router.get("/inquiries")
async def list_inquiries(status: str | None = Query(None)):
    if status:
        rows = await db.fetch_all(
            "SELECT * FROM inquiries WHERE status = $1 ORDER BY id DESC", status
        )
    else:
        rows = await db.fetch_all("SELECT * FROM inquiries ORDER BY id DESC")
    return [_serialize(r) for r in rows]


@router.get("/inquiries/{inquiry_id}")
async def get_inquiry(inquiry_id: int):
    row = await db.fetch_one("SELECT * FROM inquiries WHERE id = $1", inquiry_id)
    if not row:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    return _serialize(row)


@router.put("/inquiries/{inquiry_id}")
async def update_inquiry(inquiry_id: int, body: InquiryUpdate):
    inquiry = await db.fetch_one("SELECT * FROM inquiries WHERE id = $1", inquiry_id)
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")

    now = datetime.now(timezone.utc)
    pool = db.get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Auto-create order when quoted_price is first set on a "new" inquiry
            order_id = inquiry.get("order_id")
            new_quoted = body.quoted_price
            if (
                new_quoted is not None
                and inquiry.get("quoted_price") is None
                and inquiry["status"] == "new"
            ):
                # Find or create placeholder product
                placeholder = await conn.fetchrow(
                    "SELECT id FROM products WHERE name = 'Custom Inquiry Order' AND deleted_at IS NULL"
                )
                if not placeholder:
                    placeholder = await conn.fetchrow(
                        """INSERT INTO products (name, price, stock, active, created_at, updated_at)
                           VALUES ('Custom Inquiry Order', $1, 999, true, $2, $2) RETURNING id""",
                        new_quoted, now,
                    )
                product_id = placeholder["id"]

                order = await conn.fetchrow(
                    """INSERT INTO orders (user_id, total, currency, status, created_at, updated_at)
                       VALUES ($1,$2,'PHP','converted',$3,$3) RETURNING *""",
                    inquiry.get("user_id"), new_quoted, now,
                )
                await conn.execute(
                    """INSERT INTO order_items (order_id, product_id, quantity, unit_price, total_price, created_at)
                       VALUES ($1,$2,1,$3,$3,$4)""",
                    order["id"], product_id, new_quoted, now,
                )
                order_id = order["id"]

            updated = await conn.fetchrow(
                """UPDATE inquiries SET
                   status = COALESCE($2, status),
                   quoted_price = COALESCE($3, quoted_price),
                   admin_notes = COALESCE($4, admin_notes),
                   order_id = COALESCE($5, order_id),
                   updated_at = $6
                   WHERE id = $1 RETURNING *""",
                inquiry_id, body.status, body.quoted_price, body.admin_notes, order_id, now,
            )

    return {"message": "Inquiry updated", "inquiry": _serialize(dict(updated))}


@router.get("/user/{user_id}/inquiries")
async def get_user_inquiries(user_id: int):
    rows = await db.fetch_all(
        "SELECT * FROM inquiries WHERE user_id = $1 ORDER BY id DESC", user_id
    )
    return [_serialize(r) for r in rows]


@router.put("/inquiries/{inquiry_id}/convert")
async def convert_inquiry(inquiry_id: int):
    inquiry = await db.fetch_one("SELECT * FROM inquiries WHERE id = $1", inquiry_id)
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    if not inquiry.get("quoted_price"):
        raise HTTPException(status_code=400, detail="Inquiry must have a quoted price before converting")

    if inquiry.get("order_id"):
        return {
            "message": "Already converted",
            "orderId": inquiry["order_id"],
            "order": await db.fetch_one("SELECT * FROM orders WHERE id = $1", inquiry["order_id"]),
        }

    now = datetime.now(timezone.utc)
    pool = db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            placeholder = await conn.fetchrow(
                "SELECT id FROM products WHERE name = 'Custom Inquiry Order' AND deleted_at IS NULL"
            )
            if not placeholder:
                placeholder = await conn.fetchrow(
                    """INSERT INTO products (name, price, stock, active, created_at, updated_at)
                       VALUES ('Custom Inquiry Order', $1, 999, true, $2, $2) RETURNING id""",
                    float(inquiry["quoted_price"]), now,
                )
            order = await conn.fetchrow(
                """INSERT INTO orders (user_id, total, currency, status, created_at, updated_at)
                   VALUES ($1,$2,'PHP','converted',$3,$3) RETURNING *""",
                inquiry.get("user_id"), float(inquiry["quoted_price"]), now,
            )
            await conn.execute(
                """INSERT INTO order_items (order_id, product_id, quantity, unit_price, total_price, created_at)
                   VALUES ($1,$2,1,$3,$3,$4)""",
                order["id"], placeholder["id"], float(inquiry["quoted_price"]), now,
            )
            await conn.execute(
                "UPDATE inquiries SET order_id = $1, status = 'converted', updated_at = $2 WHERE id = $3",
                order["id"], now, inquiry_id,
            )

    return {
        "message": "Inquiry converted to order",
        "orderId": order["id"],
        "order": _serialize(dict(order)),
    }
