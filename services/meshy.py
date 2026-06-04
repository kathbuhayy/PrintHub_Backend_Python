import asyncio
import time
import httpx
from core.config import settings
from db.supabase import upload_file

POLL_INTERVAL = 3
MAX_WAIT = 600  # 10 minutes
BASE_URL = "https://api.meshy.ai"


async def _poll_task(task_id: str) -> dict:
    deadline = time.time() + MAX_WAIT
    async with httpx.AsyncClient(timeout=30) as client:
        while time.time() < deadline:
            resp = await client.get(
                f"{BASE_URL}/v2/text-to-3d/{task_id}",
                headers={"Authorization": f"Bearer {settings.MESHY_API_KEY}"},
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            if status == "SUCCEEDED":
                return data
            if status in ("FAILED", "EXPIRED"):
                raise ValueError(f"Meshy task {task_id} failed: {status}")
            await asyncio.sleep(POLL_INTERVAL)
    raise TimeoutError("Meshy 3D generation timed out after 10 minutes")


async def _poll_image_task(task_id: str) -> dict:
    deadline = time.time() + MAX_WAIT
    async with httpx.AsyncClient(timeout=30) as client:
        while time.time() < deadline:
            resp = await client.get(
                f"{BASE_URL}/v1/image-to-3d/{task_id}",
                headers={"Authorization": f"Bearer {settings.MESHY_API_KEY}"},
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            if status == "SUCCEEDED":
                return data
            if status in ("FAILED", "EXPIRED"):
                raise ValueError(f"Meshy image-to-3D task {task_id} failed: {status}")
            await asyncio.sleep(POLL_INTERVAL)
    raise TimeoutError("Meshy image-to-3D timed out after 10 minutes")


async def text_to_3d(prompt: str, quality: str = "standard") -> dict:
    mode_map = {"draft": "preview", "standard": "refine", "preview": "refine"}
    mode = mode_map.get(quality, "refine")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE_URL}/v2/text-to-3d",
            headers={"Authorization": f"Bearer {settings.MESHY_API_KEY}"},
            json={"mode": mode, "prompt": prompt, "art_style": "realistic"},
        )
        resp.raise_for_status()
        task_id = resp.json()["result"]

    result = await _poll_task(task_id)
    glb_url = result.get("model_urls", {}).get("glb", "")

    stored_url = glb_url
    path = None
    if glb_url:
        async with httpx.AsyncClient(timeout=60) as client:
            glb_resp = await client.get(glb_url)
            glb_resp.raise_for_status()
            glb_data = glb_resp.content
        path = f"uploads/3d/{int(time.time())}.glb"
        stored_url = await upload_file(path, glb_data, "model/gltf-binary")

    return {
        "glbUrl": stored_url,
        "meshyUrl": glb_url,
        "meshyTaskId": task_id,
        "stored": bool(path),
        "path": path,
    }


async def image_to_3d(image_url: str, description: str = "", quality: str = "standard") -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE_URL}/v1/image-to-3d",
            headers={"Authorization": f"Bearer {settings.MESHY_API_KEY}"},
            json={
                "image_url": image_url,
                "enable_pbr": True,
                **({"description": description} if description else {}),
            },
        )
        resp.raise_for_status()
        task_id = resp.json()["result"]

    result = await _poll_image_task(task_id)
    glb_url = result.get("model_urls", {}).get("glb", "")

    stored_url = glb_url
    path = None
    if glb_url:
        async with httpx.AsyncClient(timeout=60) as client:
            glb_resp = await client.get(glb_url)
            glb_resp.raise_for_status()
            glb_data = glb_resp.content
        path = f"uploads/3d/{int(time.time())}.glb"
        stored_url = await upload_file(path, glb_data, "model/gltf-binary")

    return {
        "glbUrl": stored_url,
        "meshyUrl": glb_url,
        "meshyTaskId": task_id,
        "stored": bool(path),
        "path": path,
    }
