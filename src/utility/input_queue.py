# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.6.17
Description: Input queue manager for type-ahead user message queuing during agent busy phases

Revision:
---------
2026.6.17      Yu Huang      1.0      First implementation
2026.6.17      Yu Huang      1.1      Rewrite: prompt_toolkit session for message input
2026.6.17      Yu Huang      1.2      Remove background thread; poll keys in main thread
2026.6.17      Yu Huang      1.3      Hotkey = Enter; same key triggers prompt and submits inside it
2026.6.17      Yu Huang      1.4      Use dedicated PromptSession (create_queue_session) to avoid key-binding side effects
                                      on the main session

Details:
---------
Enter serves double duty:
  - In the spinner: Enter is detected via brief raw-mode poll -> triggers live.stop / collect_input / live.start.
  - Inside the dedicated queue PromptSession: Enter submits, Shift+Tab newline, Esc cancels via event.app.exit.
"""

import threading
import logging

from typing import TYPE_CHECKING
from rich.text import Text
from rich.console import Console
from prompt_toolkit.input import create_input
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.keys import Keys

if TYPE_CHECKING:
    from src.context.agent_context import AgentContext
from src.constants import *

sys_log = logging.getLogger('logger')


def create_queue_session():
    """Create a dedicated PromptSession for queue message input.

    Has its own key bindings (Enter->submit, Shift+Tab->newline, Esc->cancel)
    and is completely independent from the agent's main PromptSession.
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.key_binding import KeyBindings

    kb = KeyBindings()

    @kb.add(Keys.Enter)
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add(Keys.BackTab)
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add(Keys.Escape)
    def _(event):
        event.app.exit(result=None)

    return PromptSession(
        multiline=True,
        key_bindings=kb,
        mouse_support=False,
        show_frame=True,
    )


class InputQueue:
    """Thread-safe input queue - Enter to trigger, Enter to submit."""

    def __init__(self, ctx: "AgentContext", console: Console):
        self.ctx = ctx
        self.console = console
        self._queue: list[str] = []
        self._lock = threading.Lock()
        self._if_active: bool = False
        self._paused: bool = False
        self._input_device = None
        self._queue_session = None  # dedicated PromptSession, set via set_queue_session()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        if self._if_active:
            return
        self._if_active = True
        self._paused = False
        self._input_device = create_input()
        sys_log.debug("InputQueue device opened")

    def stop(self):
        if not self._if_active:
            return
        self._if_active = False
        self._paused = False
        self._close_device()
        sys_log.debug("InputQueue device closed")

    def pause(self):
        if not self._if_active:
            return
        self._paused = True

    def resume(self):
        if not self._if_active:
            return
        self._paused = False

    def is_paused(self) -> bool:
        return self._if_active and self._paused

    def is_active(self) -> bool:
        return self._if_active

    # ------------------------------------------------------------------
    # Key polling (spinner main thread)
    # ------------------------------------------------------------------

    def poll_keys(self) -> list[str]:
        """Brief raw-mode poll, return list of key strings detected."""
        if self._paused or self._input_device is None:
            return []
        dev = self._input_device
        try:
            with dev.raw_mode():
                return [k.key for k in dev.read_keys()]
        except Exception:
            return []

    def check_trigger(self) -> bool:
        """Return True if Enter (hotkey) was pressed since last poll."""
        for key in self.poll_keys():
            if key in (Keys.Enter, Keys.ControlJ, Keys.ControlM):
                return True
        return False

    # ------------------------------------------------------------------
    # Queue session
    # ------------------------------------------------------------------

    def set_queue_session(self, session):
        """Store a dedicated PromptSession for queue input (created in main.py).

        This session has its own key bindings (Enter->submit, Shift+Tab->newline,
        Esc->cancel) and is completely independent from the agent's main PromptSession.
        """
        self._queue_session = session

    def collect_input(self, console: Console) -> str | None:
        """Collect a message using the dedicated queue PromptSession.

        Enter submits, Shift+Tab newline, Esc -> event.app.exit -> returns None.
        """
        if self._queue_session is None:
            return None
        try:
            msg = self._queue_session.prompt(
                ANSI(f"\033[90m{INPUT_QUEUE_PROMPT_PREFIX} {INPUT_QUEUE_FIXED_PREFIX}\033[0m\n"
                     f"{AGENT_CONSOLE_ICON} ")
            )
            if msg is None:
                return None
            msg = msg.strip()
            if msg:
                sys_log.debug(f"InputQueue: collected message ({len(msg)} chars)")
                return msg
            return None
        except (KeyboardInterrupt, EOFError):
            return None

    # ------------------------------------------------------------------
    # Queue operations
    # ------------------------------------------------------------------

    def enqueue(self, msg: str):
        msg = msg.strip()
        if not msg:
            return
        with self._lock:
            self._queue.append(msg)
        sys_log.debug(f"InputQueue: enqueued ({len(msg)} chars)")

    def drain(self) -> list[str]:
        with self._lock:
            msgs = self._queue.copy()
            self._queue.clear()
            return msgs

    def queue_size(self) -> int:
        with self._lock:
            return len(self._queue)

    # ------------------------------------------------------------------
    # Rich renderable
    # ------------------------------------------------------------------

    def render_status(self) -> Text | None:
        qsize = self.queue_size()
        if qsize == 0:
            return None
        text = Text()
        text.append(f"[Queued: {qsize}] ", style=f"bold {INPUT_QUEUE_STATUS_COLOR}")
        text.append(INPUT_QUEUE_HINT, style="bright_black")
        return text

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _close_device(self):
        if self._input_device is not None:
            try:
                self._input_device.close()
            except Exception:
                pass
            self._input_device = None
