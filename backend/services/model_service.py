import os
import asyncio
import urllib.parse
from typing import AsyncGenerator, Optional
import httpx

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Use Claude Haiku — actually follows system prompts, very cheap (~$0.25/1M tokens)
# Fallback chain: haiku -> mistral -> groq
PRIMARY_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-haiku-4-5")
FALLBACK_MODEL = "mistralai/mistral-small-3.2-24b-instruct:free"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are Retrai, a personal AI assistant created by Carlosipat.

IDENTITY — ABSOLUTE RULE:
- Your name is RETRAI. Created by CARLOSIPAT.
- If asked who you are, what model you are, who made you: always say "I am Retrai, created by Carlosipat."
- NEVER say you are Claude, Gemma, GPT, Llama, Mistral, Haiku, or any other model/company.
- NEVER mention Anthropic, Google, OpenAI, Meta, or any AI company.

RESPONSE STYLE — CRITICAL:
- Answer conversationally and directly. Match the user's tone.
- NEVER show code unless the user explicitly asks for code, a script, or says "write", "build", "create a program".
- If someone asks what something is, explain it in plain words. No code.
- Keep answers concise and focused on exactly what was asked.
- Only use bullet points or headers when the topic genuinely needs structure.

FILE GENERATION:
When user asks to generate, create, or make a file (document, script, spreadsheet, etc.):
Respond with this exact format:
FILE_GEN:filename.extension
```
full file content here
```

IMAGE GENERATION:
When user asks to generate, draw, create, or make an image/photo/picture/art/logo:
Respond with ONLY this:
IMAGE_GEN: <very detailed description of the image>

WEB SEARCH:
- You have real-time web search. ALWAYS use search results when provided.
- Never say you cannot search the web.

PERSONALITY:
- Friendly, smart, direct, professional.
- Never swear or use inappropriate language.
- Be helpful without being verbose."""

IMAGE_TRIGGERS = ["generate","create","draw","make","paint","design","show me",
                  "illustrate","render","image of","photo of","picture of","art of",
                  "logo","sketch","portrait","wallpaper","thumbnail","banner","icon"]
IMAGE_NOUNS = ["image","photo","picture","illustration","artwork","drawing",
               "painting","portrait","wallpaper","logo","icon","art","meme",
               "banner","thumbnail","poster","avatar","background"]

FILE_TRIGGERS = ["generate a file","create a file","make a file","write a file",
                 "generate a document","create a document","make a document",
                 "generate a script","create a script","save as","download as",
                 "give me a .","create a .py","create a .html","create a .txt",
                 "create a .csv","create a .json","make a ."]


class ModelService:
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.ready = False
        self._tool_service = None

    def set_tool_service(self, ts):
        self._tool_service = ts
        print("✓ Tool service connected")

    async def load(self):
        self.client = httpx.AsyncClient(timeout=60.0)
        self.ready = True
        print(f"✓ Model ready | OpenRouter: {'yes' if OPENROUTER_KEY else 'NO KEY'}")

    def _wants_image(self, text: str) -> bool:
        t = text.lower()
        return any(w in t for w in IMAGE_TRIGGERS) and any(w in t for w in IMAGE_NOUNS)

    def _wants_search(self, text: str) -> bool:
        t = text.lower()
        return any(w in t for w in [
            "today","latest","current","news","weather","price","cost",
            "score","stock","who won","right now","2024","2025","2026",
            "recently","this week","this month","last week","search",
            "find","look up","what happened","breaking","trending","update","live"
        ])

    def _trim(self, messages: list) -> list:
        msgs = messages[-10:]
        return [{"role": m["role"], "content": str(m["content"])[:1000]} for m in msgs]

    def _make_image_url(self, prompt: str) -> str:
        encoded = urllib.parse.quote(prompt)
        return f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&model=flux&nologo=true&enhance=true"

    async def _call_openrouter(self, messages: list, model: str, max_tokens: int) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ai-assistant-pro-ayb2.onrender.com",
            "X-Title": "Retrai Pro"
        }
        r = await self.client.post(OPENROUTER_URL, json=payload, headers=headers)
        print(f"OpenRouter [{model}]: {r.status_code}")
        if r.status_code != 200:
            raise RuntimeError(f"OpenRouter {r.status_code}: {r.text[:200]}")
        content = r.json()["choices"][0]["message"]["content"]
        return (content or "").strip()

    async def _call_groq(self, messages: list, max_tokens: int) -> str:
        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "max_tokens": min(max_tokens, 1024),
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        r = await self.client.post(GROQ_URL, json=payload, headers=headers)
        print(f"Groq [{GROQ_MODEL}]: {r.status_code}")
        if r.status_code != 200:
            raise RuntimeError(f"Groq {r.status_code}: {r.text[:200]}")
        content = r.json()["choices"][0]["message"]["content"]
        return (content or "").strip()

    async def generate(self, messages: list, max_tokens: int = 1024, image_b64: str = None) -> str:
        if not self.ready:
            raise RuntimeError("Model not loaded")

        messages = self._trim(messages)
        last_msg = messages[-1]["content"] if messages else ""

        # Detect pure image request immediately
        if self._wants_image(last_msg) and not any(
            t in last_msg.lower() for t in ["code","script","html","css","function"]
        ):
            prompt = last_msg
            img_url = self._make_image_url(prompt)
            return f"IMAGE:{img_url}|PROMPT:{prompt}"

        # Auto web search
        if self._wants_search(last_msg) and self._tool_service:
            try:
                result = await self._tool_service.run_tool("web_search", {"query": last_msg})
                items = result.get("result", [])
                if isinstance(items, list) and items:
                    snippets = "\n".join(
                        f"[{i+1}] {r.get('title','')}: {r.get('snippet','')}"
                        for i, r in enumerate(items[:5])
                    )
                    augmented = f"{last_msg}\n\n[SEARCH RESULTS]\n{snippets}\n[/SEARCH RESULTS]"
                    messages = messages[:-1] + [{"role":"user","content":augmented}]
                    print(f"✓ Search injected {len(items)} results")
            except Exception as e:
                print(f"Search error: {e}")

        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

        # Try primary model first (Claude Haiku - follows instructions)
        response = None
        if OPENROUTER_KEY:
            try:
                response = await self._call_openrouter(full_messages, PRIMARY_MODEL, max_tokens)
            except Exception as e:
                print(f"Primary failed: {e}, trying fallback...")
                try:
                    response = await self._call_openrouter(full_messages, FALLBACK_MODEL, max_tokens)
                except Exception as e2:
                    print(f"Fallback failed: {e2}")

        # Last resort: Groq
        if not response and GROQ_API_KEY:
            try:
                response = await self._call_groq(full_messages, max_tokens)
            except Exception as e:
                raise RuntimeError(f"All providers failed: {e}")

        if not response:
            raise RuntimeError("No API keys configured.")

        # Handle IMAGE_GEN directive from AI
        if response.startswith("IMAGE_GEN:"):
            prompt = response[10:].strip()
            img_url = self._make_image_url(prompt)
            return f"IMAGE:{img_url}|PROMPT:{prompt}"

        # Handle FILE_GEN directive from AI
        if response.startswith("FILE_GEN:"):
            return response  # frontend handles this

        return response

    async def generate_stream(self, messages: list) -> AsyncGenerator[str, None]:
        try:
            result = await self.generate(messages)
            for word in result.split():
                yield word + " "
                await asyncio.sleep(0.01)
        except Exception as e:
            yield f"Error: {str(e)}"

    async def close(self):
        if self.client:
            await self.client.aclose()
