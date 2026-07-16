# -*- coding: utf-8 -*-
"""
Header information
---------
Original Project: https://github.com/corespeed-io/wechatbot under MIT license

Shanghai Jiao Tong University, School of Integrated Circuits, SMIL Lab
Author: Yu Huang
Create Date: 2026.7.15
Description: WeChat iLink SDK for Python

Revision:
---------
2026.7.15      Yu Huang      1.0      Add header information

Details:
---------
WeChat iLink SDK API export
"""
from .types import (
    CDNMedia,
    Credentials,
    IncomingMessage,
    ImageContent,
    VoiceContent,
    FileContent,
    VideoContent,
    QuotedMessage,
    ContentType,
    DownloadedMedia,
    UploadResult,
    MediaType,
)
from .client import SendContent, WeChatBot
from .errors import (
    WeChatBotError,
    ApiError,
    AuthError,
    NoContextError,
    MediaError,
)
from .crypto import (
    encrypt_aes_ecb,
    decrypt_aes_ecb,
    generate_aes_key,
    decode_aes_key,
    encrypted_size,
)

__all__ = [
    "CDNMedia",
    "WeChatBot",
    "SendContent",
    "Credentials",
    "IncomingMessage",
    "ImageContent",
    "VoiceContent",
    "FileContent",
    "VideoContent",
    "QuotedMessage",
    "ContentType",
    "DownloadedMedia",
    "UploadResult",
    "MediaType",
    "WeChatBotError",
    "ApiError",
    "AuthError",
    "NoContextError",
    "MediaError",
    "encrypt_aes_ecb",
    "decrypt_aes_ecb",
    "generate_aes_key",
    "decode_aes_key",
    "encrypted_size",
]
