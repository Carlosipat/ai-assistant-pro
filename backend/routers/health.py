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
    # NEVER expose supabase_key or any secret in a public endpoint.
    return {
        "status": "ok",
        "model_ready": model_ready.ready if model_ready else False,
        "version": "3.0.0",
        "providers": providers,
    }
