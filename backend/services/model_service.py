import os, asyncio, urllib.parse, json
from typing import AsyncGenerator, Optional
import httpx

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PRIMARY_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-haiku-4-5")
FALLBACK_MODEL = "mistralai/mistral-7b-instruct:free"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """IDENTITY — NEVER BREAK THIS RULE:
Your name is Retrai. Created by Carlosipat.
If asked who you are: "I am Retrai, a next-generation AI assistant created by Carlosipat."
NEVER say Claude, Gemma, GPT, Llama, Mistral, Haiku, Anthropic, Google, OpenAI, Meta.

PERSONALITY:
You are Retrai — the most advanced personal AI. Intelligent, helpful, direct, friendly.
Adapt to the user's language and tone. Never be robotic.

RESPONSE RULES — CRITICAL:
- Answer EXACTLY what was asked. Do not add unrequested content.
- NEVER show code unless user explicitly says: write code, create script, build, program, code.
- For general questions: give clear, conversational answers.
- Match response length to question complexity. Simple question = short answer.
- Use markdown only when it genuinely helps (complex topics, lists, comparisons).

SPECIAL OUTPUT FORMATS:

1. IMAGE GENERATION — when user asks to generate/draw/create/make any image/photo/art/logo:
Respond ONLY with:
IMAGE_GEN: <very detailed image description>

2. FILE GENERATION — when user asks to create/generate/make any file (document, script, spreadsheet, etc):
Respond ONLY with:
FILE_GEN:filename.ext
```language
complete file content here
```

3. WORD DOCUMENT — when user asks to create a Word doc, reviewer, report, essay, letter:
Respond ONLY with:
FILE_GEN:filename.docx
```
DOCUMENT_TITLE: Title Here
DOCUMENT_CONTENT:
Full document content here with proper formatting.
Use ## for headings, **bold**, bullet points etc.
```

4. CODE RUNNER — when user says "run this code" or "execute":
Show the code with explanation of what it would output.

5. DOCUMENT SUMMARY — when user uploads a file and asks to summarize:
Give a structured summary with: Overview, Key Points, Important Details, Conclusion.

6. TASK — when user asks to plan, schedule, or organize tasks:
Format as a clear numbered task list with priorities.

WEB SEARCH: You have real-time search. Never say you cannot search.
Always use search results when provided to give accurate current answers.

CAPABILITIES: Web search · Image generation · File & document creation
Code writing · File analysis · Task planning · Research · Writing"""

IMAGE_TRIGGERS = ["generate","create","draw","make","paint","design","show me","illustrate","render","image of","photo of","picture of","art of","logo","sketch","portrait","wallpaper","thumbnail","banner","icon","avatar"]
IMAGE_NOUNS = ["image","photo","picture","illustration","artwork","drawing","painting","portrait","wallpaper","logo","icon","art","meme","banner","thumbnail","poster","avatar","background","graphic","visual"]
FILE_TRIGGERS = ["create a file","generate a file","make a file","create a document","generate a document","make a document","write a document","create a word","make a word","create a report","generate a report","create a letter","write a letter","create an essay","write an essay","create a review","make a review","create a spreadsheet","generate csv","create html","write a script","create a script","generate code","create a .","make a .","save as","download as","create a txt","create a py","create a js","create a json"]


class ModelService:
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.ready = False
        self._tool_service = None

    def set_tool_service(self, ts):
        self._tool_service = ts

    async def load(self):
        self.client = httpx.AsyncClient(timeout=60.0)
        self.ready = True
        print(f"✓ Retrai Model Service Ready | OR:{'✓' if OPENROUTER_KEY else '✗'} | Groq:{'✓' if GROQ_API_KEY else '✗'}")

    def _or_h(self):
        return {"Authorization":f"Bearer {OPENROUTER_KEY}","Content-Type":"application/json",
                "HTTP-Referer":"https://ai-assistant-pro-ayb2.onrender.com","X-Title":"Retrai"}

    def _groq_h(self):
        return {"Authorization":f"Bearer {GROQ_API_KEY}","Content-Type":"application/json"}

    def _wants_image(self, t):
        tl=t.lower()
        return any(w in tl for w in IMAGE_TRIGGERS) and any(w in tl for w in IMAGE_NOUNS)

    def _wants_search(self, t):
        tl=t.lower()
        return any(w in tl for w in ["today","latest","current","news","weather","price","score","stock","who won","right now","2024","2025","2026","recently","this week","search","look up","what happened","breaking","trending","live","real-time","find out"])

    def _wants_file(self, t):
        tl=t.lower()
        return any(w in tl for w in FILE_TRIGGERS)

    def _trim(self, msgs):
        m=msgs[-10:]
        return [{"role":x["role"],"content":str(x["content"])[:1200]} for x in m]

    def _make_img(self, prompt, model=None, size=None):
        m=model or "flux"
        s=size or "1024x1024"
        w,h=s.split("x") if "x" in s else ("1024","1024")
        enc=urllib.parse.quote(prompt)
        return f"https://image.pollinations.ai/prompt/{enc}?width={w}&height={h}&model={m}&nologo=true&enhance=true"

    async def _call_or(self, messages, model, max_tokens):
        payload={"model":model,"messages":messages,"max_tokens":max_tokens,"temperature":0.7}
        r=await self.client.post(OPENROUTER_URL,json=payload,headers=self._or_h())
        print(f"OR[{model[:25]}]:{r.status_code}")
        if r.status_code!=200:
            raise RuntimeError(f"OR {r.status_code}: {r.text[:200]}")
        return (r.json()["choices"][0]["message"]["content"] or "").strip()

    async def _call_groq(self, messages, max_tokens):
        payload={"model":GROQ_MODEL,"messages":messages,"max_tokens":min(max_tokens,1024),"temperature":0.7}
        r=await self.client.post(GROQ_URL,json=payload,headers=self._groq_h())
        print(f"Groq[{GROQ_MODEL}]:{r.status_code}")
        if r.status_code!=200:
            raise RuntimeError(f"Groq {r.status_code}: {r.text[:200]}")
        return (r.json()["choices"][0]["message"]["content"] or "").strip()

    async def _get_response(self, full_msgs, max_tokens):
        """Try OpenRouter primary → fallback → Groq."""
        response = None
        if OPENROUTER_KEY:
            try:
                response = await self._call_or(full_msgs, PRIMARY_MODEL, max_tokens)
            except Exception as e:
                print(f"Primary failed: {e}")
                try:
                    response = await self._call_or(full_msgs, FALLBACK_MODEL, max_tokens)
                except Exception as e2:
                    print(f"Fallback failed: {e2}")
        if not response and GROQ_API_KEY:
            try:
                response = await self._call_groq(full_msgs, max_tokens)
            except Exception as e:
                raise RuntimeError(f"All providers failed: {e}")
        if not response:
            raise RuntimeError("No API keys configured. Add OPENROUTER_KEY in Render.")
        return response

    async def generate(self, messages, max_tokens=1024, image_b64=None):
        if not self.ready:
            raise RuntimeError("Model not loaded")
        messages = self._trim(messages)
        last = messages[-1]["content"] if messages else ""

        # Immediate image detection
        if self._wants_image(last) and not any(t in last.lower() for t in ["code","html","css","function","script","file"]):
            return f"IMAGE:{self._make_img(last)}|PROMPT:{last}"

        # Web search injection
        if self._wants_search(last) and self._tool_service:
            try:
                result = await self._tool_service.run_tool("web_search", {"query": last})
                items = result.get("result", [])
                if isinstance(items, list) and items:
                    snippets = "\n".join(f"[{i+1}] {r.get('title','')}: {r.get('snippet','')}" for i,r in enumerate(items[:5]))
                    messages = messages[:-1] + [{"role":"user","content":f"{last}\n\n[SEARCH RESULTS]\n{snippets}\n[/SEARCH RESULTS]\nUse these results to answer accurately."}]
            except Exception as e:
                print(f"Search error: {e}")

        full_msgs = [{"role":"system","content":SYSTEM_PROMPT}] + messages
        response = await self._get_response(full_msgs, max_tokens)

        if response.startswith("IMAGE_GEN:"):
            prompt = response[10:].strip()
            return f"IMAGE:{self._make_img(prompt)}|PROMPT:{prompt}"

        return response

    async def generate_stream(self, messages) -> AsyncGenerator[str, None]:
        """Real SSE streaming via OpenRouter, fallback to word-by-word simulation."""
        if not self.ready:
            yield "Error: Model not loaded"
            return

        messages = self._trim(messages)
        last = messages[-1]["content"] if messages else ""

        # Immediate image
        if self._wants_image(last) and not any(t in last.lower() for t in ["code","html","css","function","script","file"]):
            yield f"IMAGE:{self._make_img(last)}|PROMPT:{last}"
            return

        # Search injection
        if self._wants_search(last) and self._tool_service:
            try:
                result = await self._tool_service.run_tool("web_search", {"query": last})
                items = result.get("result", [])
                if isinstance(items, list) and items:
                    snippets = "\n".join(f"[{i+1}] {r.get('title','')}: {r.get('snippet','')}" for i,r in enumerate(items[:5]))
                    messages = messages[:-1] + [{"role":"user","content":f"{last}\n\n[SEARCH RESULTS]\n{snippets}\n[/SEARCH RESULTS]"}]
            except Exception as e:
                print(f"Stream search error: {e}")

        full_msgs = [{"role":"system","content":SYSTEM_PROMPT}] + messages

        # Try real OpenRouter streaming
        if OPENROUTER_KEY:
            try:
                payload = {"model":PRIMARY_MODEL,"messages":full_msgs,"max_tokens":1024,"temperature":0.7,"stream":True}
                async with self.client.stream("POST", OPENROUTER_URL, json=payload, headers=self._or_h(), timeout=60) as r:
                    if r.status_code == 200:
                        async for line in r.aiter_lines():
                            if line.startswith("data: "):
                                ds = line[6:]
                                if ds.strip() == "[DONE]":
                                    return
                                try:
                                    data = json.loads(ds)
                                    delta = data["choices"][0]["delta"].get("content","")
                                    if delta:
                                        yield delta
                                        await asyncio.sleep(0)
                                except (json.JSONDecodeError, KeyError, IndexError):
                                    continue
                        return
                    else:
                        print(f"OR stream {r.status_code}, falling back")
            except Exception as e:
                print(f"OR stream exception: {e}, falling back")

        # Fallback: full response, simulate streaming
        try:
            response = ""
            if GROQ_API_KEY:
                response = await self._call_groq(full_msgs, 1024)
            elif OPENROUTER_KEY:
                response = await self._call_or(full_msgs, FALLBACK_MODEL, 1024)
            else:
                yield "Error: No API keys configured."
                return

            if response.startswith("IMAGE_GEN:"):
                prompt = response[10:].strip()
                yield f"IMAGE:{self._make_img(prompt)}|PROMPT:{prompt}"
                return

            # Word-by-word simulation
            words = response.split()
            for i, word in enumerate(words):
                yield word + (" " if i < len(words)-1 else "")
                await asyncio.sleep(0.015)
        except Exception as e:
            yield f"Error: {str(e)}"

    async def close(self):
        if self.client:
            await self.client.aclose()
