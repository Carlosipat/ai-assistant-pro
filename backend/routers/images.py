"""
Image generation via Pollinations.ai — completely free, no API key needed.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

router = APIRouter(tags=["images"])

class ImageRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 1024
    model: str = "flux"  # flux, turbo, flux-realism, flux-anime, flux-3d

@router.post("/images/generate")
async def generate_image(body: ImageRequest):
    """Generate image using Pollinations.ai (free, no key needed)."""
    import urllib.parse
    encoded = urllib.parse.quote(body.prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={body.width}&height={body.height}&model={body.model}&nologo=true&enhance=true"
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            return {
                "url": url,
                "prompt": body.prompt,
                "width": body.width,
                "height": body.height,
                "model": body.model
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")

@router.get("/images/models")
async def list_image_models():
    return {
        "models": [
            {"id": "flux", "name": "Flux", "description": "Best quality, photorealistic"},
            {"id": "turbo", "name": "Turbo", "description": "Fastest generation"},
            {"id": "flux-realism", "name": "Flux Realism", "description": "Hyper realistic photos"},
            {"id": "flux-anime", "name": "Flux Anime", "description": "Anime & illustration style"},
            {"id": "flux-3d", "name": "Flux 3D", "description": "3D rendered style"},
        ]
    }
