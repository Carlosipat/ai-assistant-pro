from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routers import chat, memory, tools, health, images, auth
from services.model_service import ModelService
from services.tool_service import ToolService

model_service = ModelService()
tool_service = ToolService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading Retrai Pro...")
    await model_service.load()
    model_service.set_tool_service(tool_service)
    print("Ready.")
    app.state.model_service = model_service
    app.state.tool_service = tool_service
    yield

app = FastAPI(title="Retrai Pro", version="4.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(tools.router, prefix="/api")
app.include_router(images.router, prefix="/api")
