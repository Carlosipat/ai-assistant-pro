from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request):
    model_ready = getattr(request.app.state, "model_service", None)
    return {
        "status": "ok",
        "model_ready": model_ready.ready if model_ready else False,
        "version": "1.0.0"
    }
