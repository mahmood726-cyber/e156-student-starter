"""Persistent conversational REPL — Claude-Code-style, but for paper writing.

`student chat` drops the student into a single AI session that remembers
what they said earlier in the conversation. Each turn is sent with the
accumulated history so follow-ups like 'rewrite that in plainer English'
actually refer to the previous answer.

The REPL is intentionally tiny — one file, stdlib-only, no prompt-toolkit
dep. First-year students on shared lab machines can't `pip install` freely.

Design notes:
- History grows in-memory; flushed on exit. Not persisted by default.
  A student can copy/paste the final transcript — simpler than shipping
  a history file they'd then have to manage.
- Each call goes through ai.ai_call.ask(), so routing (Ollama local vs.
  Gemini cloud vs. GitHub Models) is honored. No separate cloud setup.
- Context is passed by prepending previous turns to the prompt. This
  works for ~50 turns on Gemini's 1M context; we truncate older turns
  beyond a char budget so we don't suddenly blow token limits.
- Errors (network, consent, rate limit) print inline and the REPL keeps
  going. Ctrl+C in the middle of a reply just cancels that turn.
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai.ai_call import Response


# Keep the character budget generous — Gemini 1.5 Flash has 1M tokens ≈ 4M
# chars. 200K chars leaves plenty of headroom and still truncates rogue
# pastes (e.g. a student pasting a whole PDF into the chat).
_HISTORY_CHAR_BUDGET = 200_000

_BANNER = """\
student chat — ask anything about writing your E156 paper.
(Ctrl+D or type 'exit' to quit. 'clear' drops history.)
"""


def _build_prompt(history: list[tuple[str, str]], user_msg: str) -> str:
    """Flatten (user, assistant) pairs into a single prompt the router accepts.

    We keep the newest turns and drop the oldest when we blow the budget.
    """
    lines = [
        "You are a writing assistant for E156 papers: 7 sentences, ≤156 words, "
        "one primary estimand, no citations in the body. Answer the user's "
        "latest message. If the user asks you to rewrite something, use the "
        "prior assistant turn as the source.",
        "",
    ]
    # Render newest-first, then reverse so the model sees chronological order
    # but we can truncate from the front (oldest).
    rendered: list[str] = []
    for u, a in reversed(history):
        rendered.append(f"USER: {u}")
        rendered.append(f"ASSISTANT: {a}")
    rendered.reverse()
    rendered.append(f"USER: {user_msg}")
    rendered.append("ASSISTANT:")

    body = "\n".join(rendered)
    while len(body) > _HISTORY_CHAR_BUDGET and history:
        # Drop the oldest pair and re-render.
        history.pop(0)
        rendered = []
        for u, a in history:
            rendered.append(f"USER: {u}")
            rendered.append(f"ASSISTANT: {a}")
        rendered.append(f"USER: {user_msg}")
        rendered.append("ASSISTANT:")
        body = "\n".join(rendered)

    return "\n".join(lines) + body


def _one_turn(
    user_msg: str,
    history: list[tuple[str, str]],
    ask_fn,        # callable(kind, prompt) -> Response, injectable for tests
    stderr=None,   # injectable for tests
) -> "Response | None":
    """Single turn — returns Response or None on failure.

    Factored out so tests can exercise the build-prompt + call + history-append
    path without a real AI backend.
    """
    if stderr is None:
        stderr = sys.stderr
    prompt = _build_prompt(history, user_msg)
    try:
        return ask_fn("prose", prompt)
    except Exception as exc:  # noqa: BLE001 — deliberate; we don't want a REPL to die on one error
        stderr.write(f"  (error: {exc})\n")
        stderr.flush()
        return None


def run(
    ask_fn=None,           # injectable for tests
    stdin=None,
    stdout=None,
    stderr=None,
    print_banner: bool = True,
) -> int:
    """Main REPL loop. Returns 0 on clean exit."""
    if ask_fn is None:
        from ai.ai_call import ask as _real_ask
        ask_fn = _real_ask
    if stdin is None:
        stdin = sys.stdin
    if stdout is None:
        stdout = sys.stdout
    if stderr is None:
        stderr = sys.stderr

    if print_banner:
        stdout.write(_BANNER)
        stdout.flush()

    history: list[tuple[str, str]] = []
    while True:
        stdout.write("\n> ")
        stdout.flush()
        try:
            line = stdin.readline()
        except KeyboardInterrupt:
            stdout.write("\n")
            return 0
        if line == "":
            # EOF (Ctrl+D / Ctrl+Z+Enter on Windows)
            stdout.write("\n")
            return 0
        msg = line.strip()
        if msg == "":
            continue
        if msg in ("exit", "quit", ".exit", ".quit"):
            return 0
        if msg == "clear":
            history.clear()
            stdout.write("  (history cleared)\n")
            continue

        resp = _one_turn(msg, history, ask_fn, stderr=stderr)
        if resp is None:
            continue
        stdout.write("\n")
        stdout.write(resp.text.rstrip() + "\n")
        history.append((msg, resp.text))


if __name__ == "__main__":
    sys.exit(run())
