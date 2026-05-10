from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.config import Settings, get_settings
from apps.api.schemas import LoginRequest, LoginResponse, MeResponse
from apps.api.security import AdminPrincipal, create_access_token, get_current_admin, verify_admin_credentials


router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, settings: Settings = Depends(get_settings)):
    principal = verify_admin_credentials(payload.username, payload.password, settings)
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    return {
        "access_token": create_access_token(principal, settings),
        "token_type": "bearer",
        "expires_in": settings.auth_token_ttl_seconds,
        "role": principal.role,
        "username": principal.username,
    }


@router.get("/me", response_model=MeResponse)
def me(principal: AdminPrincipal = Depends(get_current_admin)):
    return {"username": principal.username, "role": principal.role}
