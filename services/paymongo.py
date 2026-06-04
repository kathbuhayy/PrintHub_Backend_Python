import base64
import hashlib
import hmac
import httpx
from core.config import settings

BASE_URL = "https://api.paymongo.com/v1"


def _auth_header() -> str:
    token = base64.b64encode(f"{settings.PAYMONGO_SECRET_KEY}:".encode()).decode()
    return f"Basic {token}"


async def create_checkout(order: dict, items: list[dict], return_base: str | None = None) -> dict:
    frontend = return_base or settings.FRONTEND_URL
    line_items = []
    for item in items:
        li = {
            "currency": "PHP",
            "amount": int(float(item["unit_price"]) * 100),
            "name": item.get("product_name", "Product"),
            "quantity": item["quantity"],
        }
        if item.get("image_url"):
            li["images"] = [item["image_url"]]
        line_items.append(li)

    payload = {
        "data": {
            "attributes": {
                "line_items": line_items,
                "payment_method_types": ["card", "gcash", "paymaya"],
                "success_url": f"{frontend}/order-success?orderId={order['id']}",
                "cancel_url": f"{frontend}/checkout?orderId={order['id']}",
                "description": f"Order #{order['id']}",
                "reference_number": str(order["id"]),
            }
        }
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE_URL}/checkout_sessions",
            headers={"Authorization": _auth_header(), "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()["data"]

    return {
        "checkout_url": data["attributes"]["checkout_url"],
        "session_id": data["id"],
    }


async def get_session_status(session_id: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/checkout_sessions/{session_id}",
            headers={"Authorization": _auth_header()},
        )
        resp.raise_for_status()
        attrs = resp.json()["data"]["attributes"]

    payments = attrs.get("payments", [])
    for p in payments:
        if p.get("attributes", {}).get("status") == "paid":
            return "paid"

    status = attrs.get("status", "")
    if status == "active":
        return "awaiting_payment"
    return "unpaid"


def verify_webhook_signature(raw_body: bytes, sig_header: str, secret: str) -> bool:
    try:
        parts = {}
        for part in sig_header.split(","):
            k, v = part.split("=", 1)
            parts[k.strip()] = v.strip()
        timestamp = parts.get("t", "")
        given_sig = parts.get("te", "") or parts.get("li", "")
        message = f"{timestamp}.{raw_body.decode()}"
        expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, given_sig)
    except Exception:
        return False
