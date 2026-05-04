"""
Simple auth system using Supabase Auth.
- Signup with auto-login fallback
- Login
- Get current user
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
import httpx
import os

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

router = APIRouter(tags=["auth"])


# ----------------------
# Models
# ----------------------

class AuthRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    user_id: str
    email: str


# ----------------------
# Helpers
# ----------------------

def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    }


# ----------------------
# Signup (AUTO LOGIN)
# ----------------------

@router.post("/auth/signup", response_model=AuthResponse)
async def signup(body: AuthRequest):
    if not SUPABASE_URL:
        raise HTTPException(status_code=500, detail="Auth not configured")

    async with httpx.AsyncClient() as c:
        # 1. Signup
        r = await c.post(
            f"{SUPABASE_URL}/auth/v1/signup",
            json={"email": body.email, "password": body.password},
            headers=_headers()
        )

        if r.status_code not in (200, 201):
            err_data = r.json()
            err = err_data.get("msg") or err_data.get("error_description") or "Signup failed"
            raise HTTPException(status_code=400, detail=err)

        d = r.json()
        user = d.get("user")
        session = d.get("session")

        if not user:
            raise HTTPException(status_code=400, detail="Signup failed (no user returned)")

        # ✅ Case 1: Supabase already returned a session
        if session:
            return AuthResponse(
                access_token=session.get("access_token"),
                user_id=user.get("id"),
                email=user.get("email")
            )

        # 🔁 Case 2: No session → auto-login
        login_res = await c.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            json={"email": body.email, "password": body.password},
            headers=_headers()
        )

        if login_res.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail="Signup succeeded but auto-login failed (email confirmation may be required)"
            )

        login_data = login_res.json()

        return AuthResponse(
            access_token=login_data.get("access_token"),
            user_id=login_data.get("user", {}).get("id"),
            email=login_data.get("user", {}).get("email")
        )


# ----------------------
# Login
# ----------------------

@router.post("/auth/login", response_model=AuthResponse)
async def login(body: AuthRequest):
    if not SUPABASE_URL:
        raise HTTPException(status_code=500, detail="Auth not configured")

    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            json={"email": body.email, "password": body.password},
            headers=_headers()
        )

        if r.status_code != 200:
            err_data = r.json()
            err = err_data.get("error_description") or "Invalid email or password"
            raise HTTPException(status_code=401, detail=err)

        d = r.json()

        return AuthResponse(
            access_token=d.get("access_token"),
            user_id=d.get("user", {}).get("id"),
            email=d.get("user", {}).get("email")
        )


# ----------------------
# Logout (client-side)
# ----------------------

@router.post("/auth/logout")
async def logout():
    return {"message": "Logged out successfully"}


# ----------------------
# Get Current User
# ----------------------

@router.get("/auth/me")
async def get_me(authorization: str = Header(None)):
    if not authorization or not SUPABASE_URL:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.replace("Bearer ", "")

    async with httpx.AsyncClient() as c:
        r = await c.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={**_headers(), "Authorization": f"Bearer {token}"}
        )

        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")

        d = r.json()

        return {
            "user_id": d.get("id"),
            "email": d.get("email")
        }
