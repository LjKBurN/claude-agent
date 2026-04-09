"""HTTP/SSE Transport 实现。

通过 HTTP + Server-Sent Events 与远程 MCP Server 通信。
"""

import asyncio
import json
from typing import Any

import httpx

from backend.core.mcp.types import BaseTransport, JSONRPCMessage, MCPServerConfig


class HTTPTransport(BaseTransport):
    """HTTP/SSE 传输层。

    使用 HTTP POST 发送请求，SSE 接收响应和通知。
    """

    def __init__(self, config: MCPServerConfig):
        super().__init__(config)
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._sse_task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None
        self._message_endpoint: str | None = None
        self._running = False

    async def start(self) -> None:
        """启动 HTTP 连接并建立 SSE 流。"""
        if not self.config.url:
            raise ValueError(f"No URL specified for HTTP transport: {self.config.name}")

        # 创建 HTTP 客户端
        self._client = httpx.AsyncClient(
            base_url=self.config.url,
            headers=self.config.headers,
            timeout=httpx.Timeout(30.0, read=300.0),  # SSE 需要长超时
        )

        # 启动 SSE 监听
        self._running = True
        self._sse_task = asyncio.create_task(self._sse_loop())

        # 等待 endpoint 事件（MCP 规范要求）
        # 短暂延迟让 SSE 连接建立
        await asyncio.sleep(0.1)

    async def stop(self) -> None:
        """停止 HTTP 连接。"""
        self._running = False

        if self._sse_task:
            self._sse_task.cancel()
            try:
                await self._sse_task
            except asyncio.CancelledError:
                pass
            self._sse_task = None

        if self._client:
            await self._client.aclose()
            self._client = None

    async def send_request(
        self,
        method: str,
        params: dict | None = None,
        timeout: float = 30.0,
    ) -> Any:
        """发送 HTTP POST 请求并等待 SSE 响应。"""
        if not self._client:
            raise RuntimeError("Transport not started")

        self._request_id += 1
        request_id = self._request_id

        message = JSONRPCMessage(
            id=request_id,
            method=method,
            params=params,
        )

        # 创建 Future 等待响应
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        # 确定发送端点
        endpoint = self._message_endpoint or "/message"

        try:
            # 发送 HTTP POST
            response = await self._client.post(
                endpoint,
                json=message.to_dict(),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            # 等待 SSE 响应
            result = await asyncio.wait_for(future, timeout=timeout)
            return result

        except httpx.HTTPStatusError as e:
            self._pending_requests.pop(request_id, None)
            raise RuntimeError(f"HTTP request failed: {e}") from e
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise TimeoutError(f"Request {method} timed out after {timeout}s")

    async def send_notification(self, method: str, params: dict | None = None) -> None:
        """发送通知（不等待响应）。"""
        if not self._client:
            raise RuntimeError("Transport not started")

        message = JSONRPCMessage(method=method, params=params)
        endpoint = self._message_endpoint or "/message"

        response = await self._client.post(
            endpoint,
            json=message.to_dict(),
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

    async def _sse_loop(self) -> None:
        """持续监听 SSE 事件。"""
        if not self._client:
            return

        try:
            async with self._client.stream("GET", "/sse") as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not self._running:
                        break

                    await self._process_sse_line(line)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            # 连接错误，通知所有等待的请求
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(
                        RuntimeError(f"SSE connection error: {e}")
                    )
            self._pending_requests.clear()

    async def _process_sse_line(self, line: str) -> None:
        """处理 SSE 行。"""
        line = line.strip()

        if not line:
            return

        # 处理事件类型
        if line.startswith("event:"):
            return  # 忽略事件类型，统一处理

        # 处理数据
        if line.startswith("data:"):
            data_str = line[5:].strip()
            if not data_str:
                return

            try:
                data = json.loads(data_str)

                # 处理 endpoint 事件（MCP 规范）
                if isinstance(data, dict) and "endpoint" in data:
                    self._message_endpoint = data["endpoint"]
                    return

                # 解析 JSON-RPC 消息
                message = JSONRPCMessage.from_dict(data)

                # 处理响应
                if message.id is not None and message.id in self._pending_requests:
                    future = self._pending_requests.pop(message.id)
                    if message.error:
                        future.set_exception(
                            Exception(f"MCP Error: {message.error}")
                        )
                    else:
                        future.set_result(message.result)

            except json.JSONDecodeError:
                # 忽略无效 JSON
                pass

    @property
    def is_running(self) -> bool:
        """检查连接是否活跃。"""
        return self._running and self._client is not None
