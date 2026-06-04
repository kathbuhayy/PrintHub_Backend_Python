import time
from threading import Lock

_store: dict[str, dict] = {}
_lock = Lock()

OTP_TTL = 300        # 5 minutes
VERIFIED_TTL = 600   # 10 minutes


def set_otp(email: str, code: str, ttl: int = OTP_TTL) -> None:
    with _lock:
        _store[email] = {"otp": code, "expires_at": time.time() + ttl}


def verify_otp(email: str, code: str) -> bool:
    with _lock:
        entry = _store.get(email)
        if not entry:
            return False
        if time.time() > entry["expires_at"]:
            del _store[email]
            return False
        if entry["otp"] != code:
            return False
        del _store[email]
        return True


def set_verified(email: str, ttl: int = VERIFIED_TTL) -> None:
    with _lock:
        _store[email + "_verified"] = {"expires_at": time.time() + ttl}


def check_verified(email: str) -> bool:
    with _lock:
        entry = _store.get(email + "_verified")
        if not entry:
            return False
        if time.time() > entry["expires_at"]:
            del _store[email + "_verified"]
            return False
        return True


def clear(email: str) -> None:
    with _lock:
        _store.pop(email, None)
        _store.pop(email + "_verified", None)
