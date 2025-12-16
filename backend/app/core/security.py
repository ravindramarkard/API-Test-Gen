"""
Security utilities for encryption and authentication.
"""
from cryptography.fernet import Fernet
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Encryption for sensitive data
def get_fernet():
    """Get or create Fernet instance for encryption."""
    try:
        key = settings.ENCRYPTION_KEY.encode()
        if len(key) != 44:  # Fernet keys are 44 bytes when base64 encoded
            key = Fernet.generate_key()
            settings.ENCRYPTION_KEY = key.decode()
        return Fernet(key)
    except Exception:
        key = Fernet.generate_key()
        settings.ENCRYPTION_KEY = key.decode()
        return Fernet(key)

fernet = get_fernet()


def encrypt_data(data: str) -> str:
    """Encrypt sensitive data."""
    try:
        f = get_fernet()
        return f.encrypt(data.encode()).decode()
    except Exception:
        # If encryption fails, generate new key (for first run)
        f = Fernet.generate_key()
        settings.ENCRYPTION_KEY = f.decode()
        return Fernet(f).encrypt(data.encode()).decode()


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data."""
    if not encrypted_data:
        raise ValueError("No encrypted data provided")
    
    try:
        f = get_fernet()
        return f.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(f"Decryption failed: {error_type} - {error_msg}")
        
        # Provide more specific error messages
        if "InvalidToken" in error_type or "InvalidToken" in error_msg:
            raise ValueError(
                "Encrypted data is invalid or corrupted. This usually happens when the encryption key has changed. "
                "Please re-enter your API key."
            )
        elif "InvalidSignature" in error_type or "InvalidSignature" in error_msg:
            raise ValueError(
                "Encrypted data signature is invalid. The encryption key may have changed. "
                "Please re-enter your API key."
            )
        else:
            raise ValueError(f"Failed to decrypt data: {error_msg}. The encryption key may have changed. Please re-enter your API key.")


def hash_password(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None

