import enum
import asyncio

from .protocol import Protocol
from .error import EngineError, EngineTerminatedError
from .utils import T

from typing import Generic, List, Callable


class CommandState(enum.Enum):
    NEW = enum.auto()
    ACTIVE = enum.auto()
    CANCELLING = enum.auto()
    DONE = enum.auto()


class BaseCommand(Generic[T]):
    def __init__(self, engine: Protocol) -> None:
        self._engine = engine

        self.state = CommandState.NEW

        self.result: asyncio.Future[T] = asyncio.Future()
        self.finished: asyncio.Future[None] = asyncio.Future()

        self._finished_callbacks: List[Callable[[], None]] = []

    def add_finished_callback(self, callback: Callable[[], None]) -> None:
        self._finished_callbacks.append(callback)
        self._dispatch_finished()

    def _dispatch_finished(self) -> None:
        if self.finished.done():
            while self._finished_callbacks:
                self._finished_callbacks.pop()()

    def _engine_terminated(self, code: int) -> None:
        hint = ", binary not compatible with cpu?" if code in [-4, 0xc000001d] else ""
        exc = EngineTerminatedError(f"engine process died unexpectedly (exit code: {code}{hint})")
        if self.state == CommandState.ACTIVE:
            self.engine_terminated(exc)
        elif self.state == CommandState.CANCELLING:
            self.finished.set_result(None)
            self._dispatch_finished()
        elif self.state == CommandState.NEW:
            self._handle_exception(exc)

    def _handle_exception(self, exc: Exception) -> None:
        if not self.result.done():
            self.result.set_exception(exc)
        else:
            self._engine.loop.call_exception_handler({ # XXX
                "message": f"{type(self).__name__} failed after returning preliminary result ({self.result!r})",
                "exception": exc,
                "protocol": self._engine,
                "transport": self._engine.transport,
            })

        if not self.finished.done():
            self.finished.set_result(None)
            self._dispatch_finished()

    def set_finished(self) -> None:
        assert self.state in [CommandState.ACTIVE, CommandState.CANCELLING], self.state
        if not self.result.done():
            self.result.set_exception(EngineError(f"engine command finished before returning result: {self!r}"))
        self.state = CommandState.DONE
        self.finished.set_result(None)
        self._dispatch_finished()

    def _cancel(self) -> None:
        if self.state != CommandState.CANCELLING and self.state != CommandState.DONE:
            assert self.state == CommandState.ACTIVE, self.state
            self.state = CommandState.CANCELLING
            self.cancel()

    def _start(self) -> None:
        assert self.state == CommandState.NEW, self.state
        self.state = CommandState.ACTIVE
        try:
            self.check_initialized()
            self.start()
        except EngineError as err:
            self._handle_exception(err)

    def _line_received(self, line: str) -> None:
        assert self.state in [CommandState.ACTIVE, CommandState.CANCELLING], self.state
        try:
            self.line_received(line)
        except EngineError as err:
            self._handle_exception(err)

    def cancel(self) -> None:
        pass

    def check_initialized(self) -> None:
        if not self._engine.initialized:
            raise EngineError("tried to run command, but engine is not initialized")

    def start(self) -> None:
        raise NotImplementedError

    def line_received(self, line: str) -> None:
        pass

    def engine_terminated(self, exc: Exception) -> None:
        self._handle_exception(exc)

    def __repr__(self) -> str:
        return "<{} at {:#x} (state={}, result={}, finished={}>".format(type(self).__name__, id(self), self.state, self.result, self.finished)