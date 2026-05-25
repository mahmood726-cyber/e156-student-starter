"""Task-typed AI router for the E156 student starter.

Design goals:
  1. Students should not need to pick a model manually.
  2. Local Ollama is the default path.
  3. Cloud fallback is isolated to a subprocess and gated by consent.
  4. The hot path stays stdlib-only.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# Local Ollama tags. The installer can override these through the env file.
OLLAMA_MODEL_FOR_PROSE = os.environ.get("E156_PROSE_MODEL", "gemma2:9b")
OLLAMA_MODEL_FOR_CODE = os.environ.get("E156_CODE_MODEL", "qwen2.5-coder:7b")
OLLAMA_MODEL_FOR_QUICK = os.environ.get("E156_QUICK_MODEL", "qwen2.5-coder:1.5b")

GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com/chat/completions"
GITHUB_MODEL_FOR_REVIEW = "gpt-4o-mini"

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL_FOR_REVIEW = "gemini-1.5-flash-latest"

_CLOUD_SUBPROC = Path(__file__).with_name("cloud_subproc.py")
_CLOUD_BACKENDS = frozenset({"github", "gemini"})
_PUBLIC_TASK_KINDS = frozenset({"prose", "code", "stats", "review", "quick"})
_PATIENT_SENSITIVE_KINDS = frozenset({"patient", "ipd", "dossier", "raw_case"})
_ALLOWED_TASK_KINDS = _PUBLIC_TASK_KINDS | _PATIENT_SENSITIVE_KINDS

_CODE_SIGNALS = (
    "```python",
    "```py",
    "```bash",
    "```sh",
    "Traceback (most recent call last)",
    "def ",
    "class ",
    "import ",
    "error:",
    "Error:",
    'File "',
)


class ConsentRequiredError(RuntimeError):
    """Raised when a cloud model would be used without consent."""


@dataclass
class Response:
    text: str
    backend: str
    model: str
    elapsed_ms: int


def _debug_enabled() -> bool:
    return os.environ.get("E156_AI_DEBUG", "") == "1"


def _prefer_backend() -> str:
    return os.environ.get("E156_AI_PREFER", "").strip().lower()


def _github_token() -> str:
    return os.environ.get("GITHUB_TOKEN", "")


def _gemini_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "")


def _consent_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(local_app_data) / "e156" / ".consent.json"


def _cloud_consent_given() -> bool:
    path = _consent_path()
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(payload.get("cloud_enabled", False))


def _ensure_cloud_allowed(task_kind: str) -> None:
    if task_kind in _PATIENT_SENSITIVE_KINDS:
        raise ConsentRequiredError("cloud_enabled=false")
    if not _cloud_consent_given():
        raise ConsentRequiredError("cloud_enabled=false")


def _looks_like_code(prompt: str) -> bool:
    head = prompt[:2000]
    return any(sig in head for sig in _CODE_SIGNALS)


def _ollama_up(timeout: float = 1.0) -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def _github_models_up(token: str | None = None) -> bool:
    if token is None:
        token = _github_token()
    return bool(token)


def _gemini_up(api_key: str | None = None) -> bool:
    if api_key is None:
        api_key = _gemini_api_key()
    return bool(api_key)


def _route(
    task_kind: str,
    prompt: str,
    *,
    github_available: bool | None = None,
    gemini_available: bool | None = None,
) -> tuple[str, str]:
    """Return (backend, model) for the task kind + prompt content."""
    if github_available is None:
        github_available = _github_models_up()
    if gemini_available is None:
        gemini_available = _gemini_up()

    prefer = _prefer_backend()
    if prefer == "gemma":
        return "ollama", OLLAMA_MODEL_FOR_PROSE
    if prefer == "qwen":
        return "ollama", OLLAMA_MODEL_FOR_CODE
    if prefer == "github" and github_available:
        return "github", GITHUB_MODEL_FOR_REVIEW
    if prefer == "gemini" and gemini_available:
        return "gemini", GEMINI_MODEL_FOR_REVIEW

    if task_kind == "code" or _looks_like_code(prompt):
        return "ollama", OLLAMA_MODEL_FOR_CODE

    if task_kind == "review" or len(prompt) > 8_000:
        if github_available:
            return "github", GITHUB_MODEL_FOR_REVIEW
        if gemini_available:
            return "gemini", GEMINI_MODEL_FOR_REVIEW
        return "ollama", OLLAMA_MODEL_FOR_PROSE

    if task_kind == "quick":
        return "ollama", OLLAMA_MODEL_FOR_QUICK

    return "ollama", OLLAMA_MODEL_FOR_PROSE


def _call_ollama(model: str, prompt: str) -> str:
    url = f"{OLLAMA_HOST}/api/generate"
    data = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())["response"]


def _call_cloud_subprocess(
    provider: str,
    model: str,
    prompt: str,
    *,
    credential_name: str,
    credential_value: str,
    endpoint: str,
) -> str:
    if not credential_value:
        raise RuntimeError(f"{credential_name} not set")
    if not _CLOUD_SUBPROC.is_file():
        raise RuntimeError(f"cloud subprocess missing: {_CLOUD_SUBPROC}")

    child_env = os.environ.copy()
    child_env.pop("GITHUB_TOKEN", None)
    child_env.pop("GEMINI_API_KEY", None)
    child_env[credential_name] = credential_value

    req = {
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "endpoint": endpoint,
    }
    proc = subprocess.run(
        [sys.executable, str(_CLOUD_SUBPROC)],
        input=json.dumps(req),
        capture_output=True,
        text=True,
        timeout=180,
        env=child_env,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or "child process crashed"
        raise RuntimeError(f"cloud subprocess failed: {stderr}")

    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"cloud subprocess returned invalid JSON: {exc}") from exc

    if not payload.get("ok"):
        raise RuntimeError(str(payload.get("error") or "unknown cloud subprocess error"))

    text = payload.get("text")
    if not isinstance(text, str):
        raise RuntimeError("cloud subprocess returned non-string text")
    return text


def _call_github_models(model: str, prompt: str, token: str) -> str:
    return _call_cloud_subprocess(
        "github",
        model,
        prompt,
        credential_name="GITHUB_TOKEN",
        credential_value=token,
        endpoint=GITHUB_MODELS_ENDPOINT,
    )


def _call_gemini(model: str, prompt: str, api_key: str) -> str:
    return _call_cloud_subprocess(
        "gemini",
        model,
        prompt,
        credential_name="GEMINI_API_KEY",
        credential_value=api_key,
        endpoint=GEMINI_ENDPOINT,
    )


def _debug_log(message: str) -> None:
    if _debug_enabled():
        print(message, file=sys.stderr)


def _unique_attempts(attempts: list[tuple[str, str]]) -> list[tuple[str, str]]:
    unique: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for attempt in attempts:
        if attempt in seen:
            continue
        seen.add(attempt)
        unique.append(attempt)
    return unique


def ask(task_kind: str, prompt: str) -> Response:
    """Send ``prompt`` to whichever backend suits ``task_kind`` best."""
    if task_kind not in _ALLOWED_TASK_KINDS:
        allowed = "|".join(sorted(_ALLOWED_TASK_KINDS))
        raise ValueError(f"task_kind must be {allowed}, got {task_kind!r}")

    github_token = _github_token()
    gemini_api_key = _gemini_api_key()

    attempts: list[tuple[str, str]] = []
    backend, model = _route(
        task_kind,
        prompt,
        github_available=bool(github_token),
        gemini_available=bool(gemini_api_key),
    )
    attempts.append((backend, model))

    if backend == "ollama" and not _ollama_up():
        if github_token:
            attempts.append(("github", GITHUB_MODEL_FOR_REVIEW))
        if gemini_api_key:
            attempts.append(("gemini", GEMINI_MODEL_FOR_REVIEW))
    elif backend == "github" and not github_token:
        if _ollama_up():
            attempts.append(("ollama", OLLAMA_MODEL_FOR_PROSE))
        if gemini_api_key:
            attempts.append(("gemini", GEMINI_MODEL_FOR_REVIEW))
    elif backend == "gemini" and not gemini_api_key:
        if _ollama_up():
            attempts.append(("ollama", OLLAMA_MODEL_FOR_PROSE))
        if github_token:
            attempts.append(("github", GITHUB_MODEL_FOR_REVIEW))

    attempts = _unique_attempts(attempts)

    last_err: Exception | None = None
    for chosen_backend, chosen_model in attempts:
        start = time.time()
        try:
            if chosen_backend == "ollama":
                if not _ollama_up():
                    raise RuntimeError(f"Ollama not reachable at {OLLAMA_HOST}")
                text = _call_ollama(chosen_model, prompt)
            elif chosen_backend == "github":
                _ensure_cloud_allowed(task_kind)
                text = _call_github_models(chosen_model, prompt, github_token)
            elif chosen_backend == "gemini":
                _ensure_cloud_allowed(task_kind)
                text = _call_gemini(chosen_model, prompt, gemini_api_key)
            else:
                raise RuntimeError(f"unknown backend {chosen_backend!r}")

            elapsed = int((time.time() - start) * 1000)
            _debug_log(
                f"[ai_call] backend={chosen_backend} model={chosen_model} took={elapsed}ms"
            )
            return Response(
                text=text,
                backend=chosen_backend,
                model=chosen_model,
                elapsed_ms=elapsed,
            )
        except ConsentRequiredError:
            raise
        except Exception as exc:
            last_err = exc
            _debug_log(f"[ai_call] backend={chosen_backend} FAILED: {exc}")
            continue

    tried = ", ".join(f"{b}/{m}" for b, m in attempts) or "<none>"
    raise RuntimeError(
        "All available AI backends failed. Tried: "
        + tried
        + f". Last error: {last_err}. "
        "Set up at least one of: (a) ollama serve + pull gemma2:9b, "
        "(b) GITHUB_TOKEN with Copilot-for-Students, "
        "(c) GEMINI_API_KEY from https://aistudio.google.com/."
    )


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
        response = ask(task_kind, prompt)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(response.text)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
