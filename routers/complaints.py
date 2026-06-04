import time
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from schemas.complaint import ComplaintCreate, ComplaintUpdate
from db import database as db
from core.utils import utcnow
from db.supabase import upload_file

router = APIRouter()

MAX_COMPLAINT_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


def _serialize(c: dict) -> dict:
    result = dict(c)
    for k, v in result.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
    return result


@router.post("/complaints/upload-image")
async def upload_complaint_image(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_COMPLAINT_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 5MB")

    ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "jpg"
    path = f"complaints/{int(time.time())}.{ext}"
    url = await upload_file(path, data, file.content_type or "image/jpeg")
    return {"url": url, "path": path, "size": len(data), "mimeType": file.content_type}


@router.post("/complaints")
async def create_complaint(body: ComplaintCreate):
    now = utcnow()
    row = await db.fetch_one(
        '''INSERT INTO "Complaint" ("userId", name, order_number, "orderId", description, image_url, status, created_at, updated_at)
           VALUES ($1,$2,$3,$4,$5,$6,'open',$7,$7) RETURNING *''',
        body.userId, body.name, body.order_number, body.orderId,
        body.description, body.image_url, now,
    )
    return {"message": "Complaint submitted", "complaint": _serialize(row)}


@router.get("/user/{user_id}/complaints")
async def get_user_complaints(user_id: int):
    rows = await db.fetch_all(
        'SELECT * FROM "Complaint" WHERE "userId" = $1 ORDER BY id DESC', user_id
    )
    return [_serialize(r) for r in rows]


@router.get("/admin/complaints")
async def admin_list_complaints(status: str | None = Query(None)):
    if status:
        rows = await db.fetch_all(
            '''SELECT c.*, u.first_name as user_first_name, u.last_name as user_last_name
               FROM "Complaint" c LEFT JOIN "User" u ON u.id = c."userId"
               WHERE c.status = $1 ORDER BY c.id DESC''',
            status,
        )
    else:
        rows = await db.fetch_all(
            '''SELECT c.*, u.first_name as user_first_name, u.last_name as user_last_name
               FROM "Complaint" c LEFT JOIN "User" u ON u.id = c."userId"
               ORDER BY c.id DESC'''
        )
    return [_serialize(r) for r in rows]


@router.get("/admin/complaints/{complaint_id}")
async def admin_get_complaint(complaint_id: int):
    row = await db.fetch_one(
        '''SELECT c.*, u.first_name as user_first_name, u.last_name as user_last_name
           FROM "Complaint" c LEFT JOIN "User" u ON u.id = c."userId"
           WHERE c.id = $1''',
        complaint_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return _serialize(row)


@router.put("/admin/complaints/{complaint_id}")
async def admin_update_complaint(complaint_id: int, body: ComplaintUpdate):
    complaint = await db.fetch_one('SELECT * FROM "Complaint" WHERE id = $1', complaint_id)
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    now = utcnow()
    row = await db.fetch_one(
        '''UPDATE "Complaint" SET
           status = COALESCE($2, status),
           admin_notes = COALESCE($3, admin_notes),
           admin_reply = COALESCE($4, admin_reply),
           updated_at = $5
           WHERE id = $1 RETURNING *''',
        complaint_id, body.status, body.admin_notes, body.admin_reply, now,
    )
    return {"message": "Complaint updated", "complaint": _serialize(row)}


@router.get("/admin/analytics/complaints")
async def complaints_analytics():
    total = await db.fetch_val('SELECT COUNT(*) FROM "Complaint"')
    status_rows = await db.fetch_all(
        'SELECT status, COUNT(*) as count FROM "Complaint" GROUP BY status'
    )
    by_status = {r["status"]: r["count"] for r in status_rows}

    monthly_rows = await db.fetch_all(
        '''SELECT TO_CHAR(created_at, \'YYYY-MM\') as month, COUNT(*) as count
           FROM "Complaint" GROUP BY month ORDER BY month DESC LIMIT 12'''
    )
    monthly_trend = {r["month"]: r["count"] for r in monthly_rows}

    return {
        "totalComplaints": total,
        "byStatus": {
            "open": by_status.get("open", 0),
            "in_review": by_status.get("in_review", 0),
            "resolved": by_status.get("resolved", 0),
            "closed": by_status.get("closed", 0),
        },
        "monthlyTrend": monthly_trend,
    }
