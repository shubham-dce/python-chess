from __future__ import annotations

import re
import typing
import time
import asyncio
import copy

import chess
from chess import Color

from .utils import LOGGER, T, ConfigMapping, ConfigValue, _next_token, _chain_config, MANAGED_OPTIONS
from .protocol import Protocol
from typing import Optional, Iterable, Callable, Any, TypeVar, Tuple, MutableMapping, Dict, Iterator, Literal
from .error import EngineError
from .base_command import BaseCommand
from .info import Opponent, Info, INFO_ALL, InfoDict, INFO_REFUTATION, INFO_CURRLINE, INFO_NONE, INFO_PV, Limit, PlayResult, INFO_SCORE, Option
from .analysis import AnalysisResult, BestMove
from .score import PovScore, Mate,  Cp
from .wdl import PovWdl, Wdl


if typing.TYPE_CHECKING:
    from typing_extensions import override
else:
    F = typing.TypeVar("F", bound=Callable[..., Any])
    def override(fn: F, /) -> F:
        return fn

if typing.TYPE_CHECKING:
    from typing_extensions import Self

UCI_REGEX = re.compile(r"^[a-h][1-8][a-h][1-8][pnbrqk]?|[PNBRQK]@[a-h][1-8]|0000\Z")

class UciProtocol(Protocol):
    """
    An implementation of the
    `Universal Chess Interface <https://www.chessprogramming.org/UCI>`_
    protocol.
    """

    def __init__(self) -> None:
        super().__init__()
        self._options: UciOptionMap[Option] = UciOptionMap()
        self.config: UciOptionMap[ConfigValue] = UciOptionMap()
        self.target_config: UciOptionMap[ConfigValue] = UciOptionMap()
        self.id = {}
        self.board = chess.Board()
        self.game: object = None
        self.first_game = True
        self.may_ponderhit: Optional[chess.Board] = None
        self.ponderhit = False

    @property
    @override
    def options(self) -> UciOptionMap[Option]:
        return self._options

    async def initialize(self) -> None:
        class UciInitializeCommand(BaseCommand[None]):
            def __init__(self, engine: UciProtocol):
                super().__init__(engine)
                self.engine = engine

            @override
            def check_initialized(self) -> None:
                if self.engine.initialized:
                    raise EngineError("engine already initialized")

            @override
            def start(self) -> None:
                self.engine.send_line("uci")

            @override
            def line_received(self, line: str) -> None:
                token, remaining = _next_token(line)
                if line.strip() == "uciok" and not self.result.done():
                    self.engine.initialized = True
                    self.result.set_result(None)
                    self.set_finished()
                elif token == "option":
                    self._option(remaining)
                elif token == "id":
                    self._id(remaining)

            def _option(self, arg: str) -> None:
                current_parameter = None
                option_parts: dict[str, str] = {k: "" for k in ["name", "type", "default", "min", "max"]}
                var = []

                parameters = list(option_parts.keys()) + ['var']
                inner_regex = '|'.join([fr"\b{parameter}\b" for parameter in parameters])
                option_regex = fr"\s*({inner_regex})\s*"
                for token in re.split(option_regex, arg.strip()):
                    if token == "var" or (token in option_parts and not option_parts[token]):
                        current_parameter = token
                    elif current_parameter == "var":
                        var.append(token)
                    elif current_parameter:
                        option_parts[current_parameter] = token

                def parse_min_max_value(option_parts: dict[str, str], which: Literal["min", "max"]) -> Optional[int]:
                    try:
                        number = option_parts[which]
                        return int(number) if number else None
                    except ValueError:
                        LOGGER.exception(f"Exception parsing option {which}")
                        return None

                name = option_parts["name"]
                type = option_parts["type"]
                default = option_parts["default"]
                min = parse_min_max_value(option_parts, "min")
                max = parse_min_max_value(option_parts, "max")

                without_default = Option(name, type, None, min, max, var)
                option = Option(without_default.name, without_default.type, without_default.parse(default), min, max, var)
                self.engine.options[option.name] = option

                if option.default is not None:
                    self.engine.config[option.name] = option.default
                if option.default is not None and not option.is_managed() and option.name.lower() != "uci_analysemode":
                    self.engine.target_config[option.name] = option.default

            def _id(self, arg: str) -> None:
                key, value = _next_token(arg)
                self.engine.id[key] = value.strip()

        return await self.communicate(UciInitializeCommand)

    def _isready(self) -> None:
        self.send_line("isready")

    def _opponent_info(self) -> None:
        opponent_info = self.config.get("UCI_Opponent") or self.target_config.get("UCI_Opponent")
        if opponent_info:
            self.send_line(f"setoption name UCI_Opponent value {opponent_info}")

    def _ucinewgame(self) -> None:
        self.send_line("ucinewgame")
        self._opponent_info()
        self.first_game = False
        self.ponderhit = False

    def debug(self, on: bool = True) -> None:
        """
        Switches debug mode of the engine on or off. This does not interrupt
        other ongoing operations.
        """
        if on:
            self.send_line("debug on")
        else:
            self.send_line("debug off")

    async def ping(self) -> None:
        class UciPingCommand(BaseCommand[None]):
            def __init__(self, engine: UciProtocol) -> None:
                super().__init__(engine)
                self.engine =  engine

            def start(self) -> None:
                self.engine._isready()

            @override
            def line_received(self, line: str) -> None:
                if line.strip() == "readyok":
                    self.result.set_result(None)
                    self.set_finished()
                else:
                    LOGGER.warning("%s: Unexpected engine output: %r", self.engine, line)

        return await self.communicate(UciPingCommand)

    def _changed_options(self, options: ConfigMapping) -> bool:
        return any(value is None or value != self.config.get(name) for name, value in _chain_config(options, self.target_config))

    def _setoption(self, name: str, value: ConfigValue) -> None:
        try:
            value = self.options[name].parse(value)
        except KeyError:
            raise EngineError("engine does not support option {} (available options: {})".format(name, ", ".join(self.options)))

        if value is None or value != self.config.get(name):
            builder = ["setoption name", name]
            if value is False:
                builder.append("value false")
            elif value is True:
                builder.append("value true")
            elif value is not None:
                builder.append("value")
                builder.append(str(value))

            if name != "UCI_Opponent":  # sent after ucinewgame
                self.send_line(" ".join(builder))
            self.config[name] = value

    def _configure(self, options: ConfigMapping) -> None:
        for name, value in _chain_config(options, self.target_config):
            if name.lower() in MANAGED_OPTIONS:
                raise EngineError("cannot set {} which is automatically managed".format(name))
            self._setoption(name, value)

    async def configure(self, options: ConfigMapping) -> None:
        class UciConfigureCommand(BaseCommand[None]):
            def __init__(self, engine: UciProtocol):
                super().__init__(engine)
                self.engine = engine

            def start(self) -> None:
                self.engine._configure(options)
                self.engine.target_config.update({name: value for name, value in options.items() if value is not None})
                self.result.set_result(None)
                self.set_finished()

        return await self.communicate(UciConfigureCommand)

    def _opponent_configuration(self, *, opponent: Optional[Opponent] = None) -> ConfigMapping:
        if opponent and opponent.name and "UCI_Opponent" in self.options:
            rating = opponent.rating or "none"
            title = opponent.title or "none"
            player_type = "computer" if opponent.is_engine else "human"
            return {"UCI_Opponent": f"{title} {rating} {player_type} {opponent.name}"}
        else:
            return {}

    async def send_opponent_information(self, *, opponent: Optional[Opponent] = None, engine_rating: Optional[int] = None) -> None:
        return await self.configure(self._opponent_configuration(opponent=opponent))

    def _position(self, board: chess.Board) -> None:
        # Select UCI_Variant and UCI_Chess960.
        uci_variant = type(board).uci_variant
        if "UCI_Variant" in self.options:
            self._setoption("UCI_Variant", uci_variant)
        elif uci_variant != "chess":
            raise EngineError("engine does not support UCI_Variant")

        if "UCI_Chess960" in self.options:
            self._setoption("UCI_Chess960", board.chess960)
        elif board.chess960:
            raise EngineError("engine does not support UCI_Chess960")

        # Send starting position.
        builder = ["position"]
        safe_history = all(board.move_stack)
        root = board.root() if safe_history else board
        fen = root.fen(shredder=board.chess960, en_passant="fen")
        if uci_variant == "chess" and fen == chess.STARTING_FEN:
            builder.append("startpos")
        else:
            builder.append("fen")
            builder.append(fen)

        # Send moves.
        if not safe_history:
            LOGGER.warning("Not transmitting history with null moves to UCI engine")
        elif board.move_stack:
            builder.append("moves")
            builder.extend(move.uci() for move in board.move_stack)

        self.send_line(" ".join(builder))
        self.board = board.copy(stack=False)

    def _go(self, limit: Limit, *, root_moves: Optional[Iterable[chess.Move]] = None, ponder: bool = False, infinite: bool = False) -> None:
        builder = ["go"]
        if ponder:
            builder.append("ponder")
        if limit.white_clock is not None:
            builder.append("wtime")
            builder.append(str(max(1, round(limit.white_clock * 1000))))
        if limit.black_clock is not None:
            builder.append("btime")
            builder.append(str(max(1, round(limit.black_clock * 1000))))
        if limit.white_inc is not None:
            builder.append("winc")
            builder.append(str(round(limit.white_inc * 1000)))
        if limit.black_inc is not None:
            builder.append("binc")
            builder.append(str(round(limit.black_inc * 1000)))
        if limit.remaining_moves is not None and int(limit.remaining_moves) > 0:
            builder.append("movestogo")
            builder.append(str(int(limit.remaining_moves)))
        if limit.depth is not None:
            builder.append("depth")
            builder.append(str(max(1, int(limit.depth))))
        if limit.nodes is not None:
            builder.append("nodes")
            builder.append(str(max(1, int(limit.nodes))))
        if limit.mate is not None:
            builder.append("mate")
            builder.append(str(max(1, int(limit.mate))))
        if limit.time is not None:
            builder.append("movetime")
            builder.append(str(max(1, round(limit.time * 1000))))
        if infinite:
            builder.append("infinite")
        if root_moves is not None:
            builder.append("searchmoves")
            if root_moves:
                builder.extend(move.uci() for move in root_moves)
            else:
                # Work around searchmoves followed by nothing.
                builder.append("0000")
        self.send_line(" ".join(builder))

    async def play(self, board: chess.Board, limit: Limit, *, game: object = None, info: Info = INFO_NONE, ponder: bool = False, draw_offered: bool = False, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}, opponent: Optional[Opponent] = None) -> PlayResult:
        new_options: Dict[str, ConfigValue] = {}
        for name, value in options.items():
            new_options[name] = value
        new_options.update(self._opponent_configuration(opponent=opponent))

        engine = self

        class UciPlayCommand(BaseCommand[PlayResult]):
            def __init__(self, engine: UciProtocol):
                super().__init__(engine)
                self.engine = engine

                # May ponderhit only in the same game and with unchanged target
                # options. The managed options UCI_AnalyseMode, Ponder, and
                # MultiPV never change between pondering play commands.
                engine.may_ponderhit = board if ponder and not engine.first_game and game == engine.game and not engine._changed_options(new_options) else None

            @override
            def start(self) -> None:
                self.info: InfoDict = {}
                self.pondering: Optional[chess.Board] = None
                self.sent_isready = False
                self.start_time = time.perf_counter()

                if self.engine.ponderhit:
                    self.engine.ponderhit = False
                    self.engine.send_line("ponderhit")
                    return

                if "UCI_AnalyseMode" in self.engine.options and "UCI_AnalyseMode" not in self.engine.target_config and all(name.lower() != "uci_analysemode" for name in new_options):
                    self.engine._setoption("UCI_AnalyseMode", False)
                if "Ponder" in self.engine.options:
                    self.engine._setoption("Ponder", ponder)
                if "MultiPV" in self.engine.options:
                    self.engine._setoption("MultiPV", self.engine.options["MultiPV"].default)

                new_opponent = new_options.get("UCI_Opponent") or self.engine.target_config.get("UCI_Opponent")
                opponent_changed = new_opponent != self.engine.config.get("UCI_Opponent")
                self.engine._configure(new_options)

                if self.engine.first_game or self.engine.game != game or opponent_changed:
                    self.engine.game = game
                    self.engine._ucinewgame()
                    self.sent_isready = True
                    self.engine._isready()
                else:
                    self._readyok()

            @override
            def line_received(self, line: str) -> None:
                token, remaining = _next_token(line)
                if token == "info":
                    self._info(remaining)
                elif token == "bestmove":
                    self._bestmove(remaining)
                elif line.strip() == "readyok" and self.sent_isready:
                    self._readyok()
                else:
                    LOGGER.warning("%s: Unexpected engine output: %r", self.engine, line)

            def _readyok(self) -> None:
                self.sent_isready = False
                engine._position(board)
                engine._go(limit, root_moves=root_moves)

            def _info(self, arg: str) -> None:
                if not self.pondering:
                    self.info.update(_parse_uci_info(arg, self.engine.board, info))

            def _bestmove(self, arg: str) -> None:
                if self.pondering:
                    self.pondering = None
                elif not self.result.cancelled():
                    best = _parse_uci_bestmove(self.engine.board, arg)
                    self.result.set_result(PlayResult(best.move, best.ponder, self.info))

                    if ponder and best.move and best.ponder:
                        self.pondering = board.copy()
                        self.pondering.push(best.move)
                        self.pondering.push(best.ponder)
                        self.engine._position(self.pondering)

                        # Adjust clocks for pondering.
                        time_used = time.perf_counter() - self.start_time
                        ponder_limit = copy.copy(limit)
                        if ponder_limit.white_clock is not None:
                            ponder_limit.white_clock += (ponder_limit.white_inc or 0.0)
                            if self.pondering.turn == chess.WHITE:
                                ponder_limit.white_clock -= time_used
                        if ponder_limit.black_clock is not None:
                            ponder_limit.black_clock += (ponder_limit.black_inc or 0.0)
                            if self.pondering.turn == chess.BLACK:
                                ponder_limit.black_clock -= time_used
                        if ponder_limit.remaining_moves:
                            ponder_limit.remaining_moves -= 1

                        self.engine._go(ponder_limit, ponder=True)

                if not self.pondering:
                    self.end()

            def end(self) -> None:
                engine.may_ponderhit = None
                self.set_finished()

            @override
            def cancel(self) -> None:
                if self.engine.may_ponderhit and self.pondering and self.engine.may_ponderhit.move_stack == self.pondering.move_stack and self.engine.may_ponderhit == self.pondering:
                    self.engine.ponderhit = True
                    self.end()
                else:
                    self.engine.send_line("stop")

            @override
            def engine_terminated(self, exc: Exception) -> None:
                # Allow terminating engine while pondering.
                if not self.result.done():
                    super().engine_terminated(exc)

        return await self.communicate(UciPlayCommand)

    async def analysis(self, board: chess.Board, limit: Optional[Limit] = None, *, multipv: Optional[int] = None, game: object = None, info: Info = INFO_ALL, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}) -> AnalysisResult:
        class UciAnalysisCommand(BaseCommand[AnalysisResult]):
            def __init__(self, engine: UciProtocol):
                super().__init__(engine)
                self.engine = engine

            def start(self) -> None:
                self.analysis = AnalysisResult(stop=lambda: self.cancel())
                self.sent_isready = False

                if "Ponder" in self.engine.options:
                    self.engine._setoption("Ponder", False)
                if "UCI_AnalyseMode" in self.engine.options and "UCI_AnalyseMode" not in self.engine.target_config and all(name.lower() != "uci_analysemode" for name in options):
                    self.engine._setoption("UCI_AnalyseMode", True)
                if "MultiPV" in self.engine.options or (multipv and multipv > 1):
                    self.engine._setoption("MultiPV", 1 if multipv is None else multipv)

                self.engine._configure(options)

                if self.engine.first_game or self.engine.game != game:
                    self.engine.game = game
                    self.engine._ucinewgame()
                    self.sent_isready = True
                    self.engine._isready()
                else:
                    self._readyok()

            @override
            def line_received(self, line: str) -> None:
                token, remaining = _next_token(line)
                if token == "info":
                    self._info(remaining)
                elif token == "bestmove":
                    self._bestmove(remaining)
                elif line.strip() == "readyok" and self.sent_isready:
                    self._readyok()
                else:
                    LOGGER.warning("%s: Unexpected engine output: %r", self.engine, line)

            def _readyok(self) -> None:
                self.sent_isready = False
                self.engine._position(board)

                if limit:
                    self.engine._go(limit, root_moves=root_moves)
                else:
                    self.engine._go(Limit(), root_moves=root_moves, infinite=True)

                self.result.set_result(self.analysis)

            def _info(self, arg: str) -> None:
                self.analysis.post(_parse_uci_info(arg, self.engine.board, info))

            def _bestmove(self, arg: str) -> None:
                if not self.result.done():
                    raise EngineError("was not searching, but engine sent bestmove")
                best = _parse_uci_bestmove(self.engine.board, arg)
                self.set_finished()
                self.analysis.set_finished(best)

            @override
            def cancel(self) -> None:
                self.engine.send_line("stop")

            @override
            def engine_terminated(self, exc: Exception) -> None:
                LOGGER.debug("%s: Closing analysis because engine has been terminated (error: %s)", self.engine, exc)
                self.analysis.set_exception(exc)

        return await self.communicate(UciAnalysisCommand)

    async def send_game_result(self, board: chess.Board, winner: Optional[Color] = None, game_ending: Optional[str] = None, game_complete: bool = True) -> None:
        pass

    async def quit(self) -> None:
        self.send_line("quit")
        await asyncio.shield(self.returncode)


class UciOptionMap(MutableMapping[str, T]):
    """Dictionary with case-insensitive keys."""

    def __init__(self, data: Optional[Iterable[Tuple[str, T]]] = None, **kwargs: T) -> None:
        self._store: Dict[str, Tuple[str, T]] = {}
        if data is None:
            data = {}
        self.update(data, **kwargs)

    def __setitem__(self, key: str, value: T) -> None:
        self._store[key.lower()] = (key, value)

    def __getitem__(self, key: str) -> T:
        return self._store[key.lower()][1]

    def __delitem__(self, key: str) -> None:
        del self._store[key.lower()]

    def __iter__(self) -> Iterator[str]:
        return (casedkey for casedkey, _ in self._store.values())

    def __len__(self) -> int:
        return len(self._store)

    def __eq__(self, other: object) -> bool:
        try:
            for key, value in self.items():
                if key not in other or other[key] != value:  # type: ignore
                    return False

            for key, value in other.items():  # type: ignore
                if key not in self or self[key] != value:
                    return False

            return True
        except (TypeError, AttributeError):
            return NotImplemented

    def copy(self) -> UciOptionMap[T]:
        return type(self)(self._store.values())

    def __copy__(self) -> UciOptionMap[T]:
        return self.copy()

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict(self.items())!r})"

def _create_variation_line(root_board: chess.Board, line: str) -> tuple[list[chess.Move], str]:
    board = root_board.copy(stack=False)
    currline: list[chess.Move] = []
    while True:
        next_move, remaining_line_after_move = _next_token(line)
        if UCI_REGEX.match(next_move):
            currline.append(board.push_uci(next_move))
            line = remaining_line_after_move
        else:
            return currline, line


def _parse_uci_info(arg: str, root_board: chess.Board, selector: Info = INFO_ALL) -> InfoDict:
    info: InfoDict = {}
    if not selector:
        return info

    remaining_line = arg
    while remaining_line:
        parameter, remaining_line = _next_token(remaining_line)

        if parameter == "string":
            info["string"] = remaining_line
            break
        elif parameter in ["depth", "seldepth", "nodes", "multipv", "currmovenumber",
                           "hashfull", "nps", "tbhits", "cpuload", "movesleft"]:
            try:
                number, remaining_line = _next_token(remaining_line)
                info[parameter] = int(number)  # type: ignore
            except (ValueError, IndexError):
                LOGGER.error("Exception parsing %s from info: %r", parameter, arg)
        elif parameter == "time":
            try:
                time_ms, remaining_line = _next_token(remaining_line)
                info["time"] = int(time_ms) / 1000.0
            except (ValueError, IndexError):
                LOGGER.error("Exception parsing %s from info: %r", parameter, arg)
        elif parameter == "ebf":
            try:
                number, remaining_line = _next_token(remaining_line)
                info["ebf"] = float(number)
            except (ValueError, IndexError):
                LOGGER.error("Exception parsing %s from info: %r", parameter, arg)
        elif parameter == "score" and selector & INFO_SCORE:
            try:
                kind, remaining_line = _next_token(remaining_line)
                value, remaining_line = _next_token(remaining_line)
                token, remaining_after_token = _next_token(remaining_line)
                if token in ["lowerbound", "upperbound"]:
                    info[token] = True  # type: ignore
                    remaining_line = remaining_after_token
                if kind == "cp":
                    info["score"] = PovScore(Cp(int(value)), root_board.turn)
                elif kind == "mate":
                    info["score"] = PovScore(Mate(int(value)), root_board.turn)
                else:
                    LOGGER.error("Unknown score kind %r in info (expected cp or mate): %r", kind, arg)
            except (ValueError, IndexError):
                LOGGER.error("Exception parsing score from info: %r", arg)
        elif parameter == "currmove":
            try:
                current_move, remaining_line = _next_token(remaining_line)
                info["currmove"] = chess.Move.from_uci(current_move)
            except (ValueError, IndexError):
                LOGGER.error("Exception parsing currmove from info: %r", arg)
        elif parameter == "currline" and selector & INFO_CURRLINE:
            try:
                if "currline" not in info:
                    info["currline"] = {}

                cpunr_text, remaining_line = _next_token(remaining_line)
                cpunr = int(cpunr_text)
                currline, remaining_line = _create_variation_line(root_board, remaining_line)
                info["currline"][cpunr] = currline
            except (ValueError, IndexError):
                LOGGER.error("Exception parsing currline from info: %r, position at root: %s", arg, root_board.fen())
        elif parameter == "refutation" and selector & INFO_REFUTATION:
            try:
                if "refutation" not in info:
                    info["refutation"] = {}

                board = root_board.copy(stack=False)
                refuted_text, remaining_line = _next_token(remaining_line)
                refuted = board.push_uci(refuted_text)

                refuted_by, remaining_line = _create_variation_line(board, remaining_line)
                info["refutation"][refuted] = refuted_by
            except (ValueError, IndexError):
                LOGGER.error("Exception parsing refutation from info: %r, position at root: %s", arg, root_board.fen())
        elif parameter == "pv" and selector & INFO_PV:
            try:
                pv, remaining_line = _create_variation_line(root_board, remaining_line)
                info["pv"] = pv
            except (ValueError, IndexError):
                LOGGER.error("Exception parsing pv from info: %r, position at root: %s", arg, root_board.fen())
        elif parameter == "wdl":
            try:
                wins, remaining_line = _next_token(remaining_line)
                draws, remaining_line = _next_token(remaining_line)
                losses, remaining_line = _next_token(remaining_line)
                info["wdl"] = PovWdl(Wdl(int(wins), int(draws), int(losses)), root_board.turn)
            except (ValueError, IndexError):
                LOGGER.error("Exception parsing wdl from info: %r", arg)

    return info

def _parse_uci_bestmove(board: chess.Board, args: str) -> BestMove:
    tokens = args.split()

    move = None
    ponder = None

    if tokens and tokens[0] not in ["(none)", "NULL"]:
        try:
            # AnMon 5.75 uses uppercase letters to denote promotion types.
            move = board.push_uci(tokens[0].lower())
        except ValueError as err:
            raise EngineError(err)

        try:
            # Houdini 1.5 sends NULL instead of skipping the token.
            if len(tokens) >= 3 and tokens[1] == "ponder" and tokens[2] not in ["(none)", "NULL"]:
                ponder = board.parse_uci(tokens[2].lower())
        except ValueError:
            LOGGER.exception("Engine sent invalid ponder move")
        finally:
            board.pop()

    return BestMove(move, ponder)