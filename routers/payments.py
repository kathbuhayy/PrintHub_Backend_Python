from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from db import database as db
from services.paymongo import create_checkout, get_session_status, verify_webhook_signature
from core.config import settings
from datetime import datetime, timezone

router = APIRouter()


class CheckoutRequest(BaseModel):
    orderId: int
    returnBase: Optional[str] = None


def _serialize_order(o: dict) -> dict:
    result = dict(o)
    for k, v in result.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
    if result.get("total") is not None:
        result["total"] = float(result["total"])
    return result


@router.post("/payments/checkout")
async def checkout(body: CheckoutRequest):
    order = await db.fetch_one(
        "SELECT * FROM orders WHERE id = $1 AND deleted_at IS NULL", body.orderId
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    items = await db.fetch_all(
        """SELECT oi.quantity, oi.unit_price, p.name as product_name, p.images as product_images
           FROM order_items oi
           JOIN products p ON p.id = oi.product_id
           WHERE oi.order_id = $1""",
        body.orderId,
    )

    items_payload = []
    for item in items:
        images = item.get("product_images") or []
        items_payload.append({
            "product_name": item["product_name"],
            "quantity": item["quantity"],
            "unit_price": float(item["unit_price"]),
            "image_url": images[0] if images else None,
        })

    result = await create_checkout(dict(order), items_payload, body.returnBase)

    now = datetime.now(timezone.utc)
    await db.execute(
        "UPDATE orders SET paymongo_session_id = $1, checkout_url = $2, payment_status = 'awaiting_payment', updated_at = $3 WHERE id = $4",
        result["session_id"], result["checkout_url"], now, body.orderId,
    )

    return {"checkout_url": result["checkout_url"], "session_id": result["session_id"]}


@router.get("/payments/{order_id}/status")
async def payment_status(order_id: int):
    order = await db.fetch_one(
        "SELECT * FROM orders WHERE id = $1 AND deleted_at IS NULL", order_id
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order["payment_status"] == "paid":
        return {"payment_status": "paid", "order": _serialize_order(order)}

    if order.get("paymongo_session_id"):
        try:
            remote_status = await get_session_status(order["paymongo_session_id"])
            if remote_status == "paid":
                now = datetime.now(timezone.utc)
                await db.execute(
                    "UPDATE orders SET payment_status = 'paid', status = 'confirmed', updated_at = $1 WHERE id = $2",
                    now, order_id,
                )
                updated = await db.fetch_one("SELECT * FROM orders WHERE id = $1", order_id)
                return {"payment_status": "paid", "order": _serialize_order(updated)}
            return {"payment_status": remote_status, "order": _serialize_order(order)}
        except Exception:
            pass

    return {"payment_status": order["payment_status"], "order": _serialize_order(order)}


@router.post("/payments/webhook")
async def payment_webhook(request: Request):
    raw_body = await request.body()
    sig_header = request.headers.get("Paymongo-Signature", "")

    if not verify_webhook_signature(raw_body, sig_header, settings.PAYMONGO_WEBHOOK_SECRET):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    import json
    try:
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = payload.get("data", {}).get("attributes", {}).get("type", "")

    if event_type in ("checkout_session.payment.paid", "payment.paid"):
        attrs = payload["data"]["attributes"]
        session_id = attrs.get("data", {}).get("id") or attrs.get("id")
        ref = attrs.get("data", {}).get("attributes", {}).get("reference_number") or attrs.get("reference_number", "")

        order = None
        if ref:
            try:
                order = await db.fetch_one("SELECT * FROM orders WHERE id = $1", int(ref))
            except Exception:
                pass
        if not order and session_id:
            order = await db.fetch_one("SELECT * FROM orders WHERE paymongo_session_id = $1", session_id)

        if order and order["payment_status"] != "paid":
            now = datetime.now(timezone.utc)
            await db.execute(
                "UPDATE orders SET payment_status = 'paid', status = 'confirmed', updated_at = $1 WHERE id = $2",
                now, order["id"],
            )

    return {"received": True}
