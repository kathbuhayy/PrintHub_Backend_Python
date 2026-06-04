from supabase import create_client, Client
from core.config import settings

_client: Client | None = None

BUCKET = "printhub_s3"


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _client


async def upload_file(path: str, data: bytes, mime_type: str, bucket: str = BUCKET) -> str:
    client = get_client()
    try:
        client.storage.from_(bucket).upload(
            path=path,
            file=data,
            file_options={"content-type": mime_type, "upsert": "true"},
        )
    except Exception:
        # bucket may not exist; create it and retry
        try:
            client.storage.create_bucket(bucket, options={"public": True})
        except Exception:
            pass
        client.storage.from_(bucket).upload(
            path=path,
            file=data,
            file_options={"content-type": mime_type, "upsert": "true"},
        )

    public_url = client.storage.from_(bucket).get_public_url(path)
    return public_url
