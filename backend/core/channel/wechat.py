"""微信 ilink Bot Adapter。

通过长轮询获取微信消息，通过 ilink Bot API 发送回复。
"""

import asyncio
import base64
import logging
import os
import uuid
from typing import Any

import httpx

from backend.core.channel.base import ChannelAdapter
from backend.core.channel.types import ChannelMessage

logger = logging.getLogger(__name__)

ILINK_BASE_URL = "https://ilinkai.weixin.qq.com"
BOT_TYPE = 3
MSG_TYPE_USER = 1
MSG_TYPE_BOT = 2
MSG_STATE_FINISH = 2
MSG_ITEM_TEXT = 1
CHANNEL_VERSION = "0.2.0"


class WeChatAdapter(ChannelAdapter):
    """微信 ilink Bot 适配器。

    start() 启动长轮询，stop() 取消轮询并清理资源。
    运行时状态（cursor、context_tokens）保存在内存中。
    """

    def __init__(self, channel_id: str, config: dict, on_message):
        super().__init__(channel_id, config, on_message)

        self.bot_token: str = config.get("bot_token", "")
        self.ilink_bot_id: str = config.get("ilink_bot_id", "")
        self.ilink_user_id: str = config.get("ilink_user_id", "")

        # 运行时状态
        self._updates_buf: str = ""
        self._context_tokens: dict[str, str] = {}
        self._poll_task: asyncio.Task | None = None
        self._fail_count = 0
        self._client: httpx.AsyncClient | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=40)
        return self._client

    def _get_headers(self) -> dict[str, str]:
        uin = base64.b64encode(os.urandom(4)).decode()
        logger.debug(f"[wechat:{self.channel_id}] bot_token: {self.bot_token}")
        return {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": uin,
            "Authorization": f"Bearer {self.bot_token}",
        }

    # ==================== 生命周期 ====================

    async def start(self) -> None:
        if self._running:
            return
        if not self.bot_token:
            logger.warning(f"[wechat:{self.channel_id}] No bot_token, skip polling")
            return

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info(f"[wechat:{self.channel_id}] Started polling")

    async def stop(self) -> None:
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        logger.info(f"[wechat:{self.channel_id}] Stopped polling")

    # ==================== 消息轮询 ====================

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                messages = await self._get_updates()
                self._fail_count = 0

                for msg in messages:
                    try:
                        await self._handle_raw_message(msg)
                    except Exception as e:
                        logger.error(f"[wechat:{self.channel_id}] Handle msg error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._fail_count += 1
                wait = 2 if self._fail_count < 3 else 30
                logger.error(
                    f"[wechat:{self.channel_id}] Poll error ({self._fail_count}): {e}"
                )
                await asyncio.sleep(wait)

    async def _get_updates(self) -> list[dict]:
        client = self._get_client()
        resp = await client.post(
            f"{ILINK_BASE_URL}/ilink/bot/getupdates",
            headers=self._get_headers(),
            json={
                "get_updates_buf": self._updates_buf,
                "base_info": {"channel_version": CHANNEL_VERSION},
            },
        )
        resp.raise_for_status()
        data = resp.json()

        new_buf = data.get("get_updates_buf", "")
        if new_buf:
            self._updates_buf = new_buf

        msgs = data.get("msgs", [])
        if msgs:
            logger.info(f"[wechat:{self.channel_id}] Got {len(msgs)} messages")

        return msgs

    async def _handle_raw_message(self, msg: dict) -> None:
        if msg.get("message_type") != MSG_TYPE_USER:
            return

        from_user_id = msg.get("from_user_id", "")
        session_id = msg.get("session_id", "")
        group_id = msg.get("group_id", "")
        context_token = msg.get("context_token", "")

        # 私聊时 session_id 和 group_id 都为空，用 from_user_id 作为 conversation_id
        conversation_id = group_id or session_id or from_user_id

        logger.info(
            f"[wechat:{self.channel_id}] Raw message: "
            f"sender={from_user_id}, conv={conversation_id}, "
            f"group={'yes' if group_id else 'no'}, has_ctx={'yes' if context_token else 'no'}"
        )

        if context_token:
            self._context_tokens[conversation_id] = context_token

        text = self._extract_text(msg)
        if not text:
            return

        channel_msg = ChannelMessage(
            message_id=str(msg.get("create_time_ms", "")),
            conversation_id=conversation_id,
            sender_id=from_user_id,
            text=text,
            raw_data=msg,
            platform="wechat",
        )

        await self._on_message(self.channel_id, channel_msg)

    @staticmethod
    def _extract_text(msg: dict) -> str:
        item_list = msg.get("item_list", [])
        texts = []
        for item in item_list:
            item_type = item.get("type", 0)
            if item_type == MSG_ITEM_TEXT:
                text_item = item.get("text_item", {})
                texts.append(text_item.get("text", ""))
            elif item_type == 3:
                voice_item = item.get("voice_item", {})
                voice_text = voice_item.get("text", "")
                if voice_text:
                    texts.append(f"[语音] {voice_text}")
        return "\n".join(texts)

    # ==================== 发送消息 ====================

    async def send_message(self, conversation_id: str, text: str, **kwargs) -> None:
        context_token = self._context_tokens.get(conversation_id, "")
        if not context_token:
            logger.warning(
                f"[wechat:{self.channel_id}] No context_token for {conversation_id}"
            )
            return

        client = self._get_client()
        client_id = f"claude-agent:{uuid.uuid4().hex[:16]}"

        resp = await client.post(
            f"{ILINK_BASE_URL}/ilink/bot/sendmessage",
            headers=self._get_headers(),
            json={
                "msg": {
                    "from_user_id": "",
                    "to_user_id": conversation_id,
                    "client_id": client_id,
                    "message_type": MSG_TYPE_BOT,
                    "message_state": MSG_STATE_FINISH,
                    "context_token": context_token,
                    "item_list": [
                        {"type": MSG_ITEM_TEXT, "text_item": {"text": text}}
                    ],
                },
                "base_info": {"channel_version": CHANNEL_VERSION},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("ret") != 0:
            logger.error(
                f"[wechat:{self.channel_id}] Send failed: {data.get('errmsg')}"
            )

    async def send_typing(self, conversation_id: str) -> None:
        context_token = self._context_tokens.get(conversation_id, "")
        logger.info(
            f"[wechat:{self.channel_id}] send_typing: conv={conversation_id}, "
            f"has_token={'yes' if context_token else 'no'}, "
            f"stored_convs={list(self._context_tokens.keys())}"
        )
        if not context_token:
            return

        try:
            client = self._get_client()
            resp = await client.post(
                f"{ILINK_BASE_URL}/ilink/bot/getconfig",
                headers=self._get_headers(),
                json={
                    "to_user_id": conversation_id,
                    "context_token": context_token,
                    "base_info": {"channel_version": CHANNEL_VERSION},
                },
            )
            data = resp.json()
            typing_ticket = data.get("typing_ticket", "")
            if not typing_ticket:
                return

            await client.post(
                f"{ILINK_BASE_URL}/ilink/bot/sendtyping",
                headers=self._get_headers(),
                json={
                    "to_user_id": conversation_id,
                    "typing_ticket": typing_ticket,
                    "context_token": context_token,
                    "base_info": {"channel_version": CHANNEL_VERSION},
                },
            )
        except Exception as e:
            logger.debug(f"[wechat:{self.channel_id}] Typing error (non-critical): {e}")

    # ==================== QR 登录 ====================

    async def request_qrcode(self) -> dict[str, str]:
        client = self._get_client()
        resp = await client.get(
            f"{ILINK_BASE_URL}/ilink/bot/get_bot_qrcode",
            params={"bot_type": BOT_TYPE},
        )
        resp.raise_for_status()
        return resp.json()

    async def check_login_status(self, qrcode_id: str) -> dict[str, Any]:
        client = self._get_client()
        resp = await client.get(
            f"{ILINK_BASE_URL}/ilink/bot/get_qrcode_status",
            params={"qrcode": qrcode_id},
            headers={"iLink-App-ClientVersion": "1"},
        )
        resp.raise_for_status()
        return resp.json()
