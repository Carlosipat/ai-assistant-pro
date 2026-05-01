from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from routers import chat, memory, tools, health
from services.model_service import ModelService
from services.tool_service import tool_service

model_service = ModelService()

@app.get("/")
def root():
    return {"status": "ok"}

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading AI model...")
    await model_service.load()
    model_service.set_tool_service(tool_service)  # wire tools into AI loop
    print("Model ready.")
    app.state.model_service = model_service
    yield
    await model_service.close()

app = FastAPI(title="AI Assistant Pro", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(tools.router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
