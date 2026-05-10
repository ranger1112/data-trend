import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.api.config import Settings, get_settings


ROLE_LEVELS = {"readonly": 1, "reviewer": 2, "operator": 3}
bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AdminPrincipal:
    username: str
    role: str


def verify_admin_credentials(username: str, password: str, settings: Settings) -> AdminPrincipal | None:
    if not hmac.compare_digest(username, settings.admin_username):
        return None
    if not hmac.compare_digest(password, settings.admin_password):
        return None
    role = settings.admin_role if settings.admin_role in ROLE_LEVELS else "operator"
    return AdminPrincipal(username=username, role=role)


def create_access_token(principal: AdminPrincipal, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    payload = {
        "sub": principal.username,
        "role": principal.role,
        "exp": int(time.time()) + settings.auth_token_ttl_seconds,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    payload_part = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
    signature = _sign(payload_part, settings.auth_token_secret)
    return f"{payload_part}.{signature}"


def decode_access_token(token: str, settings: Settings | None = None) -> AdminPrincipal:
    settings = settings or get_settings()
    try:
        payload_part, signature = token.split(".", 1)
    except ValueError as exc:
        raise _auth_error("invalid token") from exc
    expected = _sign(payload_part, settings.auth_token_secret)
    if not hmac.compare_digest(signature, expected):
        raise _auth_error("invalid token")
    try:
        payload = json.loads(_b64decode(payload_part))
    except (ValueError, json.JSONDecodeError) as exc:
        raise _auth_error("invalid token") from exc
    if int(payload.get("exp", 0)) < int(time.time()):
        raise _auth_error("token expired")
    role = payload.get("role")
    username = payload.get("sub")
    if role not in ROLE_LEVELS or not isinstance(username, str):
        raise _auth_error("invalid token")
    return AdminPrincipal(username=username, role=role)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> AdminPrincipal:
    if credentials is None:
        raise _auth_error("missing token")
    return decode_access_token(credentials.credentials, settings)


def require_role(required_role: str):
    def dependency(principal: AdminPrincipal = Depends(get_current_admin)) -> AdminPrincipal:
        if ROLE_LEVELS[principal.role] < ROLE_LEVELS[required_role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role")
        return principal

    return dependency


def _sign(payload_part: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload_part.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _auth_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
