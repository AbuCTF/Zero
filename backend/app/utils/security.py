"""security utilities: password hashing (ctfd-compatible), encryption, token generation."""

import hashlib
import hmac
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta
from typing import Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from werkzeug.security import check_password_hash, generate_password_hash

from app.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    """pbkdf2:sha256, ctfd-compatible."""
    return generate_password_hash(
        password,
        method=settings.password_hash_method,
        salt_length=16,
    )


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def get_fernet() -> Fernet:
    if not settings.encryption_key:
        raise ValueError("ENCRYPTION_KEY not configured")
    return Fernet(settings.encryption_key.encode())


def encrypt_data(data: str) -> str:
    fernet = get_fernet()
    encrypted = fernet.encrypt(data.encode())
    return encrypted.decode()


def decrypt_data(encrypted_data: str) -> str:
    fernet = get_fernet()
    decrypted = fernet.decrypt(encrypted_data.encode())
    return decrypted.decode()


def safe_decrypt(encrypted_data: Optional[str]) -> Optional[str]:
    """decrypt, returning None on failure."""
    if not encrypted_data:
        return None
    try:
        return decrypt_data(encrypted_data)
    except (InvalidToken, ValueError):
        return None


def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def generate_session_id() -> str:
    return secrets.token_urlsafe(32)


def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)


def generate_password_reset_token() -> str:
    return secrets.token_urlsafe(32)


def generate_certificate_code(
    participant_id: str,
    cert_type: str,
    issued_at: datetime,
) -> str:
    """deterministic so it can be regenerated for verification; format H7-XXXX-XXXX-XXXX."""
    data = f"{participant_id}:{cert_type}:{issued_at.isoformat()}:{settings.cert_salt}"
    hash_hex = hashlib.sha256(data.encode()).hexdigest()[:12].upper()
    return f"H7-{hash_hex[:4]}-{hash_hex[4:8]}-{hash_hex[8:]}"


def verify_certificate_code(
    code: str,
    participant_id: str,
    cert_type: str,
    issued_at: datetime,
) -> bool:
    expected = generate_certificate_code(participant_id, cert_type, issued_at)
    return hmac.compare_digest(code, expected)


def generate_timed_token(data: str, expires_in: timedelta) -> str:
    expires_at = datetime.utcnow() + expires_in
    expires_ts = int(expires_at.timestamp())

    # format: data|expiry_timestamp|signature
    payload = f"{data}|{expires_ts}"
    signature = hmac.new(
        settings.secret_key.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()[:16]

    full_payload = f"{payload}|{signature}"
    return urlsafe_b64encode(full_payload.encode()).decode()


def verify_timed_token(token: str) -> Tuple[bool, Optional[str]]:
    try:
        decoded = urlsafe_b64decode(token.encode()).decode()
        parts = decoded.split("|")

        if len(parts) != 3:
            return False, None

        data, expires_ts, signature = parts

        payload = f"{data}|{expires_ts}"
        expected_signature = hmac.new(
            settings.secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()[:16]

        if not hmac.compare_digest(signature, expected_signature):
            return False, None

        expires_at = datetime.fromtimestamp(int(expires_ts))
        if datetime.utcnow() > expires_at:
            return False, None

        return True, data

    except Exception:
        return False, None


def sanitize_username(username: str) -> str:
    import re
    username = username.lower().strip()
    return re.sub(r'[^a-z0-9_-]', '', username)


def is_valid_username(username: str) -> bool:
    """3-50 chars, alphanumeric/underscore/hyphen, must start with a letter."""
    import re
    if not 3 <= len(username) <= 50:
        return False
    return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', username))


def is_valid_email(email: str) -> bool:
    from email_validator import EmailNotValidError, validate_email

    try:
        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False
