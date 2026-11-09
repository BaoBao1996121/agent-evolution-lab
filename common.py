"""Explicit API configuration for the public lab; no local secret-file discovery.

Offline verification imports no API package and makes no model calls.
Online runs use only the endpoint and model names explicitly provided by the reader.
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

SOLVER_MODEL = os.environ.get("RSI_SOLVER_MODEL", "")
EDITOR_MODEL = os.environ.get("RSI_EDITOR_MODEL", "")
USAGE = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
_client = None
_client_lock = Lock()
_usage_lock = Lock()


def validate_config(require_solver: bool = False) -> None:
    names = ["RSI_API_KEY", "RSI_BASE_URL", "RSI_EDITOR_MODEL"]
    if require_solver:
        names.append("RSI_SOLVER_MODEL")
    missing = [name for name in names if not os.environ.get(name, "").strip()]
    if missing:
        raise SystemExit("Missing explicit settings: " + ", ".join(missing))
    parsed = urlsplit(os.environ["RSI_BASE_URL"])
    if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SystemExit("RSI_BASE_URL must be an HTTP(S) API base URL without embedded credentials, query or fragment")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Use HTTPS for non-local API endpoints")


def client():
    global _client
    with _client_lock:
        if _client is None:
            validate_config()
            from openai import OpenAI
            _client = OpenAI(api_key=os.environ["RSI_API_KEY"],
                             base_url=os.environ["RSI_BASE_URL"],
                             timeout=120, max_retries=0)
    return _client


def chat(model: str, messages: list[dict], temperature: float = 0.7,
         max_tokens: int = 1024, retries: int = 3) -> str:
    api = client()
    if not model:
        raise SystemExit("Set the solver/editor model explicitly before running")
    extra = {"enable_thinking": False} if os.environ.get("RSI_DISABLE_THINKING") == "1" else {}
    last_err = None
    for attempt in range(retries):
        try:
            resp = api.chat.completions.create(
                model=model, messages=messages, temperature=temperature,
                max_tokens=max_tokens, extra_body=extra,
            )
            with _usage_lock:
                USAGE["calls"] += 1
                if resp.usage:
                    USAGE["prompt_tokens"] += resp.usage.prompt_tokens or 0
                    USAGE["completion_tokens"] += resp.usage.completion_tokens or 0
            return resp.choices[0].message.content or ""
        except Exception as exc:
            last_err = exc
            if attempt + 1 < retries:
                time.sleep(2 * (attempt + 1))
    return f"[CALL_FAILED] {type(last_err).__name__}"


def pmap(fn, items, workers: int = 8):
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, items))


def append_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
