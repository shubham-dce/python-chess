from __future__ import annotations

import asyncio
import abc
import typing
import sys
import subprocess

import chess
from chess import Color

from .error import *
from .info import Info, INFO_ALL, INFO_NONE

from typing import Dict, Optional, Any, Union, Callable, Self, Type, List, MutableMapping, Iterable, Tuple, TypeVar

from .utils import T, ConfigMapping, LOGGER
from .info import Limit, InfoDict, Opponent, PlayResult, Option
from .analysis import AnalysisResult

if typing.TYPE_CHECKING:
    from .base_command import BaseCommand
    from .utils import ProtocolT

# ProtocolT = TypeVar("ProtocolT", bound="Protocol")

class Protocol(asyncio.SubprocessProtocol, metaclass=abc.ABCMeta):
    """Protocol for communicating with a chess engine process."""

    id: Dict[str, str]
    """
    Dictionary of information about the engine. Common keys are ``name``
    and ``author``.
    """

    returncode: asyncio.Future[int]
    """Future: Exit code of the process."""

    

    def __init__(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.transport: Optional[asyncio.SubprocessTransport] = None

        self.buffer = {
            1: bytearray(),  # stdout
            2: bytearray(),  # stderr
        }

        self.command: Optional[BaseCommand[Any]] = None
        self.next_command: Optional[BaseCommand[Any]] = None

        self.initialized = False
        self.returncode: asyncio.Future[int] = asyncio.Future()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        # SubprocessTransport expected, but not checked to allow duck typing.
        self.transport = transport  # type: ignore
        LOGGER.debug("%s: Connection made", self)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        assert self.transport is not None
        code = self.transport.get_returncode()
        assert code is not None, "connect lost, but got no returncode"
        LOGGER.debug("%s: Connection lost (exit code: %d, error: %s)", self, code, exc)

        # Terminate commands.
        command, self.command = self.command, None
        next_command, self.next_command = self.next_command, None
        if command:
            command._engine_terminated(code)
        if next_command:
            next_command._engine_terminated(code)

        self.returncode.set_result(code)

    def process_exited(self) -> None:
        LOGGER.debug("%s: Process exited", self)

    def send_line(self, line: str) -> None:
        LOGGER.debug("%s: << %s", self, line)
        assert self.transport is not None, "cannot send line before connection is made"
        stdin = self.transport.get_pipe_transport(0)
        # WriteTransport expected, but not checked to allow duck typing.
        stdin.write((line + "\n").encode("utf-8"))  # type: ignore

    def pipe_data_received(self, fd: int, data: Union[bytes, str]) -> None:
        self.buffer[fd].extend(data)  # type: ignore
        while b"\n" in self.buffer[fd]:
            line_bytes, self.buffer[fd] = self.buffer[fd].split(b"\n", 1)
            if line_bytes.endswith(b"\r"):
                line_bytes = line_bytes[:-1]
            try:
                line = line_bytes.decode("utf-8")
            except UnicodeDecodeError as err:
                LOGGER.warning("%s: >> %r (%s)", self, bytes(line_bytes), err)
            else:
                if fd == 1:
                    self._line_received(line)
                else:
                    self.error_line_received(line)

    def error_line_received(self, line: str) -> None:
        LOGGER.warning("%s: stderr >> %s", self, line)

    def _line_received(self, line: str) -> None:
        LOGGER.debug("%s: >> %s", self, line)

        self.line_received(line)

        if self.command:
            self.command._line_received(line)

    def line_received(self, line: str) -> None:
        pass

    async def communicate(self, command_factory: Callable[[Self], BaseCommand[T]]) -> T:
        from .base_command import CommandState
        command = command_factory(self)

        if self.returncode.done():
            raise EngineTerminatedError(f"engine process dead (exit code: {self.returncode.result()})")

        assert command.state == CommandState.NEW, command.state

        if self.next_command is not None:
            self.next_command.result.cancel()
            self.next_command.finished.cancel()
            self.next_command.set_finished()

        self.next_command = command

        def previous_command_finished() -> None:
            self.command, self.next_command = self.next_command, None
            if self.command is not None:
                cmd = self.command

                def cancel_if_cancelled(result: asyncio.Future[T]) -> None:
                    if result.cancelled():
                        cmd._cancel()

                cmd.result.add_done_callback(cancel_if_cancelled)
                cmd._start()
                cmd.add_finished_callback(previous_command_finished)

        if self.command is None:
            previous_command_finished()
        elif not self.command.result.done():
            self.command.result.cancel()
        elif not self.command.result.cancelled():
            self.command._cancel()

        return await command.result

    def __repr__(self) -> str:
        pid = self.transport.get_pid() if self.transport is not None else "?"
        return f"<{type(self).__name__} (pid={pid})>"

    @property
    @abc.abstractmethod
    def options(self) -> MutableMapping[str, Option]:
        """Dictionary of available options."""

    @abc.abstractmethod
    async def initialize(self) -> None:
        """Initializes the engine."""

    @abc.abstractmethod
    async def ping(self) -> None:
        """
        Pings the engine and waits for a response. Used to ensure the engine
        is still alive and idle.
        """

    @abc.abstractmethod
    async def configure(self, options: ConfigMapping) -> None:
        """
        Configures global engine options.

        :param options: A dictionary of engine options where the keys are
            names of :data:`~chess.engine.Protocol.options`. Do not set options
            that are managed automatically
            (:func:`chess.engine.Option.is_managed()`).
        """

    @abc.abstractmethod
    async def send_opponent_information(self, *, opponent: Optional[Opponent] = None, engine_rating: Optional[int] = None) -> None:
        """
        Sends the engine information about its opponent. The information will
        be sent after a new game is announced and before the first move. This
        method should be called before the first move of a game--i.e., the
        first call to :func:`chess.engine.Protocol.play()`.

        :param opponent: Optional. An instance of :class:`chess.engine.Opponent` that has the opponent's information.
        :param engine_rating: Optional. This engine's own rating. Only used by XBoard engines.
        """

    @abc.abstractmethod
    async def play(self, board: chess.Board, limit: Limit, *, game: object = None, info: Info = INFO_NONE, ponder: bool = False, draw_offered: bool = False, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}, opponent: Optional[Opponent] = None) -> PlayResult:
        """
        Plays a position.

        :param board: The position. The entire move stack will be sent to the
            engine.
        :param limit: An instance of :class:`chess.engine.Limit` that
            determines when to stop thinking.
        :param game: Optional. An arbitrary object that identifies the game.
            Will automatically inform the engine if the object is not equal
            to the previous game (e.g., ``ucinewgame``, ``new``).
        :param info: Selects which additional information to retrieve from the
            engine. ``INFO_NONE``, ``INFO_BASIC`` (basic information that is
            trivial to obtain), ``INFO_SCORE``, ``INFO_PV``,
            ``INFO_REFUTATION``, ``INFO_CURRLINE``, ``INFO_ALL`` or any
            bitwise combination. Some overhead is associated with parsing
            extra information.
        :param ponder: Whether the engine should keep analysing in the
            background even after the result has been returned.
        :param draw_offered: Whether the engine's opponent has offered a draw.
            Ignored by UCI engines.
        :param root_moves: Optional. Consider only root moves from this list.
        :param options: Optional. A dictionary of engine options for the
            analysis. The previous configuration will be restored after the
            analysis is complete. You can permanently apply a configuration
            with :func:`~chess.engine.Protocol.configure()`.
        :param opponent: Optional. Information about a new opponent. Information
            about the original opponent will be restored once the move is
            complete. New opponent information can be made permanent with
            :func:`~chess.engine.Protocol.send_opponent_information()`.
        """

    @typing.overload
    async def analyse(self, board: chess.Board, limit: Limit, *, game: object = None, info: Info = INFO_ALL, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}) -> InfoDict: ...
    @typing.overload
    async def analyse(self, board: chess.Board, limit: Limit, *, multipv: int, game: object = None, info: Info = INFO_ALL, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}) -> List[InfoDict]: ...
    @typing.overload
    async def analyse(self, board: chess.Board, limit: Limit, *, multipv: Optional[int] = None, game: object = None, info: Info = INFO_ALL, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}) -> Union[List[InfoDict], InfoDict]: ...
    async def analyse(self, board: chess.Board, limit: Limit, *, multipv: Optional[int] = None, game: object = None, info: Info = INFO_ALL, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}) -> Union[List[InfoDict], InfoDict]:
        """
        Analyses a position and returns a dictionary of
        :class:`information <chess.engine.InfoDict>`.

        :param board: The position to analyse. The entire move stack will be
            sent to the engine.
        :param limit: An instance of :class:`chess.engine.Limit` that
            determines when to stop the analysis.
        :param multipv: Optional. Analyse multiple root moves. Will return
            a list of at most *multipv* dictionaries rather than just a single
            info dictionary.
        :param game: Optional. An arbitrary object that identifies the game.
            Will automatically inform the engine if the object is not equal
            to the previous game (e.g., ``ucinewgame``, ``new``).
        :param info: Selects which information to retrieve from the
            engine. ``INFO_NONE``, ``INFO_BASIC`` (basic information that is
            trivial to obtain), ``INFO_SCORE``, ``INFO_PV``,
            ``INFO_REFUTATION``, ``INFO_CURRLINE``, ``INFO_ALL`` or any
            bitwise combination. Some overhead is associated with parsing
            extra information.
        :param root_moves: Optional. Limit analysis to a list of root moves.
        :param options: Optional. A dictionary of engine options for the
            analysis. The previous configuration will be restored after the
            analysis is complete. You can permanently apply a configuration
            with :func:`~chess.engine.Protocol.configure()`.
        """
        analysis = await self.analysis(board, limit, multipv=multipv, game=game, info=info, root_moves=root_moves, options=options)

        with analysis:
            await analysis.wait()

        return analysis.info if multipv is None else analysis.multipv

    @abc.abstractmethod
    async def analysis(self, board: chess.Board, limit: Optional[Limit] = None, *, multipv: Optional[int] = None, game: object = None, info: Info = INFO_ALL, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}) -> AnalysisResult:
        """
        Starts analysing a position.

        :param board: The position to analyse. The entire move stack will be
            sent to the engine.
        :param limit: Optional. An instance of :class:`chess.engine.Limit`
            that determines when to stop the analysis. Analysis is infinite
            by default.
        :param multipv: Optional. Analyse multiple root moves.
        :param game: Optional. An arbitrary object that identifies the game.
            Will automatically inform the engine if the object is not equal
            to the previous game (e.g., ``ucinewgame``, ``new``).
        :param info: Selects which information to retrieve from the
            engine. ``INFO_NONE``, ``INFO_BASIC`` (basic information that is
            trivial to obtain), ``INFO_SCORE``, ``INFO_PV``,
            ``INFO_REFUTATION``, ``INFO_CURRLINE``, ``INFO_ALL`` or any
            bitwise combination. Some overhead is associated with parsing
            extra information.
        :param root_moves: Optional. Limit analysis to a list of root moves.
        :param options: Optional. A dictionary of engine options for the
            analysis. The previous configuration will be restored after the
            analysis is complete. You can permanently apply a configuration
            with :func:`~chess.engine.Protocol.configure()`.

        Returns :class:`~chess.engine.AnalysisResult`, a handle that allows
        asynchronously iterating over the information sent by the engine
        and stopping the analysis at any time.
        """

    @abc.abstractmethod
    async def send_game_result(self, board: chess.Board, winner: Optional[Color] = None, game_ending: Optional[str] = None, game_complete: bool = True) -> None:
        """
        Sends the engine the result of the game.

        XBoard engines receive the final moves and a line of the form
        ``result <winner> {<ending>}``. The ``<winner>`` field is one of ``1-0``,
        ``0-1``, ``1/2-1/2``, or ``*`` to indicate white won, black won, draw,
        or adjournment, respectively. The ``<ending>`` field is a description
        of the specific reason for the end of the game: "White mates",
        "Time forfeiture", "Stalemate", etc.

        UCI engines do not expect end-of-game information and so are not
        sent anything.

        :param board: The final state of the board.
        :param winner: Optional. Specify the winner of the game. This is useful
            if the result of the game is not evident from the board--e.g., time
            forfeiture or draw by agreement. If not ``None``, this parameter
            overrides any winner derivable from the board.
        :param game_ending: Optional. Text describing the reason for the game
            ending. Similarly to the winner parameter, this overrides any game
            result derivable from the board.
        :param game_complete: Optional. Whether the game reached completion.
        """

    @abc.abstractmethod
    async def quit(self) -> None:
        """Asks the engine to shut down."""

    @classmethod
    async def popen(cls: Type[ProtocolT], command: Union[str, List[str]], *, setpgrp: bool = False, **popen_args: Any) -> Tuple[asyncio.SubprocessTransport, ProtocolT]:
        if not isinstance(command, list):
            command = [command]

        if setpgrp:
            try:
                # Windows.
                popen_args["creationflags"] = popen_args.get("creationflags", 0) | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore
            except AttributeError:
                # Unix.
                if sys.version_info >= (3, 11):
                    popen_args["process_group"] = 0
                else:
                    # Before Python 3.11
                    popen_args["start_new_session"] = True

        return await asyncio.get_running_loop().subprocess_exec(cls, *command, **popen_args)