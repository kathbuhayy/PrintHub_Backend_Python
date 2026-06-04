from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from schemas.user import (
    UpdateProfileRequest, ChangePasswordRequest,
    AdminCreateUserRequest, AdminUpdateUserRequest,
)
from db import database as db
from core import otp_store, security

router = APIRouter()


def _serialize_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "first_name": u.get("first_name"),
        "last_name": u.get("last_name"),
        "email": u["email"],
        "phone": u.get("phone"),
        "address": u.get("address"),
        "gender": u.get("gender"),
        "avatar_url": u.get("avatar_url"),
        "birthday": u["birthday"].isoformat() if u.get("birthday") else None,
        "role": u.get("role"),
        "status": u.get("status"),
        "last_login": u["last_login"].isoformat() if u.get("last_login") else None,
        "join_date": u["join_date"].isoformat() if u.get("join_date") else None,
        "created_at": u["created_at"].isoformat() if u.get("created_at") else None,
    }


@router.get("/user-profile/{user_id}")
async def get_user_profile(user_id: int):
    user = await db.fetch_one("SELECT * FROM users WHERE id = $1", user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _serialize_user(user)


@router.put("/user-profile/{user_id}")
async def update_user_profile(user_id: int, body: UpdateProfileRequest):
    user = await db.fetch_one("SELECT * FROM users WHERE id = $1", user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.phone and not security.validate_phone(body.phone):
        raise HTTPException(status_code=400, detail="Phone must be in format +639XXXXXXXXX")

    if body.email and not security.validate_email(body.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    if body.birthday:
        try:
            bday = datetime.fromisoformat(body.birthday)
            if bday.year > 2011:
                raise HTTPException(status_code=400, detail="Must be born in 2011 or earlier")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid birthday format")

    first_name = user["first_name"]
    last_name = user["last_name"]
    if body.name:
        parts = body.name.strip().split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

    now = datetime.now(timezone.utc)
    await db.execute(
        """UPDATE users SET first_name=$1, last_name=$2, email=COALESCE($3, email),
           phone=COALESCE($4, phone), address=COALESCE($5, address),
           gender=COALESCE($6, gender), avatar_url=COALESCE($7, avatar_url),
           birthday=COALESCE($8::timestamptz, birthday), updated_at=$9
           WHERE id=$10""",
        first_name, last_name,
        body.email, body.phone, body.address,
        body.gender, body.avatar_url,
        datetime.fromisoformat(body.birthday) if body.birthday else None,
        now, user_id,
    )
    return {"message": "Profile updated successfully"}


@router.put("/profile/{user_id}/password")
async def change_password(user_id: int, body: ChangePasswordRequest):
    user = await db.fetch_one("SELECT * FROM users WHERE id = $1", user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not security.verify_password(body.currentPassword, user["password"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if not security.validate_password_strength(body.newPassword):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8-12 characters with uppercase, number, and special character",
        )

    now = datetime.now(timezone.utc)
    await db.execute(
        "UPDATE users SET password=$1, updated_at=$2 WHERE id=$3",
        security.hash_password(body.newPassword), now, user_id,
    )
    return {"message": "Password updated successfully"}


# ─── Admin ────────────────────────────────────────────────────────────────────

@router.get("/admin/users")
async def admin_list_users():
    rows = await db.fetch_all(
        "SELECT id, first_name, last_name, email, role, status, last_login, join_date FROM users ORDER BY id DESC"
    )
    return [
        {
            "id": r["id"],
            "name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "email": r["email"],
            "role": r["role"],
            "status": r["status"],
            "lastLogin": r["last_login"].isoformat() if r.get("last_login") else None,
            "joinDate": r["join_date"].isoformat() if r.get("join_date") else None,
        }
        for r in rows
    ]


@router.post("/admin/users")
async def admin_create_user(body: AdminCreateUserRequest):
    existing = await db.fetch_one("SELECT id FROM users WHERE email = $1", body.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    parts = body.name.strip().split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""
    now = datetime.now(timezone.utc)

    await db.execute(
        """INSERT INTO users (first_name, last_name, email, password, role, status, join_date, created_at, updated_at)
           VALUES ($1,$2,$3,$4,$5,'active',$6,$6,$6)""",
        first_name, last_name, body.email,
        security.hash_password(body.password), body.role, now,
    )
    return {"message": "User created successfully"}


@router.put("/admin/users/{user_id}")
async def admin_update_user(user_id: int, body: AdminUpdateUserRequest):
    user = await db.fetch_one("SELECT * FROM users WHERE id = $1", user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    first_name = user["first_name"]
    last_name = user["last_name"]
    if body.name:
        parts = body.name.strip().split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

    now = datetime.now(timezone.utc)
    await db.execute(
        """UPDATE users SET first_name=$1, last_name=$2,
           email=COALESCE($3, email), role=COALESCE($4, role),
           status=COALESCE($5, status), updated_at=$6 WHERE id=$7""",
        first_name, last_name, body.email, body.role, body.status, now, user_id,
    )
    return {"message": "User updated successfully"}


@router.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: int):
    user = await db.fetch_one("SELECT * FROM users WHERE id = $1", user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc)
    pool = db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO archived_users (user_id, first_name, last_name, email, password, phone, address, role, status, last_login, join_date, gender, birthday, position, archived_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
                user["id"], user["first_name"], user["last_name"], user["email"],
                user["password"], user["phone"], user["address"], user["role"],
                user["status"], user.get("last_login"), user.get("join_date"),
                user.get("gender"), user.get("birthday"), user.get("position"), now,
            )
            await conn.execute("DELETE FROM users WHERE id = $1", user_id)

    return {"message": "User archived successfully"}
