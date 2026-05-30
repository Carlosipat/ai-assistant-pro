"""
Auth system using Supabase Auth — free, no extra setup needed.
Users sign up / login with email+password.
Each user gets their own isolated chat history.
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
import httpx
import os

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

router = APIRouter(tags=["auth"])


class AuthRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    user_id: str
    email: str


class ResetRequest(BaseModel):
    email: str


def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
    }


def _get_user_id(token: str) -> str | None:
    """Decode JWT sub without a full validation lib (trusting Supabase)."""
    try:
        import base64, json as _json
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = _json.loads(base64.urlsafe_b64decode(payload))
        return decoded.get("sub")
    except Exception:
        return None


@router.post("/auth/signup", response_model=AuthResponse)
async def signup(body: AuthRequest):
    if not SUPABASE_URL:
        raise HTTPException(status_code=500, detail="Auth not configured")
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{SUPABASE_URL}/auth/v1/signup",
            json={"email": body.email, "password": body.password},
            headers=_sb_headers(),
        )
        if r.status_code not in (200, 201):
            err = r.json().get("msg", r.json().get("error_description", "Signup failed"))
            raise HTTPException(status_code=400, detail=err)
        d = r.json()
        # When email confirmation is ON, Supabase returns user but no access_token yet
        if "access_token" not in d:
            raise HTTPException(
                status_code=400,
                detail="Account created! Please check your email to confirm before signing in."
            )
        return AuthResponse(
            access_token=d["access_token"],
            user_id=d["user"]["id"],
            email=d["user"]["email"],
        )


@router.post("/auth/login", response_model=AuthResponse)
async def login(body: AuthRequest):
    if not SUPABASE_URL:
        raise HTTPException(status_code=500, detail="Auth not configured")
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            json={"email": body.email, "password": body.password},
            headers=_sb_headers(),
        )
        if r.status_code != 200:
            err = r.json().get("error_description", "Invalid email or password")
            raise HTTPException(status_code=401, detail=err)
        d = r.json()
        return AuthResponse(
            access_token=d["access_token"],
            user_id=d["user"]["id"],
            email=d["user"]["email"],
        )


@router.post("/auth/logout")
async def logout():
    return {"message": "Logged out"}


@router.post("/auth/reset-password")
async def reset_password(body: ResetRequest):
    """Send a password reset email via Supabase."""
    if not SUPABASE_URL:
        raise HTTPException(status_code=500, detail="Auth not configured")
    async with httpx.AsyncClient() as c:
        await c.post(
            f"{SUPABASE_URL}/auth/v1/recover",
            json={"email": body.email},
            headers=_sb_headers(),
        )
        return {"message": "If that account exists, a reset email was sent."}


@router.get("/auth/me")
async def get_me(authorization: str = Header(None)):
    if not authorization or not SUPABASE_URL:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "")
    async with httpx.AsyncClient() as c:
        r = await c.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={**_sb_headers(), "Authorization": f"Bearer {token}"},
        )
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
        d = r.json()
        return {"user_id": d["id"], "email": d["email"]}
