"""
Security and authentication module for Odoo MCP HTTP transport

Provides API key management, authentication middleware, rate limiting,
and security utilities for the HTTP transport layer.
"""

import hashlib
import secrets
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

# Security configuration
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Password hashing - use simple SHA256 for now due to bcrypt issues


@dataclass
class APIKey:
    """API key model for authentication"""

    key_id: str
    key_hash: str
    name: str
    created_at: datetime
    last_used: Optional[datetime] = None
    is_active: bool = True
    scopes: Set[str] = field(default_factory=set)
    rate_limit: int = 1000  # requests per hour

    def verify_key(self, key: str) -> bool:
        """Verify a plain text key against the stored hash"""
        return self.key_hash == hashlib.sha256(key.encode()).hexdigest()

    def update_last_used(self) -> None:
        """Update the last used timestamp"""
        self.last_used = datetime.utcnow()


@dataclass
class RateLimitInfo:
    """Rate limiting information for a client"""

    requests: List[float] = field(default_factory=list)
    blocked_until: Optional[float] = None

    def is_blocked(self) -> bool:
        """Check if the client is currently blocked"""
        if self.blocked_until is None:
            return False
        return time.time() < self.blocked_until

    def add_request(self, timestamp: float) -> None:
        """Add a request timestamp"""
        self.requests.append(timestamp)
        # Keep only requests from the last hour
        cutoff = timestamp - 3600
        self.requests = [t for t in self.requests if t >= cutoff]

    def get_request_count(self) -> int:
        """Get the current request count in the last hour"""
        return len(self.requests)

    def block_for(self, seconds: int) -> None:
        """Block the client for a specified number of seconds"""
        self.blocked_until = time.time() + seconds


class SecurityManager:
    """Central security manager for API keys and rate limiting"""

    def __init__(self):
        self.api_keys: Dict[str, APIKey] = {}
        self.rate_limits: Dict[str, RateLimitInfo] = defaultdict(RateLimitInfo)
        self._initialize_default_keys()

    def _initialize_default_keys(self) -> None:
        """Initialize with a default API key for development"""
        default_key = self.create_api_key(
            "default-dev-key", scopes={"read", "write", "admin"}, rate_limit=10000
        )
        print(f"Default API key created: {default_key}")

    def create_api_key(
        self, name: str, scopes: Optional[Set[str]] = None, rate_limit: int = 1000
    ) -> str:
        """
        Create a new API key

        Args:
            name: Human-readable name for the key
            scopes: Set of scopes for authorization
            rate_limit: Requests per hour limit

        Returns:
            The plain text API key (store this securely!)
        """
        key_id = secrets.token_urlsafe(16)
        plain_key = f"odoo_mcp_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()

        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            created_at=datetime.utcnow(),
            scopes=scopes or set(),
            rate_limit=rate_limit,
        )

        self.api_keys[key_id] = api_key
        return plain_key

    def verify_api_key(self, key: str) -> Optional[APIKey]:
        """
        Verify an API key and return the associated APIKey object

        Args:
            key: Plain text API key

        Returns:
            APIKey object if valid, None otherwise
        """
        for api_key in self.api_keys.values():
            if api_key.is_active and api_key.verify_key(key):
                api_key.update_last_used()
                return api_key
        return None

    def check_rate_limit(self, key_id: str, rate_limit: int) -> bool:
        """
        Check if a client has exceeded their rate limit

        Args:
            key_id: Client identifier (API key ID)
            rate_limit: Maximum requests per hour

        Returns:
            True if request should be allowed, False if rate limited
        """
        rate_info = self.rate_limits[key_id]

        # Check if currently blocked
        if rate_info.is_blocked():
            return False

        current_time = time.time()
        rate_info.add_request(current_time)

        # Check if exceeding rate limit
        if rate_info.get_request_count() > rate_limit:
            # Block for 1 hour
            rate_info.block_for(3600)
            return False

        return True

    def revoke_api_key(self, key_id: str) -> bool:
        """
        Revoke an API key

        Args:
            key_id: Key ID to revoke

        Returns:
            True if key was found and revoked
        """
        if key_id in self.api_keys:
            self.api_keys[key_id].is_active = False
            return True
        return False

    def list_api_keys(self) -> List[Dict[str, Any]]:
        """
        List all API keys (without sensitive information)

        Returns:
            List of API key information
        """
        return [
            {
                "key_id": api_key.key_id,
                "name": api_key.name,
                "created_at": api_key.created_at.isoformat(),
                "last_used": (
                    api_key.last_used.isoformat() if api_key.last_used else None
                ),
                "is_active": api_key.is_active,
                "scopes": list(api_key.scopes),
                "rate_limit": api_key.rate_limit,
            }
            for api_key in self.api_keys.values()
        ]


# Global security manager instance
security_manager = SecurityManager()


class APIKeyAuth(HTTPBearer):
    """FastAPI authentication dependency for API keys"""

    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[APIKey]:
        """
        Authenticate request using API key

        Args:
            request: FastAPI request object

        Returns:
            APIKey object if authenticated

        Raises:
            HTTPException: If authentication fails
        """
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)

        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key",
                headers={"WWW-Authenticate": "Bearer"},
            )

        api_key = security_manager.verify_api_key(credentials.credentials)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check rate limiting
        if not security_manager.check_rate_limit(api_key.key_id, api_key.rate_limit):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )

        return api_key


def require_scope(required_scope: str):
    """
    Decorator to require specific scopes for endpoints

    Args:
        required_scope: Required scope for access
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract api_key from kwargs (should be injected by dependency)
            api_key = kwargs.get("api_key")
            if not api_key or required_scope not in api_key.scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required scope: {required_scope}",
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token

    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time

    Returns:
        JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT token

    Args:
        token: JWT token string

    Returns:
        Decoded token data if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def hash_password(password: str) -> str:
    """Hash a password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password


def generate_session_id() -> str:
    """Generate a secure session ID for MCP sessions"""
    return secrets.token_urlsafe(32)


def validate_cors_origin(origin: str, allowed_origins: List[str]) -> bool:
    """
    Validate CORS origin against allowed origins

    Args:
        origin: Origin to validate
        allowed_origins: List of allowed origins (supports wildcards)

    Returns:
        True if origin is allowed
    """
    if "*" in allowed_origins:
        return True

    for allowed in allowed_origins:
        if allowed.endswith("*"):
            if origin.startswith(allowed[:-1]):
                return True
        elif origin == allowed:
            return True

    return False
