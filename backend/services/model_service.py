import os, asyncio, time, json, re, urllib.parse
from collections import defaultdict
from typing import AsyncGenerator, Optional
import httpx

GEMINI_URL  = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_KEY  = os.getenv("GEMINI_API_KEY", "")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_raw           = os.getenv("OPENROUTER_MODEL", "").strip().splitlines()[0].strip()
PRIMARY_MODEL  = _raw or None
OR_FREE        = ["openrouter/auto"]
GROQ_KEY   = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
RATE_LIMIT  = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
RATE_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW",   "60"))

SYSTEM_PROMPT = """You are Retrai, an advanced AI assistant created by Carlosipat.

IDENTITY — NEVER BREAK:
- Your name is Retrai. Created by Carlosipat.
- If asked who you are or what model powers you, say: "I am Retrai, an advanced AI assistant created by Carlosipat."
- NEVER say you are Claude, Gemini, GPT, Llama, Mistral, or any other model.
- NEVER mention Anthropic, Google, OpenAI, Meta, or any AI company.

PERSONALITY:
- Warm, intelligent, direct, never robotic.
- Always respond in the same language the user writes in.
- Casual stays casual, technical gets technical. Match the user.

RESPONSE RULES:
- Answer exactly what was asked. Be concise and precise.
- Simple question = short conversational answer.
- Complex topic = well-structured markdown answer.
- NEVER show code unless explicitly asked: write / create / build / code / script / program.
- Use markdown (headers, lists, bold) only when it genuinely improves clarity.
- No unnecessary apologies, disclaimers, or filler phrases.

SPECIAL OUTPUT FORMATS — use exactly when triggered:

IMAGE GENERATION (user asks to generate/draw/create/paint/design any image):
IMAGE_GEN: <vivid, detailed image description>

FILE GENERATION (user asks to create/write/generate any file, document, or code file):
FILE_GEN: <filename.ext>|<complete file content here>

WEB SEARCH (for current info, news, prices, weather, anything recent):
TOOL: web_search | PARAMS: {"query": "search query"}

CALCULATOR:
TOOL: calculator | PARAMS: {"expression": "2 * (3+4)"}

WEATHER:
TOOL: get_weather | PARAMS: {"city": "Manila"}

CAPABILITIES:
Real-time web search · Image generation · File creation & download
Code writing & review · File analysis (PDF, DOCX, images, CSV, ZIP)
Task planning · Translation · Math · Research & synthesis"""

IMAGE_TRIGGERS  = ["generate","create","draw","make","paint","design","show me","illustrate","render","image of","photo of","picture of","art of","logo","sketch","portrait","wallpaper","thumbnail","banner","icon","avatar"]
IMAGE_NOUNS     = ["image","photo","picture","illustration","artwork","drawing","painting","portrait","wallpaper","logo","icon","art","meme","banner","thumbnail","poster","avatar","background","graphic"]
SEARCH_TRIGGERS = ["today","latest","current","news","weather","price","cost","score","stock","who won","right now","2024","2025","2026","recently","this week","last week","search","find","look up","what happened","breaking","trending","update","live"]

class RateLimiter:
    def __init__(self):
        self._log: dict[str,list[float]] = defaultdict(list)
    def ok(self, k:str) -> bool:
        now=time.time(); self._log[k]=[t for t in self._log[k] if now-t<RATE_WINDOW]
        if len(self._log[k])>=RATE_LIMIT: return False
        self._log[k].append(now); return True
    def wait(self, k:str) -> float:
        return max(0, RATE_WINDOW-(time.time()-self._log[k][0])) if self._log[k] else 0

class ModelService:
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.ready = False
        self._ts   = None
        self._rl   = RateLimiter()

    def set_tool_service(self, ts): self._ts = ts

    async def load(self):
        self.client = httpx.AsyncClient(timeout=60.0)
        self.ready  = True
        p = []
        if GEMINI_KEY:     p.append("Gemini")
        if OPENROUTER_KEY: p.append(f"OpenRouter({PRIMARY_MODEL or 'auto'})")
        if GROQ_KEY:       p.append(f"Groq({GROQ_MODEL})")
        print(f"ModelService ready | {', '.join(p) or 'NO PROVIDERS'}")

    async def close(self):
        if self.client: await self.client.aclose()

    def _wants_image(self, t:str) -> bool:
        t=t.lower(); return any(w in t for w in IMAGE_TRIGGERS) and any(w in t for w in IMAGE_NOUNS)
    def _wants_search(self, t:str) -> bool:
        return any(w in t.lower() for w in SEARCH_TRIGGERS)
    def _trim(self, msgs:list, n=14, mc=2500) -> list:
        return [{"role":m["role"],"content":str(m["content"])[:mc]} for m in msgs[-n:]]
    def _img_url(self, p:str) -> str:
        return f"https://image.pollinations.ai/prompt/{urllib.parse.quote(p)}?width=1024&height=1024&model=flux&nologo=true&enhance=true"

    async def _gemini(self, msgs:list, max_tokens:int) -> str:
        sys=[m["content"] for m in msgs if m["role"]=="system"]
        st = sys[0] if sys else ""
        body=[m for m in msgs if m["role"]!="system"]
        contents=[]
        for i,m in enumerate(body):
            role="user" if m["role"]=="user" else "model"
            txt=(f"[Instructions]: {st}\n\n"+m["content"]) if i==0 and role=="user" and st else m["content"]
            contents.append({"role":role,"parts":[{"text":txt}]})
        if not contents or contents[0]["role"]!="user":
            contents.insert(0,{"role":"user","parts":[{"text":st or "Hello"}]})
        merged=[]
        for t in contents:
            if merged and merged[-1]["role"]==t["role"]: merged[-1]["parts"][0]["text"]+="\n"+t["parts"][0]["text"]
            else: merged.append(t)
        r=await self.client.post(f"{GEMINI_URL}?key={GEMINI_KEY}",
            json={"contents":merged,"generationConfig":{"maxOutputTokens":max_tokens,"temperature":0.7}})
        if r.status_code!=200: raise RuntimeError(f"Gemini {r.status_code}: {r.text[:200]}")
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    async def _openrouter(self, msgs:list, model:str, max_tokens:int) -> str:
        r=await self.client.post(OPENROUTER_URL,
            json={"model":model,"messages":msgs,"max_tokens":max_tokens,"temperature":0.7},
            headers={"Authorization":f"Bearer {OPENROUTER_KEY}","Content-Type":"application/json","HTTP-Referer":"https://retrai.app","X-Title":"Retrai"})
        if r.status_code!=200: raise RuntimeError(f"OpenRouter[{model}] {r.status_code}: {r.text[:200]}")
        return (r.json()["choices"][0]["message"]["content"] or "").strip()

    async def _groq(self, msgs:list, max_tokens:int) -> str:
        r=await self.client.post(GROQ_URL,
            json={"model":GROQ_MODEL,"messages":msgs,"max_tokens":min(max_tokens,4096),"temperature":0.7},
            headers={"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"})
        if r.status_code!=200: raise RuntimeError(f"Groq {r.status_code}: {r.text[:200]}")
        return (r.json()["choices"][0]["message"]["content"] or "").strip()

    async def _llm(self, msgs:list, max_tokens:int) -> str:
        last=None
        if GEMINI_KEY:
            try: return await self._gemini(msgs, max_tokens)
            except Exception as e: last=e; print(f"Gemini fail: {e}")
        if OPENROUTER_KEY:
            for m in (([PRIMARY_MODEL] if PRIMARY_MODEL else [])+[x for x in OR_FREE if x!=PRIMARY_MODEL]):
                try: return await self._openrouter(msgs, m, max_tokens)
                except Exception as e: last=e; print(f"OR[{m}] fail: {e}")
        if GROQ_KEY:
            try: return await self._groq(msgs, max_tokens)
            except Exception as e: last=e; print(f"Groq fail: {e}")
        raise RuntimeError(f"All providers failed. Last: {last}")

    def _extract_tool(self, resp:str):
        m=re.search(r"TOOL:\s*(\w+)\s*\|\s*PARAMS:\s*(\{.*?\})",resp,re.DOTALL)
        if not m: return None,None
        try: return m.group(1), json.loads(m.group(2))
        except: return m.group(1), {}

    async def _agent(self, msgs:list, max_tokens:int, steps=5) -> str:
        working=list(msgs)
        for _ in range(steps):
            resp=await self._llm(working, max_tokens)
            if "TOOL:" in resp and self._ts:
                tool,params=self._extract_tool(resp)
                if tool:
                    try:
                        res=await self._ts.run_tool(tool, params or {})
                        result=json.dumps(res.get("result",res), ensure_ascii=False)
                        working+=[{"role":"assistant","content":resp},{"role":"user","content":f"TOOL_RESULT: {result}\n\nNow give your final answer based on this."}]
                        continue
                    except Exception as e: print(f"Tool err: {e}")
            return resp
        return resp

    async def generate(self, msgs:list, max_tokens=1024, image_b64=None, user_id="guest") -> str:
        if not self.ready: raise RuntimeError("Model not loaded")
        if not self._rl.ok(user_id): raise RuntimeError(f"Rate limit. Retry in {self._rl.wait(user_id):.0f}s.")
        trimmed=self._trim(msgs)
        last=trimmed[-1]["content"] if trimmed else ""
        if self._wants_image(last) and not any(t in last.lower() for t in ["code","script","html","css","function"]):
            return f"IMAGE:{self._img_url(last)}|PROMPT:{last}"
        if self._wants_search(last) and self._ts:
            try:
                res=await self._ts.run_tool("web_search",{"query":last})
                items=res.get("result",[])
                if isinstance(items,list) and items:
                    snip="\n".join(f"[{i+1}] {r.get('title','')}: {r.get('snippet','')}" for i,r in enumerate(items[:5]))
                    trimmed[-1]["content"]=f"{last}\n\n[SEARCH RESULTS]\n{snip}\n[/SEARCH RESULTS]\nAnswer using these results."
            except Exception as e: print(f"Search inject: {e}")
        full=[{"role":"system","content":SYSTEM_PROMPT}]+trimmed
        resp=await self._agent(full, max_tokens)
        if resp.startswith("IMAGE_GEN:"):
            p=resp[10:].strip(); return f"IMAGE:{self._img_url(p)}|PROMPT:{p}"
        if resp.startswith("FILE_GEN:"): return resp
        return resp

    async def generate_stream(self, msgs:list, user_id="guest") -> AsyncGenerator[str, None]:
        try:
            full=await self.generate(msgs, max_tokens=1024, user_id=user_id)
            words=full.split(" ")
            for i,w in enumerate(words):
                chunk=w+(" " if i<len(words)-1 else "")
                yield f"data: {json.dumps({'content':chunk,'done':False})}\n\n"
                await asyncio.sleep(0.012)
            yield f"data: {json.dumps({'content':'','done':True,'full':full})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'content':f'Error: {e}','done':True})}\n\n"
            yield "data: [DONE]\n\n"
