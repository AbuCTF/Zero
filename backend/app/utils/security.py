"""
Security utilities for ZeroPool.

Handles password hashing (CTFd compatible), encryption, and token generation.
"""

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


# =============================================================================
# Password Hashing (CTFd Compatible)
# =============================================================================


def hash_password(password: str) -> str:
    """
    Hash a password using pbkdf2:sha256 (CTFd compatible).
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    return generate_password_hash(
        password,
        method=settings.password_hash_method,
        salt_length=16,
    )


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        password: Plain text password to verify
        password_hash: Stored password hash
        
    Returns:
        True if password matches, False otherwise
    """
    return check_password_hash(password_hash, password)


# =============================================================================
# Credential Encryption (Fernet)
# =============================================================================


def get_fernet() -> Fernet:
    """
    Get Fernet instance for encryption/decryption.
    
    Raises:
        ValueError: If encryption key is not configured
    """
    if not settings.encryption_key:
        raise ValueError("ENCRYPTION_KEY not configured")
    return Fernet(settings.encryption_key.encode())


def encrypt_data(data: str) -> str:
    """
    Encrypt sensitive data (e.g., API keys, credentials).
    
    Args:
        data: Plain text data to encrypt
        
    Returns:
        Encrypted data as base64 string
    """
    fernet = get_fernet()
    encrypted = fernet.encrypt(data.encode())
    return encrypted.decode()


def decrypt_data(encrypted_data: str) -> str:
    """
    Decrypt sensitive data.
    
    Args:
        encrypted_data: Encrypted base64 string
        
    Returns:
        Decrypted plain text
        
    Raises:
        InvalidToken: If decryption fails
    """
    fernet = get_fernet()
    decrypted = fernet.decrypt(encrypted_data.encode())
    return decrypted.decode()


def safe_decrypt(encrypted_data: Optional[str]) -> Optional[str]:
    """
    Safely decrypt data, returning None on failure.
    
    Args:
        encrypted_data: Encrypted base64 string or None
        
    Returns:
        Decrypted plain text or None
    """
    if not encrypted_data:
        return None
    try:
        return decrypt_data(encrypted_data)
    except (InvalidToken, ValueError):
        return None


# =============================================================================
# Token Generation
# =============================================================================


def generate_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.
    
    Args:
        length: Number of bytes (output will be longer due to hex encoding)
        
    Returns:
        URL-safe token string
    """
    return secrets.token_urlsafe(length)


def generate_session_id() -> str:
    """Generate a secure session ID."""
    return secrets.token_urlsafe(32)


def generate_verification_token() -> str:
    """Generate an email verification token."""
    return secrets.token_urlsafe(32)


def generate_password_reset_token() -> str:
    """Generate a password reset token."""
    return secrets.token_urlsafe(32)


# =============================================================================
# Certificate Verification Codes
# =============================================================================


def generate_certificate_code(
    participant_id: str,
    cert_type: str,
    issued_at: datetime,
) -> str:
    """
    Generate a deterministic, verifiable certificate code.
    
    The code is deterministic so it can be regenerated for verification.
    
    Args:
        participant_id: UUID of the participant
        cert_type: Type of certificate (e.g., 'participation', 'winner')
        issued_at: When the certificate was issued
        
    Returns:
        Verification code in format H7-XXXX-XXXX-XXXX
    """
    data = f"{participant_id}:{cert_type}:{issued_at.isoformat()}:{settings.cert_salt}"
    hash_hex = hashlib.sha256(data.encode()).hexdigest()[:12].upper()
    return f"H7-{hash_hex[:4]}-{hash_hex[4:8]}-{hash_hex[8:]}"


def verify_certificate_code(
    code: str,
    participant_id: str,
    cert_type: str,
    issued_at: datetime,
) -> bool:
    """
    Verify a certificate code is valid.
    
    Args:
        code: The verification code to check
        participant_id: UUID of the participant
        cert_type: Type of certificate
        issued_at: When the certificate was issued
        
    Returns:
        True if code is valid, False otherwise
    """
    expected = generate_certificate_code(participant_id, cert_type, issued_at)
    return hmac.compare_digest(code, expected)


# =============================================================================
# Time-based Tokens
# =============================================================================


def generate_timed_token(data: str, expires_in: timedelta) -> str:
    """
    Generate a token that embeds data and expiration time.
    
    Args:
        data: Data to embed in token
        expires_in: How long until token expires
        
    Returns:
        URL-safe token string
    """
    expires_at = datetime.utcnow() + expires_in
    expires_ts = int(expires_at.timestamp())
    
    # Format: data|expiry_timestamp|signature
    payload = f"{data}|{expires_ts}"
    signature = hmac.new(
        settings.secret_key.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    
    full_payload = f"{payload}|{signature}"
    return urlsafe_b64encode(full_payload.encode()).decode()


def verify_timed_token(token: str) -> Tuple[bool, Optional[str]]:
    """
    Verify and decode a timed token.
    
    Args:
        token: The token to verify
        
    Returns:
        Tuple of (is_valid, data)
    """
    try:
        decoded = urlsafe_b64decode(token.encode()).decode()
        parts = decoded.split("|")
        
        if len(parts) != 3:
            return False, None
        
        data, expires_ts, signature = parts
        
        # Check signature
        payload = f"{data}|{expires_ts}"
        expected_signature = hmac.new(
            settings.secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        
        if not hmac.compare_digest(signature, expected_signature):
            return False, None
        
        # Check expiration
        expires_at = datetime.fromtimestamp(int(expires_ts))
        if datetime.utcnow() > expires_at:
            return False, None
        
        return True, data
        
    except Exception:
        return False, None


# =============================================================================
# Input Sanitization
# =============================================================================


def sanitize_username(username: str) -> str:
    """
    Sanitize username input.
    
    - Lowercase
    - Strip whitespace
    - Remove special characters except underscore and hyphen
    """
    import re
    username = username.lower().strip()
    return re.sub(r'[^a-z0-9_-]', '', username)


def is_valid_username(username: str) -> bool:
    """
    Check if username is valid.
    
    Rules:
    - 3-50 characters
    - Alphanumeric, underscore, hyphen only
    - Must start with letter
    """
    import re
    if not 3 <= len(username) <= 50:
        return False
    return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', username))


def is_valid_email(email: str) -> bool:
    """
    Check if email is valid.
    
    Uses email-validator for proper validation.
    """
    from email_validator import EmailNotValidError, validate_email
    
    try:
        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False
