import os
import json
from typing import List, Dict, Tuple, Optional

from dotenv import load_dotenv
import redis

try:
    import google.generativeai as genai
except Exception:
    genai = None

try:
    from duckduckgo_search import DDGS
except Exception:
    DDGS = None

# Load .env for local runs (in Docker/EC2, envs are injected)
load_dotenv()

HISTORY_LIMIT = 30  # last N turns (user+assistant) to keep in Redis


def get_redis_client():
    host = os.getenv("REDIS_HOST", "redis")
    port = int(os.getenv("REDIS_PORT", "6379"))
    try:
        return redis.Redis(host=host, port=port, decode_responses=True)
    except Exception:
        return None


def load_history(rdb, session_id: str) -> List[Dict[str, str]]:
    if not rdb:
        return []
    key = f"history:{session_id}"
    raw = rdb.get(key)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []


def save_history(rdb, session_id: str, history: List[Dict[str, str]]):
    if not rdb:
        return
    key = f"history:{session_id}"
    trimmed = history[-HISTORY_LIMIT:]
    rdb.set(key, json.dumps(trimmed))


def perform_web_search(query: str, max_results: int = 6) -> List[Dict[str, str]]:
    """DuckDuckGo search. Returns list of {title, href, body}."""
    if not DDGS:
        return []
    results: List[Dict[str, str]] = []
    try:
        with DDGS() as ddgs:
            for result in ddgs.text(query, max_results=max_results):
                if not isinstance(result, dict):
                    continue
                title = result.get("title") or ""
                href = result.get("href") or ""
                body = result.get("body") or ""
                if title and href:
                    results.append({"title": title, "href": href, "body": body})
        return results
    except Exception:
        return []


class GeminiClient:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.enabled = bool(self.api_key) and (genai is not None)

        if self.enabled:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
            except Exception:
                self.enabled = False
                self.model = None
        else:
            self.model = None

    def generate_response(
        self,
        user_input: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[str, List[Dict[str, str]]]:
        """Returns (response_text, updated_history)."""
        history = history or []

        if not self.enabled or not self.model:
            msg = (
                "AI service is not configured. Set GEMINI_API_KEY in your .env (local) "
                "or GitHub Secrets (EC2 deploy), then redeploy."
            )
            new_history = history + [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": msg},
            ]
            return msg, new_history

        text = (user_input or "").strip()
        lower = text.lower()

        # Search trigger
        search_query = None
        if lower.startswith("search:"):
            search_query = text.split(":", 1)[1].strip()
        elif lower.startswith("/search "):
            search_query = text.split(" ", 1)[1].strip()

        # Convert our stored history into Gemini chat history format
        gemini_history = []
        for item in history:
            role = item.get("role")
            content = item.get("content", "")
            if role == "user":
                gemini_history.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                gemini_history.append({"role": "model", "parts": [content]})

        chat = self.model.start_chat(history=gemini_history)

        try:
            if search_query:
                web_results = perform_web_search(search_query, max_results=6)
                if not web_results:
                    resp_text = "I couldn't retrieve web results right now. Please try again."
                else:
                    refs_lines = []
                    for idx, item in enumerate(web_results, start=1):
                        refs_lines.append(
                            f"[{idx}] {item['title']} — {item['href']}\n{item['body']}"
                        )
                    refs_block = "\n\n".join(refs_lines)

                    system_prompt = (
                        "You are an AI research assistant. Use the provided web search results to answer the user query. "
                        "Synthesize concisely, cite sources inline like [1], [2], and include a brief summary."
                    )
                    composed = (
                        f"<system>\n{system_prompt}\n</system>\n"
                        f"<user_query>\n{search_query}\n</user_query>\n"
                        f"<web_results>\n{refs_block}\n</web_results>"
                    )
                    resp = chat.send_message(composed)
                    resp_text = resp.text
            else:
                resp = chat.send_message(text)
                resp_text = resp.text

            new_history = history + [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": resp_text},
            ]
            return resp_text, new_history

        except Exception:
            resp_text = "Sorry — I hit an error while generating a response."
            new_history = history + [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": resp_text},
            ]
            return resp_text, new_history
