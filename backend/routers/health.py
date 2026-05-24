from fastapi import APIRouter, Request
import os

router = APIRouter(tags=["health"])

@router.get("/health")
async def health(request: Request):
    model_ready = getattr(request.app.state, "model_service", None)
    providers = []
    if os.getenv("GROQ_API_KEY"):    providers.append("groq")
    if os.getenv("GEMINI_API_KEY"):  providers.append("gemini")
    if os.getenv("OPENROUTER_KEY"):  providers.append("openrouter")
    # SUPABASE_ANON_KEY is the public key safe for frontend OAuth
    # Falls back to SUPABASE_KEY if anon not set (service role — works for OAuth too)
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY", "")
    return {
        "status": "ok",
        "model_ready": model_ready.ready if model_ready else False,
        "version": "3.0.0",
        "providers": providers,
        "supabase_key": anon_key,
        "site_url": os.getenv("SITE_URL", ""),
    }
