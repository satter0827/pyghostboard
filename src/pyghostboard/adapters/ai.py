"""Safe subprocess adapter for external AI agents."""

from __future__ import annotations

import asyncio
import os
import signal
from collections.abc import Sequence
from contextlib import suppress

from pydantic import ValidationError

from pyghostboard._platform import require_posix
from pyghostboard.protocol import AgentRequest, AgentResponse, response_adapter


class AgentFailure(RuntimeError):
    """Raised for protocol, timeout, or process failures."""


class SubprocessAgent:
    def __init__(
        self,
        command: Sequence[str],
        *,
        timeout: float = 10.0,
        max_message_bytes: int = 1_048_576,
        max_stderr_bytes: int = 65_536,
    ) -> None:
        if not command:
            raise ValueError("agent command cannot be empty")
        if timeout <= 0 or max_message_bytes <= 0 or max_stderr_bytes < 0:
            raise ValueError("agent limits must be positive")
        self._command = tuple(command)
        self._timeout = timeout
        self._max_message_bytes = max_message_bytes
        self._max_stderr_bytes = max_stderr_bytes
        self._process: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._request_lock = asyncio.Lock()
        self.stderr = bytearray()

    async def __aenter__(self) -> SubprocessAgent:
        require_posix("AI process isolation")
        if self._process is not None:
            raise AgentFailure("agent process is already running")
        self._process = await asyncio.create_subprocess_exec(
            *self._command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=self._max_message_bytes + 1,
            start_new_session=True,
        )
        self.stderr.clear()
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def request(self, request: AgentRequest) -> AgentResponse:
        async with self._request_lock:
            return await self._request(request)

    async def _request(self, request: AgentRequest) -> AgentResponse:
        process = self._require_process()
        if process.returncode is not None:
            raise AgentFailure(f"agent process exited with status {process.returncode}")
        assert process.stdin is not None
        assert process.stdout is not None
        message = request.model_dump_json().encode("utf-8") + b"\n"
        if len(message) > self._max_message_bytes:
            raise AgentFailure("agent request exceeded the size limit")
        try:
            process.stdin.write(message)
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as error:
            raise AgentFailure("agent process closed its input") from error
        try:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=self._timeout)
        except TimeoutError as error:
            raise AgentFailure("agent response timed out") from error
        except ValueError as error:
            raise AgentFailure("agent response exceeded the size limit") from error
        if not line:
            raise AgentFailure(f"agent exited before responding: {process.returncode}")
        if len(line) > self._max_message_bytes:
            raise AgentFailure("agent response exceeded the size limit")
        try:
            response = response_adapter.validate_json(line)
        except ValidationError as error:
            raise AgentFailure("agent returned an invalid response") from error
        if response.request_id != request.request_id:
            raise AgentFailure("agent response request_id does not match")
        return response

    async def close(self) -> None:
        process = self._process
        if process is None:
            return
        if process.stdin is not None:
            process.stdin.close()
        self._terminate_process_group(process, signal.SIGTERM)
        if process.returncode is None:
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except TimeoutError:
                self._terminate_process_group(process, signal.SIGKILL)
                await process.wait()
        self._terminate_process_group(process, signal.SIGKILL)
        if self._stderr_task is not None:
            await self._stderr_task
        self._process = None
        self._stderr_task = None

    @staticmethod
    def _terminate_process_group(
        process: asyncio.subprocess.Process, signal_number: signal.Signals
    ) -> None:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal_number)

    async def _drain_stderr(self) -> None:
        process = self._require_process()
        assert process.stderr is not None
        while chunk := await process.stderr.read(4096):
            remaining = self._max_stderr_bytes - len(self.stderr)
            if remaining > 0:
                self.stderr.extend(chunk[:remaining])

    def _require_process(self) -> asyncio.subprocess.Process:
        if self._process is None:
            raise AgentFailure("agent process is not running")
        return self._process
