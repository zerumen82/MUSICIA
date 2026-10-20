"""Keep the local engine alive until every admitted operation has finished.

The callbacks own process identity and readiness checks. This module only owns
request lifetime and serialization: a lease does not start an engine, and ASGI
background work remains inside the lease until the application returns.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class _OperationLease:
    active: bool = True


class EngineLifecycle:
    """Serialize wake/pause and release the engine after its last operation."""

    def __init__(
        self,
        *,
        enabled: bool,
        wake: Callable[[], Awaitable[None]],
        pause: Callable[[], Awaitable[None]],
    ) -> None:
        self._enabled = enabled
        self._activated = False
        self._wake = wake
        self._pause = pause
        self._lock = asyncio.Lock()
        self._operations = 0
        self._touched = False
        self._awake = False
        self._state = "inactive"
        self._error: str | None = None
        self._context: ContextVar[_OperationLease | None] = ContextVar(
            f"engine_operation_{id(self)}", default=None,
        )

    def activate(self) -> None:
        """Enable coordination once the owning application's lifespan starts."""
        if self._enabled and not self._activated:
            self._activated = True
            self._state = "reconciling"

    def reconcile(self, state: str, error: str | None = None) -> None:
        """Adopt only a supervisor-verified process state after app startup."""
        if not self.active:
            return
        if state == "error":
            self.report_error(error or "The engine process state could not be verified.")
            return
        if state not in {"idle", "awake", "starting", "reconciling"}:
            raise ValueError(f"Invalid engine lifecycle state: {state}")
        if self._operations:
            raise RuntimeError("Cannot reconcile the engine during an active operation")
        self._state = state
        self._error = None
        self._awake = state == "awake"
        self._touched = False

    def deactivate(self) -> None:
        """Stop applying request leases after the owning app shuts down."""
        self._activated = False
        self._awake = False
        self._touched = False
        self._state = "inactive"
        self._error = None

    def report_error(self, detail: str) -> None:
        self._state = "error"
        self._error = detail

    @property
    def active(self) -> bool:
        return self._enabled and self._activated

    @property
    def in_operation(self) -> bool:
        lease = self._context.get()
        return lease is not None and lease.active

    @property
    def state(self) -> str:
        return self._state

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def operation_count(self) -> int:
        return self._operations

    def _record_failure(self, action: str, error: BaseException) -> None:
        self.report_error(f"{action}: {type(error).__name__}: {error}")
        logger.error("Local engine lifecycle {}", self._error)

    async def ensure_awake(self) -> None:
        """Wake on first actual use, never from an unleased health request."""
        if not self.active:
            return
        if not self.in_operation:
            raise RuntimeError("The local engine can only wake inside an operation")
        async with self._lock:
            if self._awake:
                self._touched = True
                return
            # A failed start can still have created a process. Its final lease
            # must attempt cleanup rather than assuming that no GPU was used.
            self._touched = True
            self._state = "starting"
            try:
                await self._wake()
            except BaseException as error:
                self._record_failure("wake", error)
                raise
            self._awake = True
            self._error = None
            self._state = "awake"

    async def _release(self) -> None:
        async with self._lock:
            self._operations -= 1
            if self._operations or not self._touched:
                return
            previous_error = self._error
            self._state = "stopping"
            try:
                await self._pause()
            except BaseException as error:
                self._awake = False
                self._record_failure("pause", error)
                raise
            self._awake = False
            self._touched = False
            # A successful cleanup does not turn a failed startup into success.
            self._state = "error" if previous_error else "idle"

    @asynccontextmanager
    async def operation(self) -> AsyncIterator[None]:
        """Lease the engine through response/background completion and errors."""
        if not self.active:
            yield
            return
        async with self._lock:
            self._operations += 1
        lease = _OperationLease()
        token = self._context.set(lease)
        primary_error: BaseException | None = None
        try:
            yield
        except BaseException as error:
            primary_error = error
            raise
        finally:
            # Child tasks inherit context variables, but cannot reuse a lease
            # after its owning request/background application has returned.
            lease.active = False
            self._context.reset(token)
            # A disconnected/cancelled request must not cancel process cleanup.
            cleanup = asyncio.create_task(self._release())
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError as error:
                    if primary_error is None:
                        primary_error = error
                except BaseException:
                    break
            try:
                cleanup.result()
            except BaseException:
                if primary_error is None:
                    raise
            if isinstance(primary_error, asyncio.CancelledError):
                raise primary_error


class EngineLifecycleMiddleware:
    """Pure ASGI middleware: the lease includes Starlette BackgroundTasks."""

    def __init__(
        self, app: Any, lifecycle: EngineLifecycle, paths: tuple[str, ...],
    ) -> None:
        self.app = app
        self.lifecycle = lifecycle
        self.paths = frozenset(paths)

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"] in self.paths
            and self.lifecycle.active
        ):
            async with self.lifecycle.operation():
                await self.app(scope, receive, send)
        else:
            await self.app(scope, receive, send)
