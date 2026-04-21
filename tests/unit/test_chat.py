"""student chat REPL — exits cleanly, accumulates context, keeps going on errors."""
from __future__ import annotations

import io
from dataclasses import dataclass

from bin.chat import run, _build_prompt, _one_turn


@dataclass
class FakeResp:
    text: str
    backend: str = "fake"
    model: str = "fake"
    elapsed_ms: int = 1


def _fake_ask(seq: list[str]):
    """Return an ask-callable that yields successive canned responses."""
    it = iter(seq)

    def _ask(_kind: str, _prompt: str):
        return FakeResp(text=next(it))

    return _ask


def test_exit_command_ends_session():
    stdin = io.StringIO("exit\n")
    stdout = io.StringIO()
    rc = run(ask_fn=_fake_ask([]), stdin=stdin, stdout=stdout, print_banner=False)
    assert rc == 0
    # No AI call should have happened (we bailed on 'exit')
    assert "ASSISTANT" not in stdout.getvalue()


def test_eof_ends_session():
    stdin = io.StringIO("")  # immediate EOF
    stdout = io.StringIO()
    rc = run(ask_fn=_fake_ask([]), stdin=stdin, stdout=stdout, print_banner=False)
    assert rc == 0


def test_quit_command_ends_session():
    stdin = io.StringIO("quit\n")
    stdout = io.StringIO()
    rc = run(ask_fn=_fake_ask([]), stdin=stdin, stdout=stdout, print_banner=False)
    assert rc == 0


def test_empty_line_is_skipped_not_sent_to_model():
    # Empty line → no call; then 'exit'
    stdin = io.StringIO("\n\n   \nexit\n")
    stdout = io.StringIO()
    calls: list[str] = []

    def _ask(kind: str, prompt: str):
        calls.append(prompt)
        return FakeResp(text="never reached")

    rc = run(ask_fn=_ask, stdin=stdin, stdout=stdout, print_banner=False)
    assert rc == 0
    assert calls == [], "empty input must not call the model"


def test_normal_turn_shows_response():
    stdin = io.StringIO("hello\nexit\n")
    stdout = io.StringIO()
    rc = run(ask_fn=_fake_ask(["hi there"]), stdin=stdin, stdout=stdout, print_banner=False)
    assert rc == 0
    assert "hi there" in stdout.getvalue()


def test_history_accumulates_across_turns():
    captured: list[str] = []

    def _ask(_kind: str, prompt: str):
        captured.append(prompt)
        return FakeResp(text=f"response-{len(captured)}")

    stdin = io.StringIO("first\nsecond\nthird\nexit\n")
    stdout = io.StringIO()
    run(ask_fn=_ask, stdin=stdin, stdout=stdout, print_banner=False)

    # Third call's prompt must mention both prior user lines AND the prior
    # assistant responses — that's the whole point of the REPL.
    assert "USER: first" in captured[2]
    assert "USER: second" in captured[2]
    assert "USER: third" in captured[2]
    assert "response-1" in captured[2]
    assert "response-2" in captured[2]


def test_clear_command_drops_history():
    captured: list[str] = []

    def _ask(_kind: str, prompt: str):
        captured.append(prompt)
        return FakeResp(text=f"r{len(captured)}")

    stdin = io.StringIO("first\nclear\nsecond\nexit\n")
    stdout = io.StringIO()
    run(ask_fn=_ask, stdin=stdin, stdout=stdout, print_banner=False)

    # Two turns happened; after 'clear', second turn must NOT contain 'first'
    assert len(captured) == 2
    assert "USER: first" in captured[0]
    assert "USER: first" not in captured[1], "clear must drop prior history"
    assert "USER: second" in captured[1]


def test_error_in_one_turn_does_not_kill_repl():
    attempts = iter(["boom", "ok-response"])

    def _ask(_kind: str, _prompt: str):
        nxt = next(attempts)
        if nxt == "boom":
            raise RuntimeError("network blip")
        return FakeResp(text=nxt)

    stdin = io.StringIO("first\nsecond\nexit\n")
    stdout = io.StringIO()
    stderr = io.StringIO()
    rc = run(ask_fn=_ask, stdin=stdin, stdout=stdout, stderr=stderr, print_banner=False)
    assert rc == 0
    assert "ok-response" in stdout.getvalue()
    assert "network blip" in stderr.getvalue()


def test_build_prompt_truncates_when_over_budget():
    """A very long history should still produce a prompt under the budget."""
    # 50 turns of 10K chars each = 500K chars of history → must truncate.
    fat = "x" * 10_000
    history = [(fat, fat) for _ in range(50)]
    prompt = _build_prompt(history, "final")
    # _HISTORY_CHAR_BUDGET is 200_000; allow headroom for system prompt.
    assert len(prompt) < 250_000
    assert "USER: final" in prompt
