# -*- coding: utf-8 -*-
"""
Header information
---------
Original Project: https://github.com/corespeed-io/wechatbot under MIT license

Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.7.15
Description: Error hierarchy for the WeChat Bot SDK

Revision:
---------
2026.7.15      Yu Huang      1.0      Add header information

Details:
---------
Error hierarchy for the WeChat Bot SDK. Base class WeChatBotError. ApiError wraps HTTP-level failures and provides is_session_expired
(errcode -14) for automatic re-login logic. AuthError covers QR login failures. NoContextError is raised when sending to
a user without a cached context_token. MediaError covers CDN upload/download failures.
"""

class WeChatBotError(Exception):
    """Base error for all SDK errors."""

    def __init__(self, message: str, code: str = "UNKNOWN") -> None:
        super().__init__(message)
        self.code = code


class ApiError(WeChatBotError):
    """Returned when the iLink API returns an error."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int = 0,
        errcode: int = 0,
        payload: object = None,
    ) -> None:
        super().__init__(message, "API_ERROR")
        self.http_status = http_status
        self.errcode = errcode
        self.payload = payload

    @property
    def is_session_expired(self) -> bool:
        return self.errcode == -14


class AuthError(WeChatBotError):
    """Authentication errors (QR expired, login failed, etc.)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "AUTH_ERROR")


class NoContextError(WeChatBotError):
    """No context_token available for a user."""

    def __init__(self, user_id: str) -> None:
        super().__init__(
            f"No context_token for user {user_id}. "
            "A message from this user must be received first.",
            "NO_CONTEXT",
        )
        self.user_id = user_id


class MediaError(WeChatBotError):
    """Media processing errors (encryption, upload, download)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "MEDIA_ERROR")
