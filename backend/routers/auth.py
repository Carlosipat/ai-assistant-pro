"""
Simple auth system using Supabase Auth — free, no extra setup needed.
Users sign up/login with email. Each user gets their own chat history.
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


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    }


@router.post("/auth/signup", response_model=AuthResponse)
async def signup(body: AuthRequest):
    if not SUPABASE_URL:
        raise HTTPException(status_code=500, detail="Auth not configured")
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{SUPABASE_URL}/auth/v1/signup",
            json={"email": body.email, "password": body.password},
            headers=_headers()
        )
        if r.status_code not in (200, 201):
            err = r.json().get("msg", r.json().get("error_description", "Signup failed"))
            raise HTTPException(status_code=400, detail=err)
        d = r.json()
        return AuthResponse(
            access_token=d["access_token"],
            user_id=d["user"]["id"],
            email=d["user"]["email"]
        )


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
            err = r.json().get("error_description", "Invalid email or password")
            raise HTTPException(status_code=401, detail=err)
        d = r.json()
        return AuthResponse(
            access_token=d["access_token"],
            user_id=d["user"]["id"],
            email=d["user"]["email"]
        )


@router.post("/auth/logout")
async def logout():
    return {"message": "Logged out successfully"}


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
        return {"user_id": d["id"], "email": d["email"]}
