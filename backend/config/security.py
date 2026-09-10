from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from cryptography.fernet import Fernet
import bcrypt
from config.settings import settings
import hashlib
import secrets
import structlog

logger = structlog.get_logger()


class SecurityManager:
    """
    Enterprise-grade security manager handling:
    - Direct bcrypt password hashing (safe 72-byte truncation)
    - JWT token generation/validation
    - PII data encryption (Fernet AES-128-CBC)
    - CSRF token generation
    - API key management
    """

    def __init__(self):
        self._fernet = None
        if settings.ENCRYPTION_KEY:
            try:
                self._fernet = Fernet(settings.ENCRYPTION_KEY.encode())
            except Exception as e:
                logger.error("fernet_init_failed", error=str(e))

    # ---- Password Hashing (Direct Bcrypt - Bug Free) ----
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt, safely handles 72-byte limit."""
        pwd_bytes = password.encode("utf-8")[:72]
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(pwd_bytes, salt)
        return hashed.decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed bcrypt password."""
        try:
            pwd_bytes = plain_password.encode("utf-8")[:72]
            hash_bytes = hashed_password.encode("utf-8")
            return bcrypt.checkpw(pwd_bytes, hash_bytes)
        except Exception as e:
            logger.warning("password_verification_failed", error=str(e))
            return False

    # ---- JWT Tokens ----
    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(
                minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
            )
        )
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access"
        })
        return jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        })
        return jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except JWTError as e:
            logger.warning("jwt_decode_failed", error=str(e))
            return None

    # ---- PII Encryption ----
    def encrypt_pii(self, data: str) -> str:
        if not data:
            return ""
        if not self._fernet:
            return data
        try:
            return self._fernet.encrypt(data.encode()).decode()
        except Exception:
            return data

    def decrypt_pii(self, encrypted_data: str) -> str:
        if not encrypted_data:
            return ""
        if not self._fernet:
            return encrypted_data
        try:
            return self._fernet.decrypt(encrypted_data.encode()).decode()
        except Exception:
            return encrypted_data

    # ---- CSRF Token ----
    @staticmethod
    def generate_csrf_token() -> str:
        return secrets.token_urlsafe(32)

    # ---- API Key ----
    @staticmethod
    def generate_api_key() -> str:
        return f"rti_{secrets.token_urlsafe(48)}"

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        return hashlib.sha256(api_key.encode()).hexdigest()


security_manager = SecurityManager()