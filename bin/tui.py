"""TUI menu for e156-student-starter.

Uses curses when available (including windows-curses on Windows). Falls back
to a plain numbered list + input() when curses is unavailable or when
E156_FORCE_CURSES_FAIL=1 (used by tests + students on locked-down labs).
"""
from __future__ import annotations

import os
import sys
from typing import Callable, NamedTuple


class Action(NamedTuple):
    label: str
    subcommand: str  # what `student ...` would be typed


MENU: list[Action] = [
    Action("Start a new paper",              "new"),
    Action("Check my paper (validate)",      "validate"),
    Action("Ask the AI to help me",          "ai"),
    Action("Download data for my analysis",  "data pull"),
    Action("Get unstuck / send diagnostics", "doctor"),
    Action("Quit",                           ""),
]


def _fallback_menu() -> int:
    """Plain-text menu; used when curses unavailable."""
    while True:
        print("\nWhat would you like to do?\n")
        for i, a in enumerate(MENU, start=1):
            print(f"  [{i}] {a.label}")
        print()
        choice = input("Type a number (or q to quit): ").strip().lower()
        if choice in ("q", "quit", ""):
            return 0
        if not choice.isdigit():
            print("Please type a number from the list.")
            continue
        idx = int(choice) - 1
        if not (0 <= idx < len(MENU)):
            print("That number isn't on the list.")
            continue
        action = MENU[idx]
        if action.label == "Quit":
            return 0
        print(f"\n\u2192 Equivalent command: student {action.subcommand}")
        print("  (Copy that command to skip this menu next time.)\n")
        return _dispatch(action.subcommand)


def _dispatch(subcommand: str) -> int:
    from bin.student import main as cli_main  # noqa: WPS433
    return cli_main(subcommand.split())


def _curses_menu() -> int:
    import curses

    def _inner(stdscr):
        curses.curs_set(0)
        selected = 0
        while True:
            stdscr.clear()
            stdscr.addstr(1, 2, "e156 \u2014 what would you like to do?", curses.A_BOLD)
            for i, a in enumerate(MENU):
                mark = "\u25B8" if i == selected else " "
                attr = curses.A_REVERSE if i == selected else curses.A_NORMAL
                stdscr.addstr(3 + i, 4, f"{mark} {a.label}", attr)
            stdscr.addstr(4 + len(MENU), 2,
                          "Arrows + Enter. Press 'c' to copy command. 'q' to quit.",
                          curses.A_DIM)
            stdscr.refresh()
            key = stdscr.getch()
            if key in (curses.KEY_UP, ord("k")):
                selected = (selected - 1) % len(MENU)
            elif key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % len(MENU)
            elif key in (curses.KEY_ENTER, 10, 13):
                return selected
            elif key in (ord("q"), 27):  # 27 = Esc
                return len(MENU) - 1  # "Quit"
            elif key == ord("c"):
                _copy_cli_to_clipboard(MENU[selected].subcommand)

    idx = curses.wrapper(_inner)
    chosen = MENU[idx]
    if chosen.label == "Quit":
        return 0
    print(f"\u2192 Equivalent command: student {chosen.subcommand}")
    return _dispatch(chosen.subcommand)


def _copy_cli_to_clipboard(subcommand: str) -> None:
    import subprocess
    cmd = f"student {subcommand}".strip()
    try:
        subprocess.run(["clip.exe"], input=cmd, text=True, check=False, timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        pass


def run() -> int:
    if os.environ.get("E156_FORCE_CURSES_FAIL") == "1":
        return _fallback_menu()
    try:
        import curses  # noqa: F401
    except ImportError:
        return _fallback_menu()
    try:
        return _curses_menu()
    except Exception:
        return _fallback_menu()
