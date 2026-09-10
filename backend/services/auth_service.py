from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from models.user import User, UserSession
from schemas.user import (
    UserRegister, UserLogin, TokenResponse, UserResponse
)
from config.security import security_manager
from config.settings import settings
import hashlib
import structlog

logger = structlog.get_logger()


class AuthService:
    """Handles all authentication operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: UserRegister) -> Tuple[User, TokenResponse]:
        """Register a new user."""
        # Check if email already exists
        result = await self.db.execute(
            select(User).where(User.email == data.email)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise ValueError("Email already registered")

        # Check phone uniqueness
        if data.phone:
            result = await self.db.execute(
                select(User).where(User.phone == data.phone)
            )
            if result.scalar_one_or_none():
                raise ValueError("Phone number already registered")

        # Create user
        user = User(
            email=data.email,
            hashed_password=security_manager.hash_password(data.password),
            full_name_encrypted=security_manager.encrypt_pii(data.full_name)
                if settings.ENCRYPTION_KEY else data.full_name,
            phone=data.phone,
            address_encrypted=security_manager.encrypt_pii(data.address)
                if data.address and settings.ENCRYPTION_KEY else data.address,
            city=data.city,
            state=data.state,
            pincode=data.pincode,
            district=data.district,
            is_bpl=data.is_bpl,
        )

        self.db.add(user)
        await self.db.flush()

        # Generate tokens
        token_response = await self._create_tokens(user)

        logger.info("user_registered", user_id=user.id, email=user.email)
        return user, token_response

    async def login(
        self,
        data: UserLogin,
        ip_address: str = None,
        user_agent: str = None
    ) -> TokenResponse:
        """Authenticate user and return tokens."""
        result = await self.db.execute(
            select(User).where(User.email == data.email)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is deactivated")

        if not security_manager.verify_password(
            data.password, user.hashed_password
        ):
            raise ValueError("Invalid email or password")

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Create session and tokens
        token_response = await self._create_tokens(
            user, ip_address, user_agent
        )

        logger.info("user_logged_in", user_id=user.id)
        return token_response

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token."""
        payload = security_manager.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")

        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Invalid token payload")

        # Verify session exists
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        result = await self.db.execute(
            select(UserSession).where(
                UserSession.refresh_token_hash == token_hash,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.now(timezone.utc)
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError("Session expired or invalid")

        # Get user
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise ValueError("User not found or deactivated")

        # Invalidate old session
        session.is_active = False

        # Create new tokens
        return await self._create_tokens(user)

    async def logout(self, refresh_token: str) -> bool:
        """Invalidate session."""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        await self.db.execute(
            update(UserSession)
            .where(UserSession.refresh_token_hash == token_hash)
            .values(is_active=False)
        )
        return True

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    def get_user_display_name(self, user: User) -> str:
        """Decrypt and return user's full name."""
        if settings.ENCRYPTION_KEY:
            try:
                return security_manager.decrypt_pii(user.full_name_encrypted)
            except Exception:
                return user.full_name_encrypted
        return user.full_name_encrypted

    def get_user_address_for_filing(self, user: User) -> str:
        """Get full address string for portal filing."""
        parts = []
        if user.address_encrypted:
            if settings.ENCRYPTION_KEY:
                try:
                    parts.append(
                        security_manager.decrypt_pii(user.address_encrypted)
                    )
                except Exception:
                    parts.append(user.address_encrypted)
            else:
                parts.append(user.address_encrypted)

        if user.city:
            parts.append(user.city)
        if user.district:
            parts.append(user.district)
        if user.state:
            parts.append(user.state)
        if user.pincode:
            parts.append(f"Pin: {user.pincode}")

        return ", ".join(parts) if parts else ""

    def _get_user_address_for_filing(self, user: User) -> str:
        """Alias for backward compatibility."""
        return self.get_user_address_for_filing(user)

    async def _create_tokens(
        self,
        user: User,
        ip_address: str = None,
        user_agent: str = None
    ) -> TokenResponse:
        """Create access and refresh tokens."""
        token_data = {"sub": user.id, "email": user.email, "role": user.role.value if hasattr(user.role, 'value') else str(user.role)}

        access_token = security_manager.create_access_token(token_data)
        refresh_token = security_manager.create_refresh_token(token_data)

        # Store session
        session = UserSession(
            user_id=user.id,
            refresh_token_hash=hashlib.sha256(
                refresh_token.encode()
            ).hexdigest(),
            device_info=user_agent,
            ip_address=ip_address,
            expires_at=datetime.now(timezone.utc) + timedelta(
                days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
            )
        )
        self.db.add(session)

        # Build user response
        display_name = self.get_user_display_name(user)

        user_response = UserResponse(
            id=user.id,
            email=user.email,
            full_name=display_name,
            phone=user.phone,
            city=user.city,
            state=user.state,
            role=user.role,
            is_verified=user.is_verified,
            is_bpl=user.is_bpl,
            created_at=user.created_at,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_response,
        )