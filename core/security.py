import re
import random
import string
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

PHONE_RE = re.compile(r"^\+639\d{9}$")
EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
PASSWORD_RE = re.compile(r"^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,12}$")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def validate_phone(phone: str) -> bool:
    return bool(PHONE_RE.match(phone))


def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))


def validate_password_strength(password: str) -> bool:
    return bool(PASSWORD_RE.match(password))
