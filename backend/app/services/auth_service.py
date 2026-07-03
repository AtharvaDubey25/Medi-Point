import bcrypt
import re
from datetime import datetime, timedelta
from jose import jwt

from app.config import settings


def validate_password_strength(password: str) -> str | None:
    if len(password) < 8:
        return "Minimum 8 characters"
    if not re.search(r"[A-Z]", password):
        return "Must contain at least 1 uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Must contain at least 1 lowercase letter"
    if not re.search(r"\d", password):
        return "Must contain at least 1 digit"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;'/`~]", password):
        return "Must contain at least 1 special character"
    return None


def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = plain_password.encode('utf-8')
        # Handle cases where the stored hash might be string/bytes
        hashed_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

