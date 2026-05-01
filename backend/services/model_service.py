import os
import json
import asyncio
from typing import AsyncGenerator, Optional
import httpx

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are a helpful, smart personal AI assistant. Answer clearly and concisely.
You can help with coding, writing, analysis, math, and general questions.
If asked about current events or real-time info, say you'll try to find it.
Be friendly and thorough."""


class ModelService:
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.ready = False
        self._tool_service = None

    def set_tool_service(self, tool_service):
        self._tool_service = tool_service

    async def load(self):
        self.client = httpx.AsyncClient(timeout=60.0)
        if not GROQ_API_KEY:
            print("WARNING: GROQ_API_KEY not set!")
        self.ready = True

    def _headers(self):
        return {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

    async def _call_groq(self, messages: list, model: str, max_tokens: int = 1024) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
        try:
            r = await self.client.post(GROQ_API_URL, json=payload, headers=self._headers())
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Groq error {e.response.status_code}: {e.response.text}")

    async def generate(self, messages: list, max_tokens: int = 1024, image_b64: str = None) -> str:
        if not self.ready:
            raise RuntimeError("Model not loaded")
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY not set. Add it in Render Environment tab.")

        # Vision mode
        if image_b64:
            vision_messages = [
                {"role": "system", "content": "You are a helpful vision AI. Describe and analyze images in detail."},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    {"type": "text", "text": messages[-1]["content"] if messages else "Describe this image."}
                ]}
            ]
            try:
                return await self._call_groq(vision_messages, GROQ_VISION_MODEL, max_tokens)
            except Exception as e:
                # Fallback if vision model fails
                return f"Image received. Vision analysis: {str(e)}. Try asking a text question instead."

        # Auto web search: detect if query needs current info
        last_msg = messages[-1]["content"].lower() if messages else ""
        needs_search = any(w in last_msg for w in [
            "today", "latest", "current", "news", "weather", "price",
            "score", "stock", "who won", "right now", "2025", "2026"
        ])

        if needs_search and self._tool_service:
            try:
                # Extract search query from last message
                query = messages[-1]["content"] if messages else ""
                result = await self._tool_service.run_tool("web_search", {"query": query})
                search_data = result.get("result", [])
                if search_data and isinstance(search_data, list):
                    snippets = "\n".join([
                        f"- {r.get('title', '')}: {r.get('snippet', '')}"
                        for r in search_data[:3]
                    ])
                    search_context = f"Web search results:\n{snippets}\n\nUsing this info, answer: {messages[-1]['content']}"
                    augmented = messages[:-1] + [{"role": "user", "content": search_context}]
                    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + augmented
                    return await self._call_groq(full_messages, GROQ_MODEL, max_tokens)
            except Exception:
                pass  # Fall through to normal generation

        # Normal generation
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        return await self._call_groq(full_messages, GROQ_MODEL, max_tokens)

    async def generate_stream(self, messages: list) -> AsyncGenerator[str, None]:
        try:
            result = await self.generate(messages)
            words = result.split()
            for i, word in enumerate(words):
                yield word + (" " if i < len(words) - 1 else "")
                await asyncio.sleep(0.015)
        except Exception as e:
            yield f"Error: {str(e)}"

    async def close(self):
        if self.client:
            await self.client.aclose()
