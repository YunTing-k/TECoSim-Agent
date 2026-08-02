# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.7.31
Description: Busy-phase background input thread for the TECoSim agent

Revision:
---------
2026.7.31      Yu Huang      1.0      First implementation
2026.8.2       Yu Huang      1.1      Separate from AgentContext

Details:
---------
Background input thread active only during busy phases (LLM request / tool execution / streaming). Reads keys in raw mode
(prompt_toolkit create_input + read_keys; non-blocking polling on Windows), maintains the draft (self.draft), and submits
complete messages into the pending queue (self.msg_queue) on Enter. Renders nothing itself: the draft is drawn by the
render layer's insert bar (get_render). Pause/resume provide time mutual exclusion with modal TUIs that take over stdin;
Ctrl+C is interpreted locally (draft non-empty -> clear draft; empty -> forward KeyboardInterrupt to the busy thread
identified by self.busy_thread_ident).
"""
import time
import ctypes
import logging
import threading
import rich.box

from typing import Callable
from datetime import datetime
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from prompt_toolkit.input import create_input, Input
from prompt_toolkit.keys import Keys
from prompt_toolkit.key_binding.key_processor import KeyPress
from src.constants import *

sys_log = logging.getLogger('logger')


class InputThread:
    """Background TUI input thread: raw-mode key reading -> ctx.draft -> Enter -> ctx.msg_queue

    Lifecycle: start()/stop() bound the busy phase; pause()/resume() guard modal TUIs
    that own stdin during the busy phase. The thread only reads stdin and never writes
    stdout -- the draft is rendered by the render layer's footer.
    """
    def __init__(self, key_source: Input | None = None, cancel_handler: Callable[[], None] | None = None):
        self._key_source = key_source  # injectable for tests
        self._input_device: Input | None = None  # lazily created on start()
        self.busy_thread_ident: int | None = None
        self.draft: str = ""
        self.msg_queue: list[str] = []
        self._msg_queue_lock = threading.Lock()
        self._pause_event = threading.Event()  # set = paused (do not read keys)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._cancel_handler = cancel_handler  # injectable for tests

    # [Lifecycle functions for input thread]
    def start(self) -> None:
        """start the input thread (call at the beginning of a busy phase)"""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._pause_event.clear()
        self._input_device = self._key_source if self._key_source is not None else create_input()
        self._thread = threading.Thread(target=self._run, name="InputThread", daemon=True)
        assert self._thread
        self._thread.start()
        sys_log.debug(f"InputThread started")

    def stop(self) -> None:
        """stop the input thread and release terminal resources (call at the end of a busy phase)"""
        self._stop_event.set()
        self._pause_event.clear()  # wake up a paused loop
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._input_device is not None:
            try:
                self._input_device.close()
            except Exception as e:
                sys_log.error(f"InputThread close input device failed with error: {e}")
            self._input_device = None
        sys_log.debug(f"InputThread stopped")

    def pause(self) -> None:
        """pause key reading while a modal TUI owns stdin"""
        self._pause_event.set()
        sys_log.debug(f"InputThread paused")

    def resume(self) -> None:
        """resume key reading after a modal TUI released stdin"""
        self._pause_event.clear()
        # drain keys buffered while is_paused (e.g. pressed right before the modal exited)
        if self._input_device is not None:
            try:
                self._input_device.flush_keys()
            except Exception as e:
                sys_log.error(f"InputThread flush keys failed with error: {e}")
        sys_log.debug(f"InputThread resumed")

    @property
    def is_paused(self) -> bool:
        """whether the input thread is currently is_paused"""
        return self._pause_event.is_set()

    @property
    def is_alive(self) -> bool:
        """whether the input thread is running"""
        return self._thread is not None and self._thread.is_alive()

    # [Messages access functions for input thread]
    def enqueue_msg(self, msg: str):
        """thread-safe enqueue of a submitted busy-phase message"""
        with self._msg_queue_lock:
            self.msg_queue.append(msg)
            sys_log.debug(f"New message appended to InputThread")

    def drain_msg_queue(self) -> list[str]:
        """thread-safe atomic copy and clear of the pending message queue"""
        with self._msg_queue_lock:
            msgs = self.msg_queue
            self.msg_queue = []
            sys_log.debug(f"Message drained from InputThread")
            return msgs

    def queue_size(self) -> int:
        """pending message count (thread-safe)"""
        with self._msg_queue_lock:
            return len(self.msg_queue)

    def get_draft(self) -> str:
        """current draft text (called by the footer renderer)"""
        return self.draft

    def clear_draft(self) -> None:
        """discard the current draft"""
        self.draft = ""

    def get_render(self, now_time: datetime, base_time: datetime, color_list: list[str]) -> Panel | Text:
        """get input thread's render"""
        time_diff = (now_time - base_time).total_seconds()
        position = time_diff % INSERT_TUI_COLOR_PERIOD
        idx = int((position / INSERT_TUI_COLOR_PERIOD) * len(color_list)) % len(color_list)
        blink: bool = (time_diff % INSERT_TUI_CURSOR_PERIOD) / INSERT_TUI_CURSOR_PERIOD > 0.5
        color = color_list[idx]

        if self.draft != "":
            input_prefix = Text(f"Inserted ", style=f"bright_black")
            input_prefix = input_prefix + Text(f"{self.queue_size()}", style=f"{color}")
            input_prefix = input_prefix + Text(f" messages {INSERT_PROMPT_FIXED_PREFIX}\n", style=f"bright_black")
            icon_str = Text(f" {AGENT_CONSOLE_ICON} ", style=f"white")
            draft_str = Text(self.draft, style="white")
            draft_str = draft_str + Text(f"{INSERT_TUI_CURSOR1 if blink else INSERT_TUI_CURSOR2}", style=f"{color}")

            t = Table(show_header=False, show_edge=False, padding=0, box=None, collapse_padding=True)
            t.add_column(width=MESSAGE_PRINT_MARGIN, min_width=MESSAGE_PRINT_MARGIN, no_wrap=True, vertical="top")
            t.add_column(vertical="top", overflow="fold")
            t.add_row(icon_str, input_prefix)
            t.add_row(Text(), draft_str)
            render = Panel(t, box=rich.box.SQUARE)
            return render
        else:
            render_str = Text(f" {AGENT_CONSOLE_ICON} Inserted ", style=f"bright_black")
            render_str = render_str + Text(f"{self.queue_size()}", style=f"{color}")
            render_str = render_str + Text(f" messages. ", style=f"bright_black")
            render_str = render_str + Text(f"Draft", style=f"{color}")
            render_str = render_str + Text(f" is empty, type to insert messages", style=f"bright_black")
            return render_str

    # [Internals functions for input thread]
    def _run(self) -> None:
        """raw-mode key polling loop; never writes to stdout"""
        device = self._input_device
        assert device is not None
        try:
            with device.raw_mode():
                while not self._stop_event.is_set():
                    if self._pause_event.is_set():
                        time.sleep(INSERT_LISTEN_SLEEP_TIME_MS / 1000.0)
                        continue
                    keys = device.read_keys()
                    if keys:
                        self._handle_keys(keys)
                        continue
                    time.sleep(INSERT_LISTEN_SLEEP_TIME_MS / 1000.0)
        except Exception as e:
            sys_log.error(f"InputThread run error: {e}")

    def _handle_keys(self, keys: list[KeyPress]) -> None:
        """process one frame of key presses against the shared draft"""
        for kp in keys:
            key = kp.key
            if isinstance(key, str) and not isinstance(key, Keys):
                # printable char (space, IME-confirmed CJK, emoji after surrogate merge).
                # NOTE: prompt_toolkit's Keys is a str subclass, so exclude it explicitly.
                self.draft += key
            elif key == Keys.Backspace or key == Keys.ControlH:
                self._backspace()
            elif key == Keys.ControlM or key == Keys.ControlJ:
                if self.draft != "":
                    self._submit()
            elif key == Keys.BackTab:
                self.draft += "\n"
            elif key == Keys.BracketedPaste:
                self.draft += kp.data
            elif key == Keys.Escape:
                self.draft = ""  # discard the draft
            elif key == Keys.ControlC:
                if self.draft:
                    self.draft = ""  # first Ctrl+C: cancel current draft input only
                else:
                    self._cancel()  # empty draft: forward cancel to the busy thread
            # other keys are ignored

    def _backspace(self) -> None:
        """delete the last character; safe for CJK and surrogate-pair emoji"""
        draft = self.draft
        if not draft:
            return
        if len(draft) >= 2 and "\udc00" <= draft[-1] <= "\udfff" and "\ud800" <= draft[-2] <= "\udbff":
            draft = draft[:-2]
        else:
            draft = draft[:-1]
        self.draft = draft

    def _submit(self) -> None:
        """Enter: strip -> ignore empty -> ignore command-like (/...) -> enqueue"""
        draft = self.draft.strip()
        self.draft = ""
        if not draft:
            return
        if draft.startswith("/"):
            # busy phase has no command completion; drop command-like input silently
            return
        self.enqueue_msg(draft)

    def _cancel(self) -> None:
        """Ctrl+C with an empty draft: forward KeyboardInterrupt to the busy thread"""
        if self._cancel_handler is not None:
            self._cancel_handler()
            return
        if self.busy_thread_ident is None:
            sys_log.debug("InputThread: no busy thread to cancel")
            return
        tid = ctypes.c_long(self.busy_thread_ident)
        t_ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(KeyboardInterrupt))
        if t_ret != 1:
            # failed to inject / invalid thread, clear to avoid a dangling exception
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)


def get_insert_list(msgs: list[str]) -> str:
    """get the inserted message list as structured string"""
    msg_str = (f"There {"is" if len(msgs) == 1 else "are"} {len(msgs)} inserted {"message" if len(msgs) == 1 else "messages"} "
                  f"from user:\n")
    for msg in msgs:
        msg_str += f" - {msg}\n"
    msg_str = msg_str.rstrip()
    return f"{INSERT_PROMPT_START_LABEL}\n" + msg_str + f"\n{INSERT_PROMPT_END_LABEL}"
