from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from routers import chat, memory, tools, health, images, auth, projects
from services.model_service import ModelService
from services.tool_service import tool_service

model_service = ModelService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Retrai...")
    await model_service.load()
    model_service.set_tool_service(tool_service)
    app.state.model_service = model_service
    app.state.tool_service  = tool_service
    print("Retrai ready.")
    yield
    await model_service.close()

app = FastAPI(title="Retrai", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router,   prefix="/api")
app.include_router(auth.router,     prefix="/api")
app.include_router(chat.router,     prefix="/api")
app.include_router(memory.router,   prefix="/api")
app.include_router(tools.router,    prefix="/api")
app.include_router(images.router,   prefix="/api")
app.include_router(projects.router, prefix="/api")
