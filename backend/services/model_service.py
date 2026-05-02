import os
import asyncio
import urllib.parse
from typing import AsyncGenerator, Optional
import httpx

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are a powerful personal AI assistant. You are helpful, smart, and friendly.
You can help with coding, writing, analysis, math, research, and general questions.
When the user asks you to generate, create, draw, or make an image/photo/picture, respond with exactly:
IMAGE_GEN: <detailed image prompt here>
Make the image prompt very descriptive and detailed for best results.
For all other questions, answer clearly and thoroughly."""

IMAGE_TRIGGERS = [
    "generate", "create", "draw", "make", "paint", "design", "show me",
    "illustrate", "render", "produce", "give me", "can you make",
    "image of", "photo of", "picture of", "art of", "logo of"
]

IMAGE_NOUNS = ["image", "photo", "picture", "illustration", "artwork",
               "drawing", "painting", "portrait", "wallpaper", "logo", "icon", "art"]


class ModelService:
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.ready = False
        self._tool_service = None

    def set_tool_service(self, ts):
        self._tool_service = ts

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

    def _wants_image(self, text: str) -> bool:
        t = text.lower()
        has_trigger = any(w in t for w in IMAGE_TRIGGERS)
        has_noun = any(w in t for w in IMAGE_NOUNS)
        return has_trigger and has_noun

    def _wants_search(self, text: str) -> bool:
        t = text.lower()
        return any(w in t for w in [
            "today", "latest", "current", "news", "weather", "price",
            "score", "stock", "who won", "right now", "2025", "2026",
            "recently", "this week", "this month"
        ])

    async def _call_groq(self, messages: list, max_tokens: int = 1024) -> str:
        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
        r = await self.client.post(GROQ_API_URL, json=payload, headers=self._headers())
        print(f"Groq status: {r.status_code} | {r.text[:200]}")
        if r.status_code != 200:
            raise RuntimeError(f"Groq error {r.status_code}: {r.text[:300]}")
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()

    async def generate(self, messages: list, max_tokens: int = 1024, image_b64: str = None) -> str:
        if not self.ready:
            raise RuntimeError("Model not loaded")
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set.")

        last_msg = messages[-1]["content"] if messages else ""

        # Auto web search
        if self._wants_search(last_msg) and self._tool_service:
            try:
                result = await self._tool_service.run_tool("web_search", {"query": last_msg})
                items = result.get("result", [])
                if isinstance(items, list) and items:
                    snippets = "\n".join(
                        f"- {r.get('title','')}: {r.get('snippet','')}"
                        for r in items[:4]
                    )
                    augmented = f"Web search results:\n{snippets}\n\nUsing this, answer: {last_msg}"
                    messages = messages[:-1] + [{"role": "user", "content": augmented}]
            except Exception as e:
                print(f"Search failed: {e}")

        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [
            {"role": m["role"], "content": m["content"]} for m in messages
        ]

        response = await self._call_groq(full_messages, max_tokens)

        # If AI returns IMAGE_GEN directive, generate the image
        if response.startswith("IMAGE_GEN:"):
            prompt = response[10:].strip()
            encoded = urllib.parse.quote(prompt)
            img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&model=flux&nologo=true&enhance=true"
            return f"IMAGE:{img_url}|PROMPT:{prompt}"

        # Also detect if user directly asked for image without AI directive
        if self._wants_image(last_msg) and "IMAGE_GEN:" not in response and "IMAGE:" not in response:
            # Use user message as prompt directly
            encoded = urllib.parse.quote(last_msg)
            img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&model=flux&nologo=true&enhance=true"
            return f"IMAGE:{img_url}|PROMPT:{last_msg}\n\n{response}"

        return response

    async def generate_stream(self, messages: list) -> AsyncGenerator[str, None]:
        try:
            result = await self.generate(messages)
            for word in result.split():
                yield word + " "
                await asyncio.sleep(0.015)
        except Exception as e:
            yield f"Error: {str(e)}"

    async def close(self):
        if self.client:
            await self.client.aclose()
