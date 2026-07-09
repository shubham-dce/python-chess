from __future__ import annotations

import asyncio
import threading
import concurrent.futures
import contextlib
import typing
import copy

import chess
from chess import Color

from .protocol import Protocol
from .error import *
from .base_command import BaseCommand
from .info import *
from .utils import T, ConfigMapping, run_in_background
from .info import Opponent, InfoDict, PlayResult, INFO_ALL, INFO_NONE, Option, Limit
from .analysis import AnalysisResult, BestMove
from .uci import UciProtocol
from .xboard import XBoardProtocol

from types import TracebackType
from typing import Optional, Generator, MutableMapping, Mapping, Callable, List, Type, Iterable, Union, Any, Iterator

class SimpleEngine:
    """
    Synchronous wrapper around a transport and engine protocol pair. Provides
    the same methods and attributes as :class:`chess.engine.Protocol`
    with blocking functions instead of coroutines.

    You may not concurrently modify objects passed to any of the methods. Other
    than that, :class:`~chess.engine.SimpleEngine` is thread-safe. When sending
    a new command to the engine, any previous running command will be cancelled
    as soon as possible.

    Methods will raise :class:`asyncio.TimeoutError` if an operation takes
    *timeout* seconds longer than expected (unless *timeout* is ``None``).

    Automatically closes the transport when used as a context manager.
    """

    def __init__(self, transport: asyncio.SubprocessTransport, protocol: Protocol, *, timeout: Optional[float] = 10.0) -> None:
        self.transport = transport
        self.protocol = protocol
        self.timeout = timeout

        self._shutdown_lock = threading.Lock()
        self._shutdown = False
        self.shutdown_event = asyncio.Event()

        self.returncode: concurrent.futures.Future[int] = concurrent.futures.Future()

    def _timeout_for(self, limit: Optional[Limit]) -> Optional[float]:
        if self.timeout is None or limit is None or limit.time is None:
            return None
        return self.timeout + limit.time

    @contextlib.contextmanager
    def _not_shut_down(self) -> Generator[None, None, None]:
        with self._shutdown_lock:
            if self._shutdown:
                raise EngineTerminatedError("engine event loop dead")
            yield

    @property
    def options(self) -> MutableMapping[str, Option]:
        with self._not_shut_down():
            coro = _async(lambda: copy.copy(self.protocol.options))
            future = asyncio.run_coroutine_threadsafe(coro, self.protocol.loop)
        return future.result()

    @property
    def id(self) -> Mapping[str, str]:
        with self._not_shut_down():
            coro = _async(lambda: self.protocol.id.copy())
            future = asyncio.run_coroutine_threadsafe(coro, self.protocol.loop)
        return future.result()

    def communicate(self, command_factory: Callable[[Protocol], BaseCommand[T]]) -> T:
        with self._not_shut_down():
            coro = self.protocol.communicate(command_factory)
            future = asyncio.run_coroutine_threadsafe(coro, self.protocol.loop)
        return future.result()

    def configure(self, options: ConfigMapping) -> None:
        with self._not_shut_down():
            coro = asyncio.wait_for(self.protocol.configure(options), self.timeout)
            future = asyncio.run_coroutine_threadsafe(coro, self.protocol.loop)
        return future.result()

    def send_opponent_information(self, *, opponent: Optional[Opponent] = None, engine_rating: Optional[int] = None) -> None:
        with self._not_shut_down():
            coro = asyncio.wait_for(
                self.protocol.send_opponent_information(opponent=opponent, engine_rating=engine_rating),
                self.timeout)
            future = asyncio.run_coroutine_threadsafe(coro, self.protocol.loop)
        return future.result()

    def ping(self) -> None:
        with self._not_shut_down():
            coro = asyncio.wait_for(self.protocol.ping(), self.timeout)
            future = asyncio.run_coroutine_threadsafe(coro, self.protocol.loop)
        return future.result()

    def play(self, board: chess.Board, limit: Limit, *, game: object = None, info: Info = INFO_NONE, ponder: bool = False, draw_offered: bool = False, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}, opponent: Optional[Opponent] = None) -> PlayResult:
        with self._not_shut_down():
            coro = asyncio.wait_for(
                self.protocol.play(board, limit, game=game, info=info, ponder=ponder, draw_offered=draw_offered, root_moves=root_moves, options=options, opponent=opponent),
                self._timeout_for(limit))
            future = asyncio.run_coroutine_threadsafe(coro, self.protocol.loop)
        return future.result()

    @typing.overload
    def analyse(self, board: chess.Board, limit: Limit, *, game: object = None, info: Info = INFO_ALL, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}) -> InfoDict: ...
    @typing.overload
    def analyse(self, board: chess.Board, limit: Limit, *, multipv: int, game: object = None, info: Info = INFO_ALL, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}) -> List[InfoDict]: ...
    @typing.overload
    def analyse(self, board: chess.Board, limit: Limit, *, multipv: Optional[int] = None, game: object = None, info: Info = INFO_ALL, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}) -> Union[InfoDict, List[InfoDict]]: ...
    def analyse(self, board: chess.Board, limit: Limit, *, multipv: Optional[int] = None, game: object = None, info: Info = INFO_ALL, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}) -> Union[InfoDict, List[InfoDict]]:
        with self._not_shut_down():
            coro = asyncio.wait_for(
                self.protocol.analyse(board, limit, multipv=multipv, game=game, info=info, root_moves=root_moves, options=options),
                self._timeout_for(limit))
            future = asyncio.run_coroutine_threadsafe(coro, self.protocol.loop)
        return future.result()

    def analysis(self, board: chess.Board, limit: Optional[Limit] = None, *, multipv: Optional[int] = None, game: object = None, info: Info = INFO_ALL, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}) -> SimpleAnalysisResult:
        with self._not_shut_down():
            coro = asyncio.wait_for(
                self.protocol.analysis(board, limit, multipv=multipv, game=game, info=info, root_moves=root_moves, options=options),
                self.timeout)  # Timeout until analysis is *started*
            future = asyncio.run_coroutine_threadsafe(coro, self.protocol.loop)
        return SimpleAnalysisResult(self, future.result())

    def send_game_result(self, board: chess.Board, winner: Optional[Color] = None, game_ending: Optional[str] = None, game_complete: bool = True) -> None:
        with self._not_shut_down():
            coro = asyncio.wait_for(self.protocol.send_game_result(board, winner, game_ending, game_complete), self.timeout)
            future = asyncio.run_coroutine_threadsafe(coro, self.protocol.loop)
        return future.result()

    def quit(self) -> None:
        with self._not_shut_down():
            coro = asyncio.wait_for(self.protocol.quit(), self.timeout)
            future = asyncio.run_coroutine_threadsafe(coro, self.protocol.loop)
        return future.result()

    def close(self) -> None:
        """
        Closes the transport and the background event loop as soon as possible.
        """
        def _shutdown() -> None:
            self.transport.close()
            self.shutdown_event.set()

        with self._shutdown_lock:
            if not self._shutdown:
                self._shutdown = True
                self.protocol.loop.call_soon_threadsafe(_shutdown)

    @classmethod
    def popen(cls, Protocol: Type[Protocol], command: Union[str, List[str]], *, timeout: Optional[float] = 10.0, debug: Optional[bool] = None, setpgrp: bool = False, **popen_args: Any) -> SimpleEngine:
        async def background(future: concurrent.futures.Future[SimpleEngine]) -> None:
            transport, protocol = await Protocol.popen(command, setpgrp=setpgrp, **popen_args)
            threading.current_thread().name = f"{cls.__name__} (pid={transport.get_pid()})"
            simple_engine = cls(transport, protocol, timeout=timeout)
            try:
                await asyncio.wait_for(protocol.initialize(), timeout)
                future.set_result(simple_engine)
                returncode = await protocol.returncode
                simple_engine.returncode.set_result(returncode)
            finally:
                simple_engine.close()
            await simple_engine.shutdown_event.wait()

        return run_in_background(background, name=f"{cls.__name__} (command={command!r})", debug=debug)

    @classmethod
    def popen_uci(cls, command: Union[str, List[str]], *, timeout: Optional[float] = 10.0, debug: Optional[bool] = None, setpgrp: bool = False, **popen_args: Any) -> SimpleEngine:
        """
        Spawns and initializes a UCI engine.
        Returns a :class:`~chess.engine.SimpleEngine` instance.
        """
        return cls.popen(UciProtocol, command, timeout=timeout, debug=debug, setpgrp=setpgrp, **popen_args)

    @classmethod
    def popen_xboard(cls, command: Union[str, List[str]], *, timeout: Optional[float] = 10.0, debug: Optional[bool] = None, setpgrp: bool = False, **popen_args: Any) -> SimpleEngine:
        """
        Spawns and initializes an XBoard engine.
        Returns a :class:`~chess.engine.SimpleEngine` instance.
        """
        return cls.popen(XBoardProtocol, command, timeout=timeout, debug=debug, setpgrp=setpgrp, **popen_args)

    def __enter__(self) -> SimpleEngine:
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException], traceback: Optional[TracebackType]) -> None:
        self.close()

    def __repr__(self) -> str:
        pid = self.transport.get_pid()  # This happens to be thread-safe
        return f"<{type(self).__name__} (pid={pid})>"


class SimpleAnalysisResult:
    """
    Synchronous wrapper around :class:`~chess.engine.AnalysisResult`. Returned
    by :func:`chess.engine.SimpleEngine.analysis()`.
    """

    def __init__(self, simple_engine: SimpleEngine, inner: AnalysisResult) -> None:
        self.simple_engine = simple_engine
        self.inner = inner

    @property
    def info(self) -> InfoDict:
        with self.simple_engine._not_shut_down():
            coro = _async(lambda: self.inner.info.copy())
            future = asyncio.run_coroutine_threadsafe(coro, self.simple_engine.protocol.loop)
        return future.result()

    @property
    def multipv(self) -> List[InfoDict]:
        with self.simple_engine._not_shut_down():
            coro = _async(lambda: [info.copy() for info in self.inner.multipv])
            future = asyncio.run_coroutine_threadsafe(coro, self.simple_engine.protocol.loop)
        return future.result()

    def stop(self) -> None:
        with self.simple_engine._not_shut_down():
            self.simple_engine.protocol.loop.call_soon_threadsafe(self.inner.stop)

    def wait(self) -> BestMove:
        with self.simple_engine._not_shut_down():
            future = asyncio.run_coroutine_threadsafe(self.inner.wait(), self.simple_engine.protocol.loop)
        return future.result()

    def would_block(self) -> bool:
        with self.simple_engine._not_shut_down():
            future = asyncio.run_coroutine_threadsafe(_async(self.inner.would_block), self.simple_engine.protocol.loop)
        return future.result()

    def empty(self) -> bool:
        with self.simple_engine._not_shut_down():
            future = asyncio.run_coroutine_threadsafe(_async(self.inner.empty), self.simple_engine.protocol.loop)
        return future.result()

    def get(self) -> InfoDict:
        with self.simple_engine._not_shut_down():
            future = asyncio.run_coroutine_threadsafe(self.inner.get(), self.simple_engine.protocol.loop)
        return future.result()

    def next(self) -> Optional[InfoDict]:
        with self.simple_engine._not_shut_down():
            future = asyncio.run_coroutine_threadsafe(self.inner.next(), self.simple_engine.protocol.loop)
        return future.result()

    def __iter__(self) -> Iterator[InfoDict]:
        with self.simple_engine._not_shut_down():
            self.simple_engine.protocol.loop.call_soon_threadsafe(self.inner.__aiter__)
        return self

    def __next__(self) -> InfoDict:
        try:
            with self.simple_engine._not_shut_down():
                future = asyncio.run_coroutine_threadsafe(self.inner.__anext__(), self.simple_engine.protocol.loop)
            return future.result()
        except StopAsyncIteration:
            raise StopIteration

    def __enter__(self) -> SimpleAnalysisResult:
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException], traceback: Optional[TracebackType]) -> None:
        self.stop()

async def _async(sync: Callable[[], T]) -> T:
    return sync()