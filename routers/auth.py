from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from schemas.user import (
    LoginRequest, SendOtpRequest, VerifyOtpRequest,
    RegisterCompleteRequest, ResetPasswordRequest,
)
from db import database as db
from core import otp_store, security
from services.email import send_otp_email

router = APIRouter()


@router.post("/login")
async def login(body: LoginRequest):
    user = await db.fetch_one(
        "SELECT * FROM users WHERE email = $1", body.email
    )
    if not user:
        archived = await db.fetch_one(
            "SELECT * FROM archived_users WHERE email = $1", body.email
        )
        if archived:
            otp = security.generate_otp()
            otp_store.set_otp(body.email, otp)
            await send_otp_email(body.email, otp)
            raise HTTPException(
                status_code=403,
                detail={"message": "Account is archived", "needsReactivation": True},
            )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not security.verify_password(body.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    await db.execute(
        "UPDATE users SET last_login = $1 WHERE id = $2",
        datetime.now(timezone.utc),
        user["id"],
    )

    return {
        "message": "Login successful",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "firstName": user["first_name"],
            "role": user["role"],
        },
    }


@router.post("/register/send-otp")
async def register_send_otp(body: SendOtpRequest):
    existing = await db.fetch_one("SELECT id FROM users WHERE email = $1", body.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    otp = security.generate_otp()
    otp_store.set_otp(body.email, otp)
    await send_otp_email(body.email, otp)
    return {"message": "OTP sent to your email"}


@router.post("/register/verify-otp")
async def register_verify_otp(body: VerifyOtpRequest):
    if not otp_store.verify_otp(body.email, body.otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    otp_store.set_verified(body.email)
    return {"message": "OTP verified successfully"}


@router.post("/register/complete")
async def register_complete(body: RegisterCompleteRequest):
    if not otp_store.check_verified(body.email):
        raise HTTPException(status_code=400, detail="Email not verified or verification expired")

    if not security.validate_phone(body.phone):
        raise HTTPException(status_code=400, detail="Phone must be in format +639XXXXXXXXX")

    if not security.validate_password_strength(body.password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8-12 characters with uppercase, number, and special character",
        )

    existing = await db.fetch_one("SELECT id FROM users WHERE email = $1", body.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = security.hash_password(body.password)
    now = datetime.now(timezone.utc)
    await db.fetch_one(
        """INSERT INTO users (first_name, last_name, email, phone, address, password, role, status, join_date, created_at, updated_at)
           VALUES ($1,$2,$3,$4,$5,$6,2,'active',$7,$7,$7) RETURNING id""",
        body.firstName, body.lastName, body.email, body.phone, body.address, hashed, now,
    )
    otp_store.clear(body.email)
    return {"message": "Registration successful"}


@router.post("/password/request-otp")
@router.post("/password/send-otp")
async def password_send_otp(body: SendOtpRequest):
    user = await db.fetch_one("SELECT id FROM users WHERE email = $1", body.email)
    if not user:
        raise HTTPException(status_code=404, detail="Email not found")
    otp = security.generate_otp()
    otp_store.set_otp(body.email, otp)
    await send_otp_email(body.email, otp)
    return {"message": "OTP sent to your email"}


@router.post("/password/verify-otp")
async def password_verify_otp(body: VerifyOtpRequest):
    if not otp_store.verify_otp(body.email, body.otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    otp_store.set_verified(body.email)
    return {"message": "OTP verified"}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    if not otp_store.check_verified(body.email):
        raise HTTPException(status_code=400, detail="OTP verification required")

    if not security.validate_password_strength(body.newPassword):
        raise HTTPException(
            status_code=400,
            detail="Password must be 8-12 characters with uppercase, number, and special character",
        )

    now = datetime.now(timezone.utc)
    result = await db.execute(
        "UPDATE users SET password = $1, updated_at = $2 WHERE email = $3",
        security.hash_password(body.newPassword), now, body.email,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="User not found")

    otp_store.clear(body.email)
    return {"message": "Password reset successful"}


@router.post("/reactivate/verify-otp")
async def reactivate_verify_otp(body: VerifyOtpRequest):
    if not otp_store.verify_otp(body.email, body.otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    archived = await db.fetch_one(
        "SELECT * FROM archived_users WHERE email = $1", body.email
    )
    if not archived:
        raise HTTPException(status_code=404, detail="Archived user not found")

    now = datetime.now(timezone.utc)
    pool = db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO users (first_name, last_name, email, password, phone, address, role, status, join_date, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,'active',$8,$8,$8)""",
                archived["first_name"], archived["last_name"], archived["email"],
                archived["password"], archived["phone"], archived["address"],
                archived.get("role", 2), now,
            )
            await conn.execute("DELETE FROM archived_users WHERE email = $1", body.email)

    return {"message": "Account reactivated successfully"}
