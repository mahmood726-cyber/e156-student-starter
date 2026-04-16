"""Task-typed AI router for the E156 student starter.

Design goals:
  1. **Students shouldn't think about which model to call.** They ask for
     `prose`, `code`, `stats`, `review`, or `quick` and the router picks.
  2. **Local-first.** Ollama models (Gemma 2 9B for prose, Qwen 2.5 Coder
     7B for code) are the default. Cloud is a fallback, not a dependency.
  3. **Graceful degrade.** If Ollama isn't running, fall back to
     GitHub Models (if GITHUB_TOKEN is set). If that's not set either,
     fall back to Gemini free tier (if GEMINI_API_KEY is set). If none
     of those work, exit with a specific message telling the student
     which backend to set up.
  4. **Zero-dependency-on-the-hot-path.** The core runs on `urllib` +
     stdlib only — no pip installs required. Students on 8GB machines
     with intermittent internet shouldn't be forced to run `pip install`
     to read a paper.

Usage from the CLI:
    python ai_call.py prose "Rewrite this 156-word abstract in plainer language: ..."
    python ai_call.py code  "Fix this pandas .iloc[0] on potentially empty df: ..."
    python ai_call.py review "Critique this 7-sentence E156 body for methods-accuracy: ..."

Or from another Python file:
    from ai_call import ask
    rewrite = ask("prose", "Rewrite this abstract: ...")

Env vars the router reads:
    OLLAMA_HOST        default http://127.0.0.1:11434
    GITHUB_TOKEN       if set, GitHub Models becomes an available backend
    GEMINI_API_KEY     if set, Gemini 1.5 Flash becomes an available backend
    E156_AI_PREFER     override the router: "gemma" / "qwen" / "github" / "gemini"
    E156_AI_DEBUG      set to 1 to print which backend was used + latency

The router intentionally makes NO cloud call unless local fails — no
surprise bills, no surprise data egress, no surprise throttling.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PREFER = os.environ.get("E156_AI_PREFER", "").strip().lower()
DEBUG = os.environ.get("E156_AI_DEBUG", "") == "1"


# --- Model choices ---------------------------------------------------------
#
# Local Ollama tags — these match what the bootstrap installer pulls.
# If a student wants to test the 8GB-laptop path, `bootstrap.ps1 --low-ram`
# pulls gemma2:2b + qwen2.5-coder:1.5b instead and this file works
# unchanged (the env file overrides the tags).
OLLAMA_MODEL_FOR_PROSE = os.environ.get("E156_PROSE_MODEL", "gemma2:9b")
OLLAMA_MODEL_FOR_CODE = os.environ.get("E156_CODE_MODEL", "qwen2.5-coder:7b")
OLLAMA_MODEL_FOR_QUICK = os.environ.get("E156_QUICK_MODEL", "qwen2.5-coder:1.5b")

# GitHub Models free-tier daily quotas (2025): gpt-4o-mini ~150/day,
# llama-3.3-70b ~150/day. Cheaper models first for review tasks.
GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com/chat/completions"
GITHUB_MODEL_FOR_REVIEW = "gpt-4o-mini"

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL_FOR_REVIEW = "gemini-1.5-flash-latest"


# --- Code-signal detector --------------------------------------------------
#
# Even when a student asks for `prose`, if the prompt is obviously code
# (traceback, backticks, def/class) we route to the coder model. This
# avoids a common failure mode: asking Gemma to "explain" a traceback
# where Qwen Coder is clearly the better tool.
_CODE_SIGNALS = (
    "```python", "```py", "```bash", "```sh",
    "Traceback (most recent call last)",
    "def ", "class ", "import ",
    "error:", "Error:", "File \"",
)


def _looks_like_code(prompt: str) -> bool:
    head = prompt[:2000]
    return any(sig in head for sig in _CODE_SIGNALS)


# --- Backend availability --------------------------------------------------


def _ollama_up(timeout: float = 1.0) -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def _github_models_up() -> bool:
    return bool(GITHUB_TOKEN)


def _gemini_up() -> bool:
    return bool(GEMINI_API_KEY)


# --- Router ----------------------------------------------------------------


@dataclass
class Response:
    text: str
    backend: str
    model: str
    elapsed_ms: int


def _route(task_kind: str, prompt: str) -> tuple[str, str]:
    """Return (backend, model) given the task kind + prompt content.

    The four rules, in order:
      1. Explicit student preference (E156_AI_PREFER env) wins.
      2. Code signals in the prompt → coder model regardless of kind.
      3. `review` or very long prompts → cloud if available (reviews need
         nuance + big context; Gemma 9B's 8K context is limiting).
      4. Default: Gemma for prose, Qwen for code, Qwen-1.5B for quick.
    """
    if PREFER == "gemma":
        return "ollama", OLLAMA_MODEL_FOR_PROSE
    if PREFER == "qwen":
        return "ollama", OLLAMA_MODEL_FOR_CODE
    if PREFER == "github" and _github_models_up():
        return "github", GITHUB_MODEL_FOR_REVIEW
    if PREFER == "gemini" and _gemini_up():
        return "gemini", GEMINI_MODEL_FOR_REVIEW

    # Code always goes to Qwen (unless local is down — handled in _call).
    if task_kind == "code" or _looks_like_code(prompt):
        return "ollama", OLLAMA_MODEL_FOR_CODE

    # Multi-persona review → cloud if available, else Gemma local (degraded).
    if task_kind == "review" or len(prompt) > 8_000:
        if _github_models_up():
            return "github", GITHUB_MODEL_FOR_REVIEW
        if _gemini_up():
            return "gemini", GEMINI_MODEL_FOR_REVIEW
        return "ollama", OLLAMA_MODEL_FOR_PROSE

    # quick → tiny fast model (1.5B)
    if task_kind == "quick":
        return "ollama", OLLAMA_MODEL_FOR_QUICK

    # default: prose → Gemma
    return "ollama", OLLAMA_MODEL_FOR_PROSE


# --- Backend calls ---------------------------------------------------------


def _call_ollama(model: str, prompt: str) -> str:
    url = f"{OLLAMA_HOST}/api/generate"
    data = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())["response"]


def _call_github_models(model: str, prompt: str) -> str:
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(
        GITHUB_MODELS_ENDPOINT,
        data=data,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read())
    return payload["choices"][0]["message"]["content"]


def _call_gemini(model: str, prompt: str) -> str:
    url = f"{GEMINI_ENDPOINT}/{model}:generateContent?key={GEMINI_API_KEY}"
    data = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}]
    }).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read())
    return payload["candidates"][0]["content"]["parts"][0]["text"]


# --- Public entrypoint -----------------------------------------------------


def ask(task_kind: str, prompt: str) -> Response:
    """Send `prompt` to whichever backend suits `task_kind` best.

    `task_kind` is one of: prose | code | stats | review | quick.
    (stats is currently routed the same as prose — kept as a separate
    label so we can redirect it later without touching call sites.)

    Falls back through backends if the preferred one is unavailable.
    Raises RuntimeError ONLY if every available backend has been tried
    and none answered — the message lists exactly which env vars to set.
    """
    if task_kind not in {"prose", "code", "stats", "review", "quick"}:
        raise ValueError(
            f"task_kind must be prose|code|stats|review|quick, got {task_kind!r}"
        )

    attempts: list[tuple[str, str]] = []
    backend, model = _route(task_kind, prompt)
    attempts.append((backend, model))

    # Fallback chain if the primary is down.
    if backend == "ollama" and not _ollama_up():
        if _github_models_up():
            attempts.append(("github", GITHUB_MODEL_FOR_REVIEW))
        if _gemini_up():
            attempts.append(("gemini", GEMINI_MODEL_FOR_REVIEW))
    elif backend == "github" and not _github_models_up():
        if _ollama_up():
            attempts.append(("ollama", OLLAMA_MODEL_FOR_PROSE))
        if _gemini_up():
            attempts.append(("gemini", GEMINI_MODEL_FOR_REVIEW))
    elif backend == "gemini" and not _gemini_up():
        if _ollama_up():
            attempts.append(("ollama", OLLAMA_MODEL_FOR_PROSE))

    last_err: Exception | None = None
    for b, m in attempts:
        start = time.time()
        try:
            if b == "ollama":
                if not _ollama_up():
                    raise RuntimeError(f"Ollama not reachable at {OLLAMA_HOST}")
                text = _call_ollama(m, prompt)
            elif b == "github":
                if not GITHUB_TOKEN:
                    raise RuntimeError("GITHUB_TOKEN not set")
                text = _call_github_models(m, prompt)
            elif b == "gemini":
                if not GEMINI_API_KEY:
                    raise RuntimeError("GEMINI_API_KEY not set")
                text = _call_gemini(m, prompt)
            else:
                raise RuntimeError(f"unknown backend {b!r}")
            elapsed = int((time.time() - start) * 1000)
            if DEBUG:
                print(f"[ai_call] backend={b} model={m} took={elapsed}ms", file=sys.stderr)
            return Response(text=text, backend=b, model=m, elapsed_ms=elapsed)
        except Exception as e:
            last_err = e
            if DEBUG:
                print(f"[ai_call] backend={b} FAILED: {e}", file=sys.stderr)
            continue

    raise RuntimeError(
        "All available AI backends failed. Tried: "
        + ", ".join(f"{b}/{m}" for b, m in attempts)
        + f". Last error: {last_err}. "
        "Set up at least one of: (a) ollama serve + pull gemma2:9b, "
        "(b) GITHUB_TOKEN with Copilot-for-Students, "
        "(c) GEMINI_API_KEY from https://aistudio.google.com/."
    )


# --- CLI entrypoint --------------------------------------------------------


def _cli() -> int:
    if len(sys.argv) < 3:
        print(
            "Usage: python ai_call.py <kind> <prompt>\n"
            "  kind: prose | code | stats | review | quick\n"
            "  prompt: anything (quote if it has spaces)\n"
            "Example:\n"
            "  python ai_call.py prose 'Rewrite this abstract in plainer English: ...'\n"
            "Env:\n"
            "  E156_AI_PREFER=gemma|qwen|github|gemini   force a backend\n"
            "  E156_AI_DEBUG=1                            print backend+latency to stderr",
            file=sys.stderr,
        )
        return 2
    task_kind = sys.argv[1]
    prompt = " ".join(sys.argv[2:])
    try:
        r = ask(task_kind, prompt)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(r.text)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
