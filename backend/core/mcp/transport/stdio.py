"""STDIO Transport 实现。

通过标准输入/输出与本地 MCP Server 进程通信。
"""

import asyncio
import json
import os
from typing import Any

from backend.core.mcp.types import BaseTransport, JSONRPCMessage, MCPServerConfig


class STDIOTransport(BaseTransport):
    """STDIO 传输层。

    启动子进程并通过 stdin/stdout 进行 JSON-RPC 通信。
    """

    def __init__(self, config: MCPServerConfig):
        super().__init__(config)
        self.process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None

    async def start(self) -> None:
        """启动 MCP Server 进程。"""
        if not self.config.command:
            raise ValueError(f"No command specified for STDIO transport: {self.config.name}")

        # 构建环境变量
        env = dict(os.environ)
        env.update(self.config.env)

        # 启动子进程
        self.process = await asyncio.create_subprocess_exec(
            self.config.command,
            *self.config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # 启动后台读取任务
        self._reader_task = asyncio.create_task(self._read_loop())

    async def stop(self) -> None:
        """停止 MCP Server 进程。"""
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None

        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
            self.process = None

    async def send_request(
        self,
        method: str,
        params: dict | None = None,
        timeout: float = 30.0,
    ) -> Any:
        """发送请求并等待响应。"""
        if not self.process or not self.process.stdin:
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

        # 发送消息
        line = json.dumps(message.to_dict()) + "\n"
        self.process.stdin.write(line.encode("utf-8"))
        await self.process.stdin.drain()

        # 等待响应
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise TimeoutError(f"Request {method} timed out after {timeout}s")

    async def send_notification(self, method: str, params: dict | None = None) -> None:
        """发送通知（不等待响应）。"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Transport not started")

        message = JSONRPCMessage(method=method, params=params)
        line = json.dumps(message.to_dict()) + "\n"
        self.process.stdin.write(line.encode("utf-8"))
        await self.process.stdin.drain()

    async def _read_loop(self) -> None:
        """持续读取响应。"""
        if not self.process or not self.process.stdout:
            return

        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break

                try:
                    data = json.loads(line.decode("utf-8").strip())
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

        except asyncio.CancelledError:
            pass

    @property
    def is_running(self) -> bool:
        """检查进程是否在运行。"""
        return self.process is not None and self.process.returncode is None
