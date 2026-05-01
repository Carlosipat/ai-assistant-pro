from fastapi import APIRouter
from models.schemas import ToolRunRequest
from services.tool_service import tool_service

router = APIRouter(tags=["tools"])


@router.get("/tools")
async def list_tools():
    return {"tools": tool_service.get_tool_descriptions()}


@router.post("/tools/run")
async def run_tool(body: ToolRunRequest):
    result = await tool_service.run_tool(body.tool_name, body.params)
    return result
