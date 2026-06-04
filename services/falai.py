import time
import httpx
from core.config import settings
from db.supabase import upload_file

_last_gen: dict[str, float] = {}
COOLDOWN = 30  # seconds

SIZE_MAP = {
    "square_hd": "1024x1024",
    "square": "512x512",
    "portrait_4_3": "768x1024",
    "portrait_16_9": "576x1024",
    "landscape_4_3": "1024x768",
    "landscape_16_9": "1024x576",
}


def _check_rate_limit(key: str) -> None:
    last = _last_gen.get(key, 0)
    elapsed = time.time() - last
    if elapsed < COOLDOWN:
        remaining = int(COOLDOWN - elapsed)
        raise ValueError(f"Rate limit: wait {remaining} seconds before generating again")


def _set_last_gen(key: str) -> None:
    _last_gen[key] = time.time()


async def generate_image(prompt: str, image_size: str, user_key: str) -> dict:
    _check_rate_limit(user_key)
    _set_last_gen(user_key)

    if settings.fal_mock:
        return await _generate_pollinations(prompt, image_size, user_key)
    return await _generate_falai(prompt, image_size, user_key)


async def _generate_pollinations(prompt: str, image_size: str, user_key: str) -> dict:
    dims = SIZE_MAP.get(image_size, "1024x1024").split("x")
    width, height = int(dims[0]), int(dims[1])

    import urllib.parse
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true"

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        image_data = resp.content
        mime = "image/jpeg"

    path = f"uploads/ai/{int(time.time())}.jpg"
    stored_url = await upload_file(path, image_data, mime)

    return {
        "imageUrl": stored_url,
        "width": width,
        "height": height,
        "prompt": prompt,
        "stored": True,
        "path": path,
    }


async def _generate_falai(prompt: str, image_size: str, user_key: str) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://fal.run/fal-ai/flux/dev",
            headers={"Authorization": f"Key {settings.FAL_KEY}"},
            json={"prompt": prompt, "image_size": image_size, "num_images": 1},
        )
        resp.raise_for_status()
        data = resp.json()

    image_url = data["images"][0]["url"]
    width = data["images"][0].get("width", 1024)
    height = data["images"][0].get("height", 1024)

    async with httpx.AsyncClient(timeout=60) as client:
        img_resp = await client.get(image_url)
        img_resp.raise_for_status()
        image_data = img_resp.content

    path = f"uploads/ai/{int(time.time())}.jpg"
    stored_url = await upload_file(path, image_data, "image/jpeg")

    return {
        "imageUrl": stored_url,
        "width": width,
        "height": height,
        "prompt": prompt,
        "stored": True,
        "path": path,
    }
