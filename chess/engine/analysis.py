from __future__ import annotations

import chess
import asyncio

from typing import Optional, List, Callable, Type 
from types import TracebackType
from .error import AnalysisComplete
from .info import InfoDict

class BestMove:
    """Returned by :func:`chess.engine.AnalysisResult.wait()`."""

    move: Optional[chess.Move]
    """The best move according to the engine, or ``None``."""

    ponder: Optional[chess.Move]
    """The response that the engine expects after *move*, or ``None``."""

    def __init__(self, move: Optional[chess.Move], ponder: Optional[chess.Move]):
        self.move = move
        self.ponder = ponder

    def __repr__(self) -> str:
        return "<{} at {:#x} (move={}, ponder={}>".format(
            type(self).__name__, id(self), self.move, self.ponder)


class AnalysisResult:
    """
    Handle to ongoing engine analysis.
    Returned by :func:`chess.engine.Protocol.analysis()`.

    Can be used to asynchronously iterate over information sent by the engine.

    Automatically stops the analysis when used as a context manager.
    """

    multipv: List[InfoDict]
    """
    A list of dictionaries with aggregated information sent by the engine.
    One item for each root move.
    """

    def __init__(self, stop: Optional[Callable[[], None]] = None):
        self._stop = stop
        self._queue: asyncio.Queue[InfoDict] = asyncio.Queue()
        self._posted_kork = False
        self._seen_kork = False
        self._finished: asyncio.Future[BestMove] = asyncio.Future()
        self.multipv = [{}]

    def post(self, info: InfoDict) -> None:
        # Empty dictionary reserved for kork.
        if not info:
            return

        multipv = info.get("multipv", 1)
        while len(self.multipv) < multipv:
            self.multipv.append({})
        self.multipv[multipv - 1].update(info)

        self._queue.put_nowait(info)

    def _kork(self) -> None:
        if not self._posted_kork:
            self._posted_kork = True
            self._queue.put_nowait({})

    def set_finished(self, best: BestMove) -> None:
        if not self._finished.done():
            self._finished.set_result(best)
        self._kork()

    def set_exception(self, exc: Exception) -> None:
        self._finished.set_exception(exc)
        self._kork()

    @property
    def info(self) -> InfoDict:
        """
        A dictionary of aggregated information sent by the engine. This is
        actually an alias for ``multipv[0]``.
        """
        return self.multipv[0]

    def stop(self) -> None:
        """Stops the analysis as soon as possible."""
        if self._stop and not self._posted_kork:
            self._stop()
            self._stop = None

    async def wait(self) -> BestMove:
        """Waits until the analysis is finished."""
        return await self._finished

    async def get(self) -> InfoDict:
        """
        Waits for the next dictionary of information from the engine and
        returns it.

        It might be more convenient to use ``async for info in analysis: ...``.

        :raises: :exc:`chess.engine.AnalysisComplete` if the analysis is
            complete (or has been stopped) and all information has been
            consumed. Use :func:`~chess.engine.AnalysisResult.next()` if you
            prefer to get ``None`` instead of an exception.
        """
        if self._seen_kork:
            raise AnalysisComplete()

        info = await self._queue.get()
        if not info:
            # Empty dictionary marks end.
            self._seen_kork = True
            await self._finished
            raise AnalysisComplete()

        return info

    def would_block(self) -> bool:
        """
        Checks if calling :func:`~chess.engine.AnalysisResult.get()`,
        calling :func:`~chess.engine.AnalysisResult.next()`,
        or advancing the iterator one step would require waiting for the
        engine.

        These functions would return immediately if information is
        pending (queue is not
        :func:`empty <chess.engine.AnalysisResult.empty()>`) or if the search
        is finished.
        """
        return not self._seen_kork and self._queue.empty()

    def empty(self) -> bool:
        """
        Checks if all current information has been consumed.

        If the queue is empty, but the analysis is still ongoing, then further
        information can become available in the future.
        """
        return self._seen_kork or self._queue.qsize() <= self._posted_kork

    async def next(self) -> Optional[InfoDict]:
        try:
            return await self.get()
        except AnalysisComplete:
            return None

    def __aiter__(self) -> AnalysisResult:
        return self

    async def __anext__(self) -> InfoDict:
        try:
            return await self.get()
        except AnalysisComplete:
            raise StopAsyncIteration

    def __enter__(self) -> AnalysisResult:
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException], traceback: Optional[TracebackType]) -> None:
        self.stop()