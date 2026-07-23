# -*- coding: utf-8 -*-
"""
Header information
---------
Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.7.6
Description: WeChat integration support for TECoSim Agent

Revision:
---------
2026.7.6-16    Yu Huang      1.0      First implementation
2026.7.17      Yu Huang      1.1      Fix: last response of LLM won't be missed if bot keep sending WeChat msg & Add quick
                                      WeChat bot exit
2026.7.18      Yu Huang      1.2      Add tool of checking WeChat status & SILK voice is processed as other media types
2026.7.23      Yu Huang      1.3      Add launch support in arbitrary path & Revise visibility of cron/web/WeChat tool calls

Details:
---------
WeChatBridge — runs the wechatbot SDK in a background daemon thread with its own asyncio event loop. Lifecycle: login()
spawns thread, blocks until QR scan completes; run() signals to enter long-poll; stop() gracefully shuts down. Implements
5 login hooks (qr_callback, scanned_callback, qr_expired_callback, verify_code_callback, error_callback) and the core
on_message handler with single-user binding.

Message pipeline: incoming messages → user binding filter → _collect_media downloads attachments under threshold (HEAD CDN
for size, AES decrypt, magic-byte extension detection, CDN cache with persistent JSON) → queue.Queue → main loop drains
via pop_pending(). Quoted message resolution via _msg_history (local in-session index, persistent JSON). Reply methods:
reply_text_sync, reply_media_sync, send_typing_sync, stop_typing_sync — all cross-thread via asyncio.run_coroutine_threadsafe.

Output: get_wechat_list() formats queued messages for LLM prompt (grouped by user, text + media counts + details, quoted
text with voice flag). CachedMedia and WeChatQueuedMsg dataclasses carry parsed message state.
"""
from __future__ import annotations

import random
import asyncio
import json
import logging
import threading
import queue
import aiohttp
import io, qrcode

from dataclasses import dataclass, field
from typing import Optional, Any
from urllib.parse import quote
from collections import defaultdict
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
from src.wechat import WeChatBot, IncomingMessage, CDNMedia
from src.wechat.protocol import CDN_BASE_URL
from src.utility.basic_utils import flush_terminal_input
from src.constants import *

sys_log = logging.getLogger("logger")


@dataclass
class CachedMedia:
    """A single media item: local_path if downloaded, cdn_ref if deferred."""
    type: str               # "image" | "file" | "video" | "voice"
    local_path: Optional[str] = None
    cdn_ref: Optional[CDNMedia] = None
    file_name: Optional[str] = None
    text: Optional[str] = None          # ASR text for voice
    duration_ms: Optional[int] = None   # voice duration
    size: Optional[int] = None          # file size in bytes (from HEAD or len field)


@dataclass
class WeChatQueuedMsg:
    """A processed incoming message ready for the main agent loop."""
    raw_msg: IncomingMessage
    images: list[CachedMedia] = field(default_factory=list)
    files: list[CachedMedia] = field(default_factory=list)
    videos: list[CachedMedia] = field(default_factory=list)
    voices: list[CachedMedia] = field(default_factory=list)
    quoted_text: Optional[str] = None
    quoted_text_is_voice: bool = False  # True when the referenced quoted_text was ASR-transcribed
    quoted_media: list[CachedMedia] = field(default_factory=list)


class WeChatBridge:
    """WeChat bot in a background daemon thread.

    Usage::

        bridge = WeChatBridge(on_qr_url=..., on_scanned=...)
        bridge.login(timeout=120)   # blocks until QR scan completes
        bridge.run()                # non-blocking, starts long-poll in background
        # agent loop runs here
        bridge.stop(timeout=10)     # graceful shutdown

    login() spawns a daemon thread that creates the WeChatBot, calls login(),
    and then pauses on an Event.  run() signals that Event to enter the SDK's
    long-poll loop.  Single WeChatBot instance, single event loop.
    """

    def __init__(self, console: Console, prompt_session: PromptSession, session_uuid: str, config: dict[str, Any]):
        self._console = console
        self._session = prompt_session
        self.session_uuid = session_uuid
        self.login_timeout = config.get("WECHAT_BOT_LOGIN_TIMEOUT_S", WECHAT_BOT_LOGIN_DEFAULT_TIMEOUT_S)
        self.stop_timeout = config.get("WECHAT_BOT_STOP_TIMEOUT_S", WECHAT_BOT_STOP_DEFAULT_TIMEOUT_S)
        self.head_cdn_timeout = config.get("WECHAT_BOT_HEAD_CDN_TIMEOUT_S", WECHAT_BOT_HEAD_CDN_DEFAULT_TIMEOUT_S)
        self.text_reply_timeout = config.get("WECHAT_BOT_TEXT_REPLY_TIMEOUT_S", WECHAT_BOT_TEXT_REPLY_DEFAULT_TIMEOUT_S)
        self.media_reply_timeout = config.get("WECHAT_BOT_MEDIA_REPLY_TIMEOUT_S", WECHAT_BOT_MEDIA_REPLY_DEFAULT_TIMEOUT_S)
        self.mute_nonfatal = config.get("WECHAT_BOT_MUTE_NONFATAL_ERROR", WECHAT_BOT_MUTE_NONFATAL_ERROR_DEFAULT)
        self.if_login = False
        self.if_bound = False
        self.budget_prefix = False
        self._media_cache_dir = AGENT_PATH / SESSION_PATH / session_uuid / WECHAT_MEDIA_CACHE_DIR
        self._media_cache_dir.mkdir(parents=True, exist_ok=True)
        self._media_threshold = config.get("WECHAT_MEDIA_DOWNLOAD_THRESHOLD_MB",
                                           WECHAT_MEDIA_DOWNLOAD_THRESHOLD_MB_DEFAULT) * 1024 * 1024
        self._bot: Optional[WeChatBot] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._logged_in = threading.Event()
        self._start_poll = threading.Event()
        self._login_error: Optional[str] = None
        self._bound_user_id: Optional[str] = None
        self._bound_user_lock = threading.Lock()
        self._msg_queue: queue.Queue = queue.Queue()
        self._cdn_cache: dict[str, CachedMedia] = {}  # encrypt_query_param -> CachedMedia
        self._cache_json = AGENT_PATH / SESSION_PATH / session_uuid / WECHAT_MEDIA_CACHE_NAME
        self._msg_history: dict[str, dict] = {}  # msg_id -> {text, images, files, videos, voices, timestamp}
        self._history_json = AGENT_PATH / SESSION_PATH / session_uuid / WECHAT_HISTORY_NAME

    # [Callback functions for WeChat bot]
    def qr_callback(self, url: str):
        """callback for QR scan"""
        sys_log.debug("QR code scan callback is triggered")

        qr = qrcode.QRCode()
        qr.add_data(url)
        qr.make()
        out = io.StringIO()
        qr.print_ascii(out=out)
        qr_str = out.getvalue()
        sys_log.debug("QR code generated")

        title = f"WeChat Bot Login"
        cmd_str = Text()
        cmd_str.append(f"Please scan the following QR code to login: \n", style=f"bold {MAJOR_COLOR2}")
        cmd_str.append(f"{qr_str}\n", style=f"{MAJOR_COLOR2}")
        cmd_str.append(f"  Tips: If the QR code is unavailable, please open the following link: \n", style=f"white")
        cmd_str.append(f"        {url}", style=f"{MAJOR_COLOR1}")
        self._console.print(
            Panel.fit(cmd_str, title=title, title_align="left", padding=(1, 2, 1, 2), border_style=MAJOR_COLOR2))


    def scanned_callback(self):
        """callback for QR scanned"""
        sys_log.debug("QR code of WeChat Bot is scanned, waiting for confirmation ... ")
        self._console.print("QR code of WeChat Bot is scanned, waiting for confirmation ... ",
                           style=f"bold {MAJOR_COLOR1}")


    def qr_expired_callback(self):
        """callback for QR expired"""
        sys_log.warning("QR code of WeChat Bot expired")
        self._console.print("QR code of WeChat Bot expired", style=f"bold yellow")


    def verify_code_callback(self, is_retry: bool) -> str:
        """callback for verify code — runs in a temp thread to avoid event-loop deadlock"""
        flush_terminal_input()
        result_queue: queue.Queue = queue.Queue()
        if not is_retry:
            prompt_text = f"\033[90m{WECHAT_VERIFY_CODE_PREFIX1}\033[0m\n{AGENT_CONSOLE_ICON} "
        else:
            prompt_text = f"\033[1;31m{WECHAT_VERIFY_CODE_PREFIX2}\033[0m\n{AGENT_CONSOLE_ICON} "

        def _do_prompt():
            try:
                result_queue.put(self._session.prompt(ANSI(prompt_text)).strip())
            except BaseException as e:
                result_queue.put(e)

        t = threading.Thread(target=_do_prompt, daemon=True)
        t.start()
        t.join()
        value = result_queue.get_nowait()
        if isinstance(value, BaseException):
            raise value
        return value


    def error_callback(self, err: Exception):
        """callback for error"""
        sys_log.error(f"WeChat Bot error: {err}")
        if not self.mute_nonfatal:
            self._console.print(f"WeChat Bot error: {err}", style=f"bold red")


    async def on_message(self, msg: IncomingMessage):
        """callback for incoming message — user binding filter"""
        assert self._bot
        with self._bound_user_lock:
            if self._bound_user_id is None:
                self._bound_user_id = msg.user_id
                self.if_bound = True
                sys_log.info(f"WeChat Bot bound to user: {msg.user_id}")
                self._console.print(f"[{MAJOR_COLOR2}]WeChat Bot[/{MAJOR_COLOR2}] bound to user [{MAJOR_COLOR2}]{msg.user_id}[/{MAJOR_COLOR2}]")
                try:
                    await self._bot.reply(msg, random.choice(WECHAT_BOT_LOCKED_LIST))
                    self.budget_prefix = True
                except Exception as e:
                    sys_log.error(f"Reply locked WeChat user failed with error: {e}")
                    if not self.mute_nonfatal:
                        self._console.print(f"Reply locked WeChat user failed with error: {e}", style=f"bold red")
            elif self._bound_user_id != msg.user_id:
                sys_log.info(f"WeChat Bot rejecting message from {msg.user_id} (bound to {self._bound_user_id})")
                try:
                    await self._bot.reply(msg, random.choice(WECHAT_BOT_BLOCK_REPLY_LIST))
                except Exception as e:
                    sys_log.error(f"Reply non-locked WeChat user failed with error: {e}")
                    if not self.mute_nonfatal:
                        self._console.print(f"Reply non-locked WeChat user failed with error: {e}", style=f"bold red")
                return

        queued = WeChatQueuedMsg(raw_msg=msg)
        await self._collect_media(queued)
        self._store_msg_history(msg, queued)
        self._msg_queue.put(queued)
        summary = get_msg_summary(msg)
        sys_log.debug(f"WeChat message from {msg.user_id}: {summary}")

    # [WeChat Bot lifecycle exposed API]
    def login(self) -> bool:
        """Block until QR scan + confirmation."""
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="wechat-bot")
        if self._thread is not None:
            self._thread.start()
        else:
            sys_log.error("WeChat Bot thread is None")
            self._console.print("WeChat Bot thread is None", style=f"bold red")
            return False

        if not self._logged_in.wait(timeout=self.login_timeout):
            self.stop()
            sys_log.error(f"WeChat Bot login timeout > {self.login_timeout} s before QR scan")
            self._console.print(f"WeChat Bot login timeout > {self.login_timeout} s before QR scan", style=f"bold red")
            return False
        if self._login_error:
            self.stop()
            sys_log.error(f"WeChat Bot login failed: {self._login_error}")
            self._console.print(f"WeChat Bot login failed: {self._login_error}", style=f"bold red")
            return False
        self.if_login = True
        sys_log.debug(f"WeChat Bot login done")
        self._console.print(f"[{MAJOR_COLOR2}]WeChat Bot[/{MAJOR_COLOR2}] login done")
        return True


    def run(self) -> None:
        """Start long-poll in the daemon thread (non-blocking)."""
        sys_log.debug("WeChat Bot long-poll started")
        self._console.print(f"[{MAJOR_COLOR2}]WeChat Bot[/{MAJOR_COLOR2}] long-poll started")
        self._start_poll.set()


    def stop(self, mute: bool = False) -> None:
        """Stop the long-poll thread."""
        if self._bot:
            self._bot.stop()
        sys_log.debug("WeChat Bot long-poll is stopping")
        if not mute:
            self._console.print(f"[{MAJOR_COLOR2}]WeChat Bot[/{MAJOR_COLOR2}] long-poll is stopping")
        if self._loop and not self._loop.is_closed():
            async def _cancel_all():
                for task in asyncio.all_tasks():
                    task.cancel()
            asyncio.run_coroutine_threadsafe(_cancel_all(), self._loop)
        sys_log.debug("WeChat Bot remaining tasks cancelled")
        if not mute:
            self._console.print(f"[{MAJOR_COLOR2}]WeChat Bot[/{MAJOR_COLOR2}] remaining tasks cancelled")
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.stop_timeout)
        self.if_login = False
        self.if_bound = False
        self.budget_prefix = False
        sys_log.debug("WeChat Bot thread terminated")
        if not mute:
            self._console.print(f"[{MAJOR_COLOR2}]WeChat Bot[/{MAJOR_COLOR2}] thread terminated")

    # [WeChat Bot msg status and pop method]
    def has_pending(self) -> bool:
        """True when at least one message is waiting in the queue."""
        return not self._msg_queue.empty()


    def pop_pending(self) -> list[WeChatQueuedMsg]:
        """Drain and return all queued messages. Returns empty list if none."""
        result = []
        while True:
            try:
                result.append(self._msg_queue.get_nowait())
            except queue.Empty:
                break
        return result

    # [WeChat Bot msg sending API]
    def send_typing_sync(self, msg: IncomingMessage | WeChatQueuedMsg) -> None:
        """Show typing indicator to the user who sent *msg*. Safe from main thread."""
        if isinstance(msg, WeChatQueuedMsg):
            _msg = msg.raw_msg
        else:
            _msg = msg
        if not self._bot or not self._loop or self._loop.is_closed():
            sys_log.error("Send typing failed, bot or loop is None or loop is closed")
            return
        try:
            asyncio.run_coroutine_threadsafe(self._bot.send_typing(_msg.user_id), self._loop)
            sys_log.debug("Send typing to user done")
        except Exception as e:
            sys_log.error(f"Send typing failed with error: {e}")
            if not self.mute_nonfatal:
                self._console.print(f"Send typing failed with error: {e}", style=f"bold red")


    def stop_typing_sync(self, msg: IncomingMessage | WeChatQueuedMsg) -> None:
        """Cancel typing indicator for the user who sent *msg*. Safe from main thread."""
        if isinstance(msg, WeChatQueuedMsg):
            _msg = msg.raw_msg
        else:
            _msg = msg
        if not self._bot or not self._loop or self._loop.is_closed():
            sys_log.error("Stop typing failed, bot or loop is None or loop is closed")
            return
        try:
            asyncio.run_coroutine_threadsafe(self._bot.stop_typing(_msg.user_id), self._loop)
            sys_log.debug("Stop typing to user done")
        except Exception as e:
            sys_log.error(f"Stop typing failed with error: {e}")
            if not self.mute_nonfatal:
                self._console.print(f"Stop typing failed with error: {e}", style=f"bold red")


    def reply_text_sync(self, msg: IncomingMessage | WeChatQueuedMsg, text: str) -> bool:
        """Send a text reply to *msg*. Safe from main thread. Returns True on success."""
        if isinstance(msg, WeChatQueuedMsg):
            _msg = msg.raw_msg
        else:
            _msg = msg
        if not self._bot or not self._loop or self._loop.is_closed():
            sys_log.error(f"Reply text failed with error, bot or loop is None or loop is closed")
            return False
        try:
            future = asyncio.run_coroutine_threadsafe(self._bot.reply(_msg, text), self._loop)
            future.result(timeout=self.text_reply_timeout)
            sys_log.debug(f"Reply text to user")
            return True
        except Exception as e:
            sys_log.error(f"Reply text failed with error: {e}")
            if not self.mute_nonfatal:
                self._console.print(f"Reply text failed with error: {e}", style=f"bold red")
            return False


    def reply_media_sync(self, msg: IncomingMessage | WeChatQueuedMsg, content: dict[str, Any]) -> tuple[bool, str]:
        """Send a media reply to *msg*. Safe from main thread. Returns True on success.

        *content* is a dict with one of:
            {"image": bytes}                            — image data
            {"image": "/path/to/photo.png"}             — image file path
            {"video": bytes}                            — video data
            {"video": "/path/to/video.mp4"}             — video file path
            {"file": bytes, "file_name": "report.pdf"}  — file data + name
            {"file": "/path/to/report.pdf"}             — file path (name derived from path)
        """
        if isinstance(msg, WeChatQueuedMsg):
            _msg = msg.raw_msg
        else:
            _msg = msg
        if not self._bot or not self._loop or self._loop.is_closed():
            return False, f"Reply media failed, bot or loop is None or loop is closed"
        try:
            resolved = self._resolve_media_content(content)
            future = asyncio.run_coroutine_threadsafe(self._bot.reply_media(_msg, resolved), self._loop)
            future.result(timeout=self.media_reply_timeout)
            sys_log.debug(f"Reply media to user done")
            return True, SUCCESS_LABEL
        except Exception as e:
            sys_log.error(f"Reply media failed with error: {e}")
            if not self.mute_nonfatal:
                self._console.print(f"Reply media failed with error: {e}", style=f"bold red")
            return False, f"Reply media failed with error: {e}"

    # [WeChat Bot data persistence]
    def load_cdn_cache(self, mute: bool = False) -> None:
        """Restore CDN cache from JSON.  Entries whose files no longer exist are dropped."""
        try:
            if not self._cache_json.exists():
                sys_log.error(f"WeChat CDN log {self._cache_json} not exist")
                self._console.print(f"WeChat CDN log {self._cache_json} not exist", style="bold red")
                return
            data = json.loads(self._cache_json.read_text("utf-8"))
            for key, entry in data.items():
                path = Path(entry["local_path"])
                if not path.exists():
                    continue
                self._cdn_cache[key] = CachedMedia(
                    type=entry.get("type", "file"),
                    local_path=entry["local_path"],
                    file_name=entry.get("file_name"),
                    size=entry.get("size"),
                )
            sys_log.info(f"WeChat CDN log with {len(self._cdn_cache)} entries of session {self.session_uuid} loaded")
            if not mute:
                self._console.print(f"[{MAJOR_COLOR2}]WeChat CDN log[/{MAJOR_COLOR2}] with [{MAJOR_COLOR2}]{len(self._cdn_cache)}[/{MAJOR_COLOR2}] "
                                    f"entries of session [bright_black]{self.session_uuid}[/bright_black] loaded")
        except Exception as e:
            sys_log.error(f"Failed to load session {self.session_uuid}'s WeChat CDN log with error: {e}")
            self._console.print(f"Failed to load session {self.session_uuid}'s WeChat CDN log with error: {e}", style="bold red")


    def save_cdn_cache(self, mute: bool = False) -> None:
        """Persist CDN cache to JSON (only entries with local_path)."""
        try:
            data = {}
            for key, cm in self._cdn_cache.items():
                if cm.local_path:
                    data[key] = {
                        "local_path": cm.local_path,
                        "type": cm.type,
                        "file_name": cm.file_name,
                        "size": cm.size,
                    }
            self._cache_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
            sys_log.info(f"WeChat CDN log with {len(self._cdn_cache)} entries of session {self.session_uuid} saved")
            if not mute:
                self._console.print(f"[{MAJOR_COLOR2}]WeChat CDN log[/{MAJOR_COLOR2}] with [{MAJOR_COLOR2}]{len(self._cdn_cache)}[/{MAJOR_COLOR2}] "
                                    f"entries of session [bright_black]{self.session_uuid}[/bright_black] saved")
        except Exception as e:
            sys_log.error(f"Failed to save session {self.session_uuid}'s WeChat CDN log with error: {e}")
            self._console.print(f"Failed to save session {self.session_uuid}'s WeChat CDN log with error: {e}", style="bold red")


    def load_msg_history(self, mute: bool = False) -> None:
        """Restore message history from JSON."""
        try:
            if not self._history_json.exists():
                return
            data = json.loads(self._history_json.read_text("utf-8"))
            self._msg_history = data
            sys_log.info(f"WeChat msg history with {len(self._msg_history)} entries of session {self.session_uuid} loaded")
            if not mute:
                self._console.print(f"[{MAJOR_COLOR2}]WeChat msg history[/{MAJOR_COLOR2}] with [{MAJOR_COLOR2}]{len(self._msg_history)}[/{MAJOR_COLOR2}] "
                                    f"entries of session [bright_black]{self.session_uuid}[/bright_black] loaded")
        except Exception as e:
            sys_log.error(f"Failed to load session {self.session_uuid}'s WeChat msg history with error: {e}")
            self._console.print(f"Failed to load session {self.session_uuid}'s WeChat msg history with error: {e}", style="bold red")


    def save_msg_history(self, mute: bool = False) -> None:
        """Persist message history to JSON."""
        try:
            self._history_json.write_text(json.dumps(self._msg_history, indent=2, ensure_ascii=False), "utf-8")
            sys_log.info(f"WeChat msg history with {len(self._msg_history)} entries of session {self.session_uuid} saved")
            if not mute:
                self._console.print(f"[{MAJOR_COLOR2}]WeChat msg history[/{MAJOR_COLOR2}] with [{MAJOR_COLOR2}]{len(self._msg_history)}[/{MAJOR_COLOR2}] "
                                    f"entries of session [bright_black]{self.session_uuid}[/bright_black] saved")
        except Exception as e:
            sys_log.error(f"Failed to save session {self.session_uuid}'s WeChat msg history with error: {e}")
            self._console.print(f"Failed to save session {self.session_uuid}'s WeChat msg history with error: {e}", style="bold red")


    def get_cdn_status(self) -> str:
        """get the status of WeChat CDN"""
        img_count = 0
        img_downloaded = 0
        img_downloaded_size = 0
        video_count = 0
        video_downloaded = 0
        video_downloaded_size = 0
        voice_count = 0
        voice_ms = 0
        voice_downloaded = 0
        voice_downloaded_size = 0
        voice_downloaded_ms = 0
        file_count = 0
        file_downloaded = 0
        file_downloaded_size = 0
        total_downloaded_size = 0
        for item in self._cdn_cache.values():
            if item.type == "image":
                img_count += 1
                if item.local_path is not None:
                    img_downloaded += 1
                if item.size is not None:
                    img_downloaded_size += item.size
                    total_downloaded_size += item.size
            if item.type == "video":
                video_count += 1
                if item.local_path is not None:
                    video_downloaded += 1
                if item.size is not None:
                    video_downloaded_size += item.size
                    total_downloaded_size += item.size
            if item.type == "voice":
                voice_count += 1
                if item.duration_ms:
                    voice_ms += item.duration_ms
                if item.local_path is not None:
                    voice_downloaded += 1
                    voice_downloaded_ms += item.duration_ms
                if item.size is not None:
                    voice_downloaded_size += item.size
                    total_downloaded_size += item.size
            if item.type == "file":
                file_count += 1
                if item.local_path is not None:
                    file_downloaded += 1
                if item.size is not None:
                    file_downloaded_size += item.size
                    total_downloaded_size += item.size
        cdn_str = (f"WeChat CDN Status:\n"
                   f" - Image: `{img_count}` received (`{img_downloaded}` downloaded, `{img_downloaded_size / (1024 * 1024):.3f}` MB)\n"
                   f" - Video: `{video_count}` received (`{video_downloaded}` downloaded, `{video_downloaded_size / (1024 * 1024):.3f}` MB)\n"
                   f" - Voice: `{voice_count}` received, total `{voice_ms / 1000:.2f}` s, "
                   f"(`{voice_downloaded}` downloaded, `{voice_downloaded_size / (1024 * 1024):.3f}` MB, `{voice_downloaded_ms / 1000:.2f}` s)\n"
                   f" - File: `{file_count}` received (`{file_downloaded}` downloaded, `{file_downloaded_size / (1024 * 1024):.3f}` MB)\n"
                   f" - Total Downloaded: `{total_downloaded_size / (1024 * 1024):.3f}` MB\n")
        return cdn_str


    def get_status(self) -> str:
        """get the status of WeChat bot"""
        status_str = (f"Session UUID: `{self.session_uuid if self.session_uuid else "None"}`\n"
                      f"Login Status: {"`ONLINE`" if self.if_login else "`OFFLINE`"}\n"
                      f"Login Error: `{self._login_error if self._login_error else "None"}`\n"
                      f"Bounded User: `{self._bound_user_id if self.if_bound else "None"}`\n\n"
                      f"Queued Messages: `{self._msg_queue.qsize()}`\n"
                      f"Logged User Messages: `{len(self._msg_history)}`\n"
                      f"{self.get_cdn_status()}")
        return status_str

    # [WeChat Bot internal API] Internal bot loop
    def _poll_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        assert self._loop
        asyncio.set_event_loop(self._loop)
        loop = self._loop
        try:
            self._bot = WeChatBot(
                cred_path=str(AGENT_PATH / WECHAT_CRED_PATH),
                on_qr_url=self.qr_callback,
                on_scanned=self.scanned_callback,
                on_expired=self.qr_expired_callback,
                on_verify_code=self.verify_code_callback,
                on_error=self.error_callback,
            )
            assert self._bot
            self._bot.on_message(self.on_message)
            sys_log.debug("WeChat Bot object created")
            self._console.print(f"[{MAJOR_COLOR2}]WeChat Bot[/{MAJOR_COLOR2}] object created")
            loop.run_until_complete(self._bot.login())
        except Exception as e:
            self._login_error = str(e)
            sys_log.error(f"WeChat Bot login failed with error: {e}")
            self._console.print(f"WeChat Bot login failed with error: {e}", style=f"bold red")
            loop.close()
            return

        self._logged_in.set()
        self._start_poll.wait()

        try:
            loop.run_until_complete(self._bot.start())
        except Exception as e:
            sys_log.error(f"WeChat Bot polling failed with error: {e}")
            self._console.print(f"WeChat Bot polling failed with error: {e}", style=f"bold red")
        finally:
            loop.close()

    # [WeChat Bot internal API] Message, media handling function
    async def _collect_media(self, queued: WeChatQueuedMsg) -> None:
        """Download media items under threshold; cache by encrypt_query_param."""
        msg = queued.raw_msg
        for img in msg.images:
            cm = await self._process_one_media(img.media, "image", img.aes_key, None, None)
            queued.images.append(cm)
        for f in msg.files:
            cm = await self._process_one_media(f.media, "file", None, f.file_name, f.size)
            queued.files.append(cm)
        for v in msg.videos:
            cm = await self._process_one_media(v.media, "video", None, None, None)
            queued.videos.append(cm)
        for v in msg.voices:
            cm = await self._process_one_media(v.media, "voice", None, None, None)
            cm.text = v.text
            cm.duration_ms = v.duration_ms
            queued.voices.append(cm)
        # Quoted msgs
        await self._collect_quoted_msg(msg, queued)


    async def _collect_quoted_msg(self, msg: IncomingMessage, queued: WeChatQueuedMsg) -> None:
        """Parse ref_msg in raw item_list, resolve via _msg_history, and fill queued.quoted_text + quoted_media."""
        for item in msg.raw.get("item_list", []):
            ref = item.get("ref_msg")
            if not ref:
                continue
            ref_id = ref.get("message_item", {}).get("msg_id")

            # ── Try local message history first ──────────────────
            hist = self._msg_history.get(ref_id) if ref_id else None
            if hist:
                if hist.get("text"):
                    queued.quoted_text = hist["text"]
                if hist.get("is_voice", False):
                    queued.quoted_text_is_voice = True
                for img_path in hist.get("images", []):
                    queued.quoted_media.append(CachedMedia(type="image", local_path=img_path))
                for f_path in hist.get("files", []):
                    queued.quoted_media.append(CachedMedia(type="file", local_path=f_path))
                for v_path in hist.get("videos", []):
                    queued.quoted_media.append(CachedMedia(type="video", local_path=v_path))
                for v_path in hist.get("voices", []):
                    queued.quoted_media.append(CachedMedia(type="voice", local_path=v_path))
                continue

            # ── Fallback: raw ref_msg content (protocol rarely fills this) ──
            if queued.quoted_text is None:
                queued.quoted_text = f"(Quoted message is unavailable)"


    async def _process_one_media(
        self, media: CDNMedia | None, mtype: str,
        aes_key: str | None, file_name: str | None, known_size: int | None,
    ) -> CachedMedia:
        if not media:
            return CachedMedia(type=mtype)
        cache_key = media.encrypt_query_param
        if cache_key in self._cdn_cache:
            return self._cdn_cache[cache_key]

        size = known_size
        if size is None:
            size = await self._head_cdn(media.encrypt_query_param)

        if size is not None and size <= self._media_threshold:
            local_path = self._make_media_path(cache_key, file_name, mtype)
            try:
                assert self._bot
                data = await self._bot.download_raw(media, aes_key)
                local_path.write_bytes(data)
                # detect if the actual format is equal to the given type
                if mtype in ("image", "video") and not file_name:
                    real_ext = detect_ext_by_magic(data, mtype)
                    guessed_ext = detect_ext_by_type(mtype)
                    if real_ext != guessed_ext:
                        corrected = local_path.with_suffix(f".{real_ext}")
                        local_path.rename(corrected)
                        local_path = corrected
                cm = CachedMedia(type=mtype, local_path=str(local_path), file_name=file_name, size=size)
            except Exception as e:
                sys_log.warning(f"Failed to download {mtype} media: {e}")
                cm = CachedMedia(type=mtype, cdn_ref=media, file_name=file_name, size=size)
        else:
            cm = CachedMedia(type=mtype, cdn_ref=media, file_name=file_name, size=size)

        self._cdn_cache[cache_key] = cm
        return cm


    async def _head_cdn(self, encrypt_query_param: str) -> int | None:
        """HEAD the CDN to get Content-Length.  Returns None on failure."""
        url = f"{CDN_BASE_URL}/download?encrypted_query_param={quote(encrypt_query_param)}"
        try:
            timeout = aiohttp.ClientTimeout(total=self.head_cdn_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.head(url) as resp:
                    if resp.status < 400:
                        cl = resp.headers.get("Content-Length")
                        if cl:
                            return int(cl)
        except Exception as e:
            sys_log.error(f"Failed to get Content-Length from {url} with error: {e}")
            self._console.print(f"Failed to get Content-Length from {url} with error: {e}", style="bold red")
        return None


    def _make_media_path(self, cache_key: str, file_name: str | None, mtype: str) -> Path:
        """Build a local path for a downloaded media file (absolute)."""
        prefix = cache_key[:WECHAT_MEDIA_CACHE_KEY_MAX_LEN]
        suffix = file_name or f"{mtype}.{detect_ext_by_type(mtype)}"
        return (self._media_cache_dir / f"{prefix}_{suffix}").resolve()


    def _store_msg_history(self, msg: IncomingMessage, queued: WeChatQueuedMsg) -> None:
        """Store an incoming message in _msg_history keyed by its server message_id."""
        msg_id = str(msg.raw.get("message_id", ""))
        if not msg_id:
            return
        entry: dict[str, Any] = {
            "text": msg.text,
            "images": [cm.local_path for cm in queued.images if cm.local_path],
            "files": [cm.local_path for cm in queued.files if cm.local_path],
            "videos": [cm.local_path for cm in queued.videos if cm.local_path],
            "voices": [cm.local_path for cm in queued.voices if cm.local_path],
            "is_voice": bool(queued.voices),
            "timestamp": msg.timestamp.isoformat(),
        }
        self._msg_history[msg_id] = entry


    @staticmethod
    def _resolve_media_content(content: dict[str, Any]) -> dict[str, Any]:
        """Resolve file paths to bytes in a media content dict.  Passes through bytes directly."""
        resolved: dict[str, Any] = {}
        for key in ("image", "video"):
            if key in content:
                value = content[key]
                if isinstance(value, bytes):
                    resolved[key] = value
                elif isinstance(value, str):
                    resolved[key] = Path(value).read_bytes()
                else:
                    raise ValueError(f"Invalid {key} content type: {type(value)}")
                return resolved
        if "file" in content:
            value = content["file"]
            fname = content.get("file_name")
            if isinstance(value, bytes):
                resolved["file"] = value
            elif isinstance(value, str):
                p = Path(value)
                resolved["file"] = p.read_bytes()
                if not fname:
                    fname = p.name
            else:
                raise ValueError(f"Invalid file content type: {type(value)}")
            if fname:
                resolved["file_name"] = fname
            return resolved
        raise ValueError(f"Unsupported media content: {list(content.keys())}")


def detect_ext_by_type(mtype: str) -> str:
    """Default file extension for a media type when file_name is unavailable."""
    return {
        "image": "jpg",
        "video": "mp4",
        "file": "bin",
        "voice": "silk",
    }.get(mtype, "bin")


def detect_ext_by_magic(data: bytes, mtype: str) -> str:
    """Detect file extension from magic bytes.  Falls back to detect_ext_by_type."""
    if mtype == "image":
        if data[:2] == b'\xff\xd8':
            return "jpg"
        if data[:4] == b'\x89PNG':
            return "png"
        if data[:4] in (b'GIF8',):
            return "gif"
        if data[:4] == b'RIFF' and len(data) > 11 and data[8:12] == b'WEBP':
            return "webp"
        if data[:2] == b'BM':
            return "bmp"
    if mtype == "video":
        if data[4:8] == b'ftyp':
            return "mp4"
        if data[:4] == b'\x1aE\xdf\xa3':
            return "mkv"
    return detect_ext_by_type(mtype)


def get_msg_summary(msg: IncomingMessage) -> str:
    """get a compact summary string for logging: text preview + media counts."""
    if msg.text:
        if len(msg.text) > WECHAT_BOT_MSG_SUMMARY_CHAR_MAX:
            text_part = msg.text[:WECHAT_BOT_MSG_SUMMARY_CHAR_MAX] + " ... "
        else:
            text_part = msg.text
    else:
        text_part = ""
    parts = [text_part] if text_part else []
    if msg.images:
        parts.append(f"[{len(msg.images)} image{'s' if len(msg.images) > 1 else ''}]")
    if msg.files:
        parts.append(f"[{len(msg.files)} file{'s' if len(msg.files) > 1 else ''}]")
    if msg.videos:
        parts.append(f"[{len(msg.videos)} video{'s' if len(msg.videos) > 1 else ''}]")
    if msg.voices:
        parts.append(f"[{len(msg.voices)} voice{'s' if len(msg.voices) > 1 else ''}]")
    if not parts:
        return f"({msg.type})"
    return " ".join(parts)


def get_wechat_list(msgs: list[WeChatQueuedMsg], media_threshold_mb: int) -> str:
    """get the WeChat message list as structured string, grouped by user_id"""
    if not msgs:
        sys_log.warning("No message received, this should not happen")
        return (f"{WECHAT_PROMPT_START_LABEL}\n"
                f"(There is no WeChat message from user, this is an unexpected error)\n"
                f"{WECHAT_PROMPT_END_LABEL}")

    grouped: dict[str, list[WeChatQueuedMsg]] = defaultdict(list)
    for msg in msgs:
        grouped[msg.raw_msg.user_id].append(msg)

    lines: list[str] = []
    num_users = len(grouped)
    total_msgs = len(msgs)
    if num_users > 1:
        lines.append(f"`{total_msgs}` new WeChat messages from `{num_users}` users:\n\n")
    elif total_msgs > 1:
        lines.append(f"`{total_msgs}` new WeChat messages from user:\n\n")
    else:
        lines.append(f"New WeChat message from user:\n\n")

    for i, (user_id, user_msgs) in enumerate(grouped.items()):
        if num_users > 1:
            lines.append(f"User `{user_id}` (`{len(user_msgs)}` msgs):\n")
        for j, msg in enumerate(user_msgs):
            msg_preview = get_msg_preview(msg)
            media_details = get_msg_media_details(msg, media_threshold_mb)
            if len(user_msgs) <= 1:
                lines.append(f"{msg_preview}")
                if media_details is not None:
                    lines.append(media_details)
            else:
                lines.append(f"Message-[`{j+1}`]\n")
                lines.append(f"{msg_preview}")
                if media_details is not None:
                    lines.append(media_details)
                lines.append(f"\n")
        if num_users > 1:
            lines.append(f"\n")

    return f"{WECHAT_PROMPT_START_LABEL}\n" + "".join(lines) + f"\n{WECHAT_PROMPT_END_LABEL}"


def get_msg_preview(msg: WeChatQueuedMsg) -> str:
    """build a single-line preview of a message: text + media counts"""
    raw = msg.raw_msg
    preview_str = ""
    if raw.text:
        if msg.voices:
            preview_str += f" - User Text (from voice): {raw.text}\n"
        else:
            preview_str += f" - User Text: {raw.text}\n"
    if msg.quoted_text:
        quote_prefix = " - Quoted Text (from voice): " if msg.quoted_text_is_voice else " - Quoted Text: "
        if len(msg.quoted_text) > WECHAT_BOT_QUOTED_CHAR_MAX:
            preview_str += f"{quote_prefix}{msg.quoted_text[:WECHAT_BOT_QUOTED_CHAR_MAX] } ... (quotation truncated)\n"
        else:
            preview_str += f"{quote_prefix}{msg.quoted_text}\n"
    media_counts = get_media_counts(msg)
    if media_counts:
        preview_str += f" - Media Count: {media_counts}\n"
    if preview_str == "":
        preview_str = f"(Message type: `{raw.type}`, but the preview is empty, this is an unexpected error)\n"
    return preview_str


def get_media_counts(msg: WeChatQueuedMsg) -> str:
    """build a compact media summary"""
    items: list[str] = []
    if msg.images:
        items.append(f"`{len(msg.images)}` image{'s' if len(msg.images) > 1 else ''}")
    if msg.files:
        items.append(f"`{len(msg.files)}` file{'s' if len(msg.files) > 1 else ''}")
    if msg.videos:
        items.append(f"`{len(msg.videos)}` video{'s' if len(msg.videos) > 1 else ''}")
    if msg.voices:
        items.append(f"`{len(msg.voices)}` voice{'s' if len(msg.voices) > 1 else ''}")
    if msg.quoted_media:
        items.append(f"`{len(msg.quoted_media)}` quoted media file{'s' if len(msg.quoted_media) > 1 else ''}")
    return f"{', '.join(items)}" if items else ""


def get_msg_media_details(msg: WeChatQueuedMsg, threshold_mb: int) -> str | None:
    """build indented media detail lines for a single message"""
    detail_str = ""
    for cm in msg.images:
        detail_str += f"   - image: {get_cached_media_str(cm, threshold_mb)}\n"
    for cm in msg.files:
        detail_str += f"   - file: {get_cached_media_str(cm, threshold_mb)}\n"
    for cm in msg.videos:
        detail_str += f"   - video: {get_cached_media_str(cm, threshold_mb)}\n"
    for cm in msg.voices:
        detail_str += f"   - voice: {get_cached_media_str(cm, threshold_mb)}\n"
    for cm in msg.quoted_media:
        detail_str += f"   - quoted: {get_cached_media_str(cm, threshold_mb, show_text=True)}\n"
    return detail_str if detail_str else None


def get_cached_media_str(cm: CachedMedia, threshold_mb: int, show_text: bool = False) -> str:
    """build a single CachedMedia representation string."""
    parts: list[str] = []
    if show_text and cm.text:
        parts.append(f"text in voice: \"{cm.text}\"")
    if cm.duration_ms is not None:
        parts.append(f"voice duration: `{cm.duration_ms / 1000:.2f}` s")
    if cm.local_path:
        parts.append(f"local path: `{cm.local_path}`")
    elif cm.size is not None:
        size_mb = cm.size / (1024 * 1024)
        if size_mb >= threshold_mb:
            parts.append(f"(exceeds `{threshold_mb:.3f}` MB threshold, not downloaded)")
        else:
            parts.append(f"(`{cm.size}` bytes, not downloaded)")
    else:
        parts.append("(not downloaded)")
    if cm.file_name:
        parts.append(f"file name: `{cm.file_name}`")
    if cm.size is not None:
        parts.append(f"file size: `{cm.size / (1024 * 1024):.3f}` MB")
    return " | ".join(parts)
