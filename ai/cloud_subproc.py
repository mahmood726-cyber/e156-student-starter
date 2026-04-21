"""Out-of-process cloud-AI invocation.

Why this exists: when ai_call.py imported GITHUB_TOKEN / GEMINI_API_KEY as
module-level constants, ANY other code loaded into the same Python runtime
could read them via `from ai.ai_call import GITHUB_TOKEN`. That is a
secrets-isolation defect (S-P0-4 in v0.3.2 review).

This script runs as a child process. Parent passes the credential via env
for the child only; parent never holds the credential in a module constant
that other in-process code can import. The child reads it once, makes the
HTTP call, and exits.

Protocol:
    stdin  (one line of JSON): {"provider": "github"|"gemini",
                                "model":    str,
                                "prompt":   str,
                                "endpoint": str (optional override)}
    stdout (one line of JSON): {"ok": true,  "text": str}
                            or {"ok": false, "error": str}

Exit code: always 0 on protocol success (parse stdout for ok/error).
Non-zero exit means the child crashed (parent treats as transport failure).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


_GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com/chat/completions"
_GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"


def _call_github(model: str, prompt: str, endpoint: str) -> str:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not present in subprocess env")
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(
        endpoint or _GITHUB_MODELS_ENDPOINT,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read())
    return payload["choices"][0]["message"]["content"]


def _call_gemini(model: str, prompt: str, endpoint: str) -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not present in subprocess env")
    base = endpoint or _GEMINI_ENDPOINT
    url = f"{base}/{model}:generateContent?key={key}"
    data = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}]
    }).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read())
    return payload["candidates"][0]["content"]["parts"][0]["text"]


def main() -> int:
    raw = sys.stdin.read()
    try:
        req = json.loads(raw)
        provider = req["provider"]
        model = req["model"]
        prompt = req["prompt"]
        endpoint = req.get("endpoint", "")
    except (json.JSONDecodeError, KeyError) as e:
        sys.stdout.write(json.dumps({"ok": False, "error": f"bad request: {e}"}))
        return 0

    try:
        if provider == "github":
            text = _call_github(model, prompt, endpoint)
        elif provider == "gemini":
            text = _call_gemini(model, prompt, endpoint)
        else:
            sys.stdout.write(json.dumps({"ok": False, "error": f"unknown provider: {provider!r}"}))
            return 0
    except urllib.error.HTTPError as e:
        sys.stdout.write(json.dumps({"ok": False, "error": f"HTTP {e.code}: {e.reason}"}))
        return 0
    except Exception as e:
        sys.stdout.write(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        return 0

    sys.stdout.write(json.dumps({"ok": True, "text": text}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
