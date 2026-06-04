from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from schemas.review import ReviewCreate, ReviewUpdate, AdminReplyRequest
from schemas.complaint import DeleteReviewRequest
from db import database as db
from core.utils import utcnow

router = APIRouter()


def _mask_name(first: str | None, last: str | None) -> str:
    full = f"{first or ''} {last or ''}".strip()
    if not full:
        return "Anonymous"
    return f"{full[0]}{'*' * (len(full) - 2)}{full[-1]}" if len(full) > 1 else full[0]


def _serialize(r: dict, mask: bool = False) -> dict:
    result = dict(r)
    for k, v in result.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
    if mask and result.get("is_anonymous"):
        result["user_first_name"] = _mask_name(
            result.get("user_first_name"), result.get("user_last_name")
        )
        result["user_last_name"] = ""
    return result


@router.post("/reviews")
async def create_review(body: ReviewCreate):
    if body.rating < 1 or body.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    existing = await db.fetch_one(
        'SELECT id FROM "Review" WHERE "userId" = $1 AND "productId" = $2',
        body.userId, body.productId,
    )
    if existing:
        raise HTTPException(status_code=400, detail="You have already reviewed this product")

    now = utcnow()
    row = await db.fetch_one(
        '''INSERT INTO "Review" ("userId", "productId", "orderId", rating, title, body, is_anonymous, created_at, updated_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$8) RETURNING *''',
        body.userId, body.productId, body.orderId, body.rating,
        body.title, body.body, body.is_anonymous, now,
    )
    return {"message": "Review submitted", "review": _serialize(row)}


@router.get("/products/{product_id}/reviews")
async def get_product_reviews(product_id: int):
    rows = await db.fetch_all(
        '''SELECT r.*, u.first_name as user_first_name, u.last_name as user_last_name
           FROM "Review" r
           LEFT JOIN "User" u ON u.id = r."userId"
           WHERE r."productId" = $1
           ORDER BY r.id DESC''',
        product_id,
    )
    return [_serialize(r, mask=True) for r in rows]


@router.get("/user/{user_id}/reviews")
async def get_user_reviews(user_id: int):
    rows = await db.fetch_all(
        'SELECT * FROM "Review" WHERE "userId" = $1 ORDER BY id DESC', user_id
    )
    return [_serialize(r) for r in rows]


@router.put("/reviews/{review_id}")
async def update_review(review_id: int, body: ReviewUpdate):
    review = await db.fetch_one('SELECT * FROM "Review" WHERE id = $1', review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review["userId"] != body.userId:
        raise HTTPException(status_code=403, detail="Not authorized to edit this review")

    if body.rating is not None and (body.rating < 1 or body.rating > 5):
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    now = utcnow()
    row = await db.fetch_one(
        '''UPDATE "Review" SET
           rating = COALESCE($2, rating),
           title = COALESCE($3, title),
           body = COALESCE($4, body),
           is_anonymous = COALESCE($5, is_anonymous),
           updated_at = $6
           WHERE id = $1 RETURNING *''',
        review_id, body.rating, body.title, body.body, body.is_anonymous, now,
    )
    return {"message": "Review updated", "review": _serialize(row)}


@router.delete("/reviews/{review_id}")
async def delete_review(review_id: int, body: DeleteReviewRequest):
    review = await db.fetch_one('SELECT * FROM "Review" WHERE id = $1', review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review["userId"] != body.userId:
        raise HTTPException(status_code=403, detail="Not authorized to delete this review")

    await db.execute('DELETE FROM "Review" WHERE id = $1', review_id)
    return {"message": "Review deleted"}


@router.get("/admin/reviews")
async def admin_list_reviews(
    productId: int | None = Query(None),
    rating: int | None = Query(None),
):
    conditions = []
    params = []
    idx = 1

    if productId is not None:
        conditions.append(f'r."productId" = ${idx}')
        params.append(productId)
        idx += 1
    if rating is not None:
        conditions.append(f"r.rating = ${idx}")
        params.append(rating)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await db.fetch_all(
        f'''SELECT r.*, u.first_name as user_first_name, u.last_name as user_last_name,
            p.name as product_name
            FROM "Review" r
            LEFT JOIN "User" u ON u.id = r."userId"
            LEFT JOIN "Product" p ON p.id = r."productId"
            {where}
            ORDER BY r.id DESC''',
        *params,
    )
    return [_serialize(r) for r in rows]


@router.put("/admin/reviews/{review_id}/reply")
async def admin_reply_review(review_id: int, body: AdminReplyRequest):
    review = await db.fetch_one('SELECT * FROM "Review" WHERE id = $1', review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    now = utcnow()
    row = await db.fetch_one(
        'UPDATE "Review" SET admin_reply = $2, updated_at = $3 WHERE id = $1 RETURNING *',
        review_id, body.admin_reply, now,
    )
    return {"message": "Reply added", "review": _serialize(row)}


@router.get("/admin/analytics/reviews")
async def reviews_analytics():
    total = await db.fetch_val('SELECT COUNT(*) FROM "Review"')
    dist_rows = await db.fetch_all(
        'SELECT rating, COUNT(*) as count FROM "Review" GROUP BY rating ORDER BY rating'
    )
    rating_distribution = {str(r["rating"]): r["count"] for r in dist_rows}
    avg = await db.fetch_val('SELECT ROUND(AVG(rating)::numeric, 2) FROM "Review"')
    product_stats = await db.fetch_all(
        '''SELECT r."productId", p.name as product_name,
           ROUND(AVG(r.rating)::numeric, 2) as avg_rating, COUNT(*) as count
           FROM "Review" r JOIN "Product" p ON p.id = r."productId"
           GROUP BY r."productId", p.name ORDER BY avg_rating DESC'''
    )
    return {
        "totalReviews": total,
        "ratingDistribution": rating_distribution,
        "averageRating": float(avg) if avg else 0,
        "productStats": [
            {
                "productId": r["productId"],
                "productName": r["product_name"],
                "avgRating": float(r["avg_rating"]),
                "count": r["count"],
            }
            for r in product_stats
        ],
    }
