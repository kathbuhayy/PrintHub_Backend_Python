import time
from fastapi import APIRouter, HTTPException, UploadFile, File, Header, Request
from pydantic import BaseModel
from typing import Optional
from db.supabase import upload_file
from services.falai import generate_image
from services.meshy import text_to_3d, image_to_3d

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024   # 10 MB for AI uploads
MAX_AVATAR_SIZE = 2 * 1024 * 1024    # 2 MB


def _get_user_key(user_id: str | None, request: Request) -> str:
    if user_id:
        return f"user_{user_id}"
    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.client.host
    return f"ip_{ip}"


@router.post("/builder/upload")
async def builder_upload(
    request: Request,
    file: UploadFile = File(...),
    description: Optional[str] = None,
    x_user_id: Optional[str] = Header(None),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")

    data = await file.read()
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB")

    ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "bin"
    path = f"uploads/{x_user_id}/{int(time.time())}.{ext}"
    url = await upload_file(path, data, file.content_type or "application/octet-stream")

    return {"url": url, "path": path, "size": len(data), "mimeType": file.content_type}


class GenerateImageRequest(BaseModel):
    prompt: str
    imageSize: str = "square_hd"


@router.post("/builder/generate-image")
async def builder_generate_image(
    body: GenerateImageRequest,
    request: Request,
    x_user_id: Optional[str] = Header(None),
):
    if len(body.prompt) > 2000:
        raise HTTPException(status_code=400, detail="Prompt too long (max 2000 characters)")

    user_key = _get_user_key(x_user_id, request)
    try:
        result = await generate_image(body.prompt, body.imageSize, user_key)
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))

    return result


class Generate3DRequest(BaseModel):
    prompt: str
    quality: str = "standard"
    productId: Optional[int] = None


@router.post("/builder/generate")
async def builder_generate_3d(
    body: Generate3DRequest,
    request: Request,
    x_user_id: Optional[str] = Header(None),
):
    try:
        result = await text_to_3d(body.prompt, body.quality)
    except (ValueError, TimeoutError) as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result


class GenerateFromImageRequest(BaseModel):
    imageUrl: str
    description: Optional[str] = ""
    quality: str = "standard"


@router.post("/builder/generate-from-image")
async def builder_generate_from_image(
    body: GenerateFromImageRequest,
    request: Request,
    x_user_id: Optional[str] = Header(None),
):
    try:
        result = await image_to_3d(body.imageUrl, body.description or "", body.quality)
    except (ValueError, TimeoutError) as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result


class Generate3DSimpleRequest(BaseModel):
    prompt: str
    designImageUrl: Optional[str] = None


@router.post("/builder/generate-3d")
async def builder_generate_3d_simple(body: Generate3DSimpleRequest):
    return {
        "message": "3D object generated with texture",
        "type": "textured-cube",
        "textureUrl": body.designImageUrl,
        "prompt": body.prompt,
    }


@router.post("/user/avatar-upload")
async def avatar_upload(
    request: Request,
    file: UploadFile = File(...),
    x_user_id: Optional[str] = Header(None),
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")

    data = await file.read()
    if len(data) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 2MB")

    ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "jpg"
    path = f"avatars/{x_user_id}/{int(time.time())}.{ext}"
    url = await upload_file(path, data, file.content_type or "image/jpeg")

    return {"url": url, "path": path, "size": len(data), "mimeType": file.content_type}
