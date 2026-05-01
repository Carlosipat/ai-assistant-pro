import httpx
import os
import json
import math
import re
from typing import Any

SERPER_KEY = os.getenv("SERPER_API_KEY", "")
WEATHER_KEY = os.getenv("OPENWEATHER_KEY", "")


class ToolService:
    def __init__(self):
        self.available_tools = {
            "web_search": self.web_search,
            "calculator": self.calculator,
            "get_weather": self.get_weather,
            "datetime": self.get_datetime,
        }

    def get_tool_descriptions(self) -> list[dict]:
        return [
            {"name": "web_search", "description": "Search the web for current information", "params": ["query"]},
            {"name": "calculator", "description": "Evaluate a math expression", "params": ["expression"]},
            {"name": "get_weather", "description": "Get current weather for a city", "params": ["city"]},
            {"name": "datetime", "description": "Get current date and time", "params": []},
        ]

    async def run_tool(self, tool_name: str, params: dict) -> dict:
        if tool_name not in self.available_tools:
            return {"error": f"Tool '{tool_name}' not found"}
        try:
            result = await self.available_tools[tool_name](**params)
            return {"tool": tool_name, "result": result, "success": True}
        except Exception as e:
            return {"tool": tool_name, "error": str(e), "success": False}

    async def web_search(self, query: str) -> Any:
        if not SERPER_KEY:
            return {"message": "Web search not configured. Set SERPER_API_KEY env var.", "query": query}
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": 5},
                timeout=10.0
            )
            r.raise_for_status()
            data = r.json()
            results = []
            for item in data.get("organic", [])[:5]:
                results.append({
                    "title": item.get("title"),
                    "snippet": item.get("snippet"),
                    "link": item.get("link"),
                })
            return results

    async def calculator(self, expression: str) -> Any:
        # Safe eval — only allow math operations
        safe_expr = re.sub(r'[^0-9+\-*/().%^ ]', '', expression)
        safe_expr = safe_expr.replace('^', '**')
        allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith('_')}
        try:
            result = eval(safe_expr, {"__builtins__": {}}, allowed_names)
            return {"expression": expression, "result": result}
        except Exception as e:
            return {"error": f"Could not evaluate: {expression}"}

    async def get_weather(self, city: str) -> Any:
        if not WEATHER_KEY:
            return {"message": "Weather not configured. Set OPENWEATHER_KEY env var.", "city": city}
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": WEATHER_KEY, "units": "metric"},
                timeout=10.0
            )
            r.raise_for_status()
            data = r.json()
            return {
                "city": data["name"],
                "temp_c": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "description": data["weather"][0]["description"],
                "humidity": data["main"]["humidity"],
            }

    async def get_datetime(self) -> Any:
        from datetime import datetime
        now = datetime.now()
        return {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day": now.strftime("%A"),
            "datetime_iso": now.isoformat(),
        }


tool_service = ToolService()
