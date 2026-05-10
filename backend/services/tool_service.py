"""
tool_service.py — Upgraded
- Pluggable tool registry (register tools at runtime)
- Safe code execution sandbox (restricted builtins, timeout)
- Vector memory search tool (cosine similarity over session embeddings)
- Existing tools preserved and improved
"""

import httpx
import os
import json
import math
import re
import asyncio
from typing import Any, Callable, Awaitable
from datetime import datetime

SERPER_KEY   = os.getenv("SERPER_API_KEY", "")
WEATHER_KEY  = os.getenv("OPENWEATHER_KEY", "")
EXEC_TIMEOUT = float(os.getenv("CODE_EXEC_TIMEOUT", "5"))  # seconds


# ── Simple in-process vector store for semantic memory ───────────────────────

class VectorMemory:
    """
    Lightweight vector memory using TF-IDF-style bag-of-words cosine similarity.
    No external dependencies — works without numpy or sentence-transformers.
    Upgrade to a real embedding model (e.g. sentence-transformers) by replacing _embed().
    """

    def __init__(self):
        self._docs: list[dict] = []  # {"id": str, "text": str, "vec": dict, "meta": dict}

    def _embed(self, text: str) -> dict:
        """Simple word-frequency vector (bag of words, lowercased, stopwords removed)."""
        STOPWORDS = {"the","a","an","is","it","in","on","of","to","and","or","for","with","as","at"}
        words = re.findall(r"\w+", text.lower())
        vec: dict[str, float] = {}
        for w in words:
            if w not in STOPWORDS:
                vec[w] = vec.get(w, 0) + 1
        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {k: v / norm for k, v in vec.items()}

    def _cosine(self, a: dict, b: dict) -> float:
        return sum(a.get(k, 0) * v for k, v in b.items())

    def add(self, doc_id: str, text: str, meta: dict | None = None):
        vec = self._embed(text)
        # Replace if exists
        self._docs = [d for d in self._docs if d["id"] != doc_id]
        self._docs.append({"id": doc_id, "text": text, "vec": vec, "meta": meta or {}})

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        qvec = self._embed(query)
        scored = [
            {"score": self._cosine(qvec, d["vec"]), "id": d["id"],
             "text": d["text"], "meta": d["meta"]}
            for d in self._docs
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return [s for s in scored[:top_k] if s["score"] > 0]

    def delete(self, doc_id: str):
        self._docs = [d for d in self._docs if d["id"] != doc_id]

    def size(self) -> int:
        return len(self._docs)


# Shared vector memory instance
vector_memory = VectorMemory()


# ── Safe code execution ───────────────────────────────────────────────────────

SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
    "chr": chr, "dict": dict, "divmod": divmod, "enumerate": enumerate,
    "filter": filter, "float": float, "format": format, "frozenset": frozenset,
    "hash": hash, "hex": hex, "int": int, "isinstance": isinstance,
    "issubclass": issubclass, "iter": iter, "len": len, "list": list,
    "map": map, "max": max, "min": min, "next": next, "oct": oct,
    "ord": ord, "pow": pow, "print": print, "range": range, "repr": repr,
    "reversed": reversed, "round": round, "set": set, "slice": slice,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "type": type,
    "zip": zip,
}

def _safe_exec(code: str, timeout: float = EXEC_TIMEOUT) -> str:
    """
    Execute Python code in a restricted environment.
    Returns stdout output or the value of the last expression.
    Raises ValueError on timeout or unsafe code.
    """
    import io, contextlib, signal

    # Block obviously dangerous patterns
    BLOCKED = ["import os", "import sys", "import subprocess", "open(",
               "__import__", "eval(", "exec(", "compile(", "globals()", "locals()"]
    for b in BLOCKED:
        if b in code:
            raise ValueError(f"Blocked pattern: '{b}'")

    output = io.StringIO()
    globs = {"__builtins__": SAFE_BUILTINS, "math": math, "json": json, "re": re}

    def _run():
        with contextlib.redirect_stdout(output):
            try:
                tree = compile(code, "<sandbox>", "exec")
                exec(tree, globs)
            except SyntaxError:
                # Try as expression
                try:
                    result = eval(code, globs)
                    if result is not None:
                        print(result)
                except Exception as e:
                    print(f"Error: {e}")
            except Exception as e:
                print(f"Error: {e}")

    # Use threading timeout (signal-based timeout only works on main thread)
    import threading
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise ValueError(f"Code execution timed out after {timeout}s")

    return output.getvalue().strip() or "(no output)"


# ── ToolService ───────────────────────────────────────────────────────────────

ToolFn = Callable[..., Awaitable[Any]]

class ToolService:
    def __init__(self):
        self._tools: dict[str, tuple[ToolFn, str, list[str]]] = {}
        # Register built-in tools
        self._register_builtins()

    def register(self, name: str, fn: ToolFn, description: str, params: list[str]):
        """Register a new tool at runtime."""
        self._tools[name] = (fn, description, params)
        print(f"✓ Tool registered: {name}")

    def _register_builtins(self):
        self.register("web_search",    self.web_search,    "Search the web for current information", ["query"])
        self.register("calculator",    self.calculator,    "Evaluate a math expression",             ["expression"])
        self.register("get_weather",   self.get_weather,   "Get current weather for a city",         ["city"])
        self.register("datetime",      self.get_datetime,  "Get current date and time",              [])
        self.register("execute_code",  self.execute_code,  "Safely run Python code and return output", ["code"])
        self.register("memory_search", self.memory_search, "Search vector memory for relevant context", ["query", "top_k"])
        self.register("memory_store",  self.memory_store,  "Store a text chunk in vector memory",    ["doc_id", "text", "meta"])

    @property
    def available_tools(self) -> dict:
        """Legacy compat: dict of name -> fn."""
        return {name: fn for name, (fn, _, _) in self._tools.items()}

    def get_tool_descriptions(self) -> list[dict]:
        return [
            {"name": name, "description": desc, "params": params}
            for name, (_, desc, params) in self._tools.items()
        ]

    async def run_tool(self, tool_name: str, params: dict) -> dict:
        if tool_name not in self._tools:
            return {"error": f"Tool '{tool_name}' not found. Available: {list(self._tools)}", "success": False}
        fn, _, _ = self._tools[tool_name]
        try:
            result = await fn(**params)
            return {"tool": tool_name, "result": result, "success": True}
        except TypeError as e:
            return {"tool": tool_name, "error": f"Bad params: {e}", "success": False}
        except Exception as e:
            return {"tool": tool_name, "error": str(e), "success": False}

    # ── Built-in tool implementations ─────────────────────────────────────────

    async def web_search(self, query: str) -> Any:
        if not SERPER_KEY:
            return {"message": "Web search not configured. Set SERPER_API_KEY.", "query": query}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": 5},
            )
            r.raise_for_status()
            data = r.json()
            results = [
                {"title": item.get("title"), "snippet": item.get("snippet"), "link": item.get("link")}
                for item in data.get("organic", [])[:5]
            ]
            return results

    async def calculator(self, expression: str) -> Any:
        safe_expr = re.sub(r"[^0-9+\-*/().%^ ]", "", expression).replace("^", "**")
        allowed = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
        try:
            result = eval(safe_expr, {"__builtins__": {}}, allowed)  # noqa: S307
            return {"expression": expression, "result": result}
        except Exception:
            return {"error": f"Could not evaluate: {expression}"}

    async def get_weather(self, city: str) -> Any:
        if not WEATHER_KEY:
            return {"message": "Weather not configured. Set OPENWEATHER_KEY.", "city": city}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": WEATHER_KEY, "units": "metric"},
            )
            r.raise_for_status()
            data = r.json()
            return {
                "city": data["name"],
                "temp_c": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "description": data["weather"][0]["description"],
                "humidity": data["main"]["humidity"],
                "wind_kph": round(data["wind"]["speed"] * 3.6, 1),
            }

    async def get_datetime(self) -> Any:
        now = datetime.now()
        return {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day": now.strftime("%A"),
            "datetime_iso": now.isoformat(),
        }

    async def execute_code(self, code: str) -> Any:
        """Safe Python code execution in a sandboxed environment."""
        try:
            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(None, _safe_exec, code)
            return {"output": output, "code": code}
        except ValueError as e:
            return {"error": str(e), "code": code}
        except Exception as e:
            return {"error": f"Execution error: {e}", "code": code}

    async def memory_search(self, query: str, top_k: int = 3) -> Any:
        """Search the in-process vector memory for relevant chunks."""
        results = vector_memory.search(query, top_k=int(top_k))
        return {
            "query": query,
            "results": results,
            "total_docs": vector_memory.size(),
        }

    async def memory_store(self, doc_id: str, text: str, meta: dict | None = None) -> Any:
        """Store a text chunk in vector memory."""
        vector_memory.add(doc_id, text, meta or {})
        return {"stored": doc_id, "total_docs": vector_memory.size()}


# Singleton — imported by routers/tools.py.
# main.py must import this instance rather than creating a new ToolService().
tool_service = ToolService()
