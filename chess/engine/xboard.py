import re
import typing
import asyncio
import shlex

import chess
from chess import Color

from .protocol import Protocol
from typing import Dict, Union, Optional, Iterable, Callable, Any
from .utils import ConfigValue, LOGGER, _next_token, _chain_config, ConfigMapping, MANAGED_OPTIONS
from .base_command import BaseCommand
from .error import EngineError
from .info import Opponent, Info, INFO_NONE, PlayResult, Limit, INFO_ALL, INFO_PV, InfoDict, Option
from .analysis import AnalysisResult, BestMove
from .score import Cp, Mate, MateGiven, Score, PovScore

if typing.TYPE_CHECKING:
    from typing_extensions import override
else:
    F = typing.TypeVar("F", bound=Callable[..., Any])
    def override(fn: F, /) -> F:
        return fn

XBOARD_ERROR_REGEX = re.compile(r"^\s*(Error|Illegal move)(\s*\([^()]+\))?\s*:")

class XBoardProtocol(Protocol):
    """
    An implementation of the
    `XBoard protocol <http://hgm.nubati.net/CECP.html>`__ (CECP).
    """

    def __init__(self) -> None:
        super().__init__()
        self.features: Dict[str, Union[int, str]] = {}
        self.id = {}
        self._options = {
            "random": Option("random", "check", False, None, None, None),
            "computer": Option("computer", "check", False, None, None, None),
            "name": Option("name", "string", "", None, None, None),
            "engine_rating": Option("engine_rating", "spin", 0, None, None, None),
            "opponent_rating": Option("opponent_rating", "spin", 0, None, None, None)
        }
        self.config: Dict[str, ConfigValue] = {}
        self.target_config: Dict[str, ConfigValue] = {}
        self.board = chess.Board()
        self.game: object = None
        self.clock_id: object = None
        self.first_game = True

    @property
    @override
    def options(self) -> Dict[str, Option]:
        return self._options

    async def initialize(self) -> None:
        class XBoardInitializeCommand(BaseCommand[None]):
            def __init__(self, engine: XBoardProtocol):
                super().__init__(engine)
                self.engine = engine

            @override
            def check_initialized(self) -> None:
                if self.engine.initialized:
                    raise EngineError("engine already initialized")

            @override
            def start(self) -> None:
                self.engine.send_line("xboard")
                self.engine.send_line("protover 2")
                self.timeout_handle = self.engine.loop.call_later(2.0, lambda: self.timeout())

            def timeout(self) -> None:
                LOGGER.error("%s: Timeout during initialization", self.engine)
                self.end()

            @override
            def line_received(self, line: str) -> None:
                token, remaining = _next_token(line)
                if token.startswith("#"):
                    pass
                elif token == "feature":
                    self._feature(remaining)
                elif XBOARD_ERROR_REGEX.match(line):
                    raise EngineError(line)

            def _feature(self, arg: str) -> None:
                for feature in shlex.split(arg):
                    key, value = feature.split("=", 1)
                    if key == "option":
                        option = _parse_xboard_option(value)
                        if option.name not in ["random", "computer", "cores", "memory"]:
                            self.engine.options[option.name] = option
                    else:
                        try:
                            self.engine.features[key] = int(value)
                        except ValueError:
                            self.engine.features[key] = value

                if "done" in self.engine.features:
                    self.timeout_handle.cancel()
                if self.engine.features.get("done"):
                    self.end()

            def end(self) -> None:
                if not self.engine.features.get("ping", 0):
                    self.result.set_exception(EngineError("xboard engine did not declare required feature: ping"))
                    self.set_finished()
                    return
                if not self.engine.features.get("setboard", 0):
                    self.result.set_exception(EngineError("xboard engine did not declare required feature: setboard"))
                    self.set_finished()
                    return

                if not self.engine.features.get("reuse", 1):
                    LOGGER.warning("%s: Rejecting feature reuse=0", self.engine)
                    self.engine.send_line("rejected reuse")
                if not self.engine.features.get("sigterm", 1):
                    LOGGER.warning("%s: Rejecting feature sigterm=0", self.engine)
                    self.engine.send_line("rejected sigterm")
                if self.engine.features.get("san", 0):
                    LOGGER.warning("%s: Rejecting feature san=1", self.engine)
                    self.engine.send_line("rejected san")

                if "myname" in self.engine.features:
                    self.engine.id["name"] = str(self.engine.features["myname"])

                if self.engine.features.get("memory", 0):
                    self.engine.options["memory"] = Option("memory", "spin", 16, 1, None, None)
                    self.engine.send_line("accepted memory")
                if self.engine.features.get("smp", 0):
                    self.engine.options["cores"] = Option("cores", "spin", 1, 1, None, None)
                    self.engine.send_line("accepted smp")
                if self.engine.features.get("egt"):
                    for egt in str(self.engine.features["egt"]).split(","):
                        name = f"egtpath {egt}"
                        self.engine.options[name] = Option(name, "path", None, None, None, None)
                    self.engine.send_line("accepted egt")

                for option in self.engine.options.values():
                    if option.default is not None:
                        self.engine.config[option.name] = option.default
                    if option.default is not None and not option.is_managed():
                        self.engine.target_config[option.name] = option.default

                self.engine.initialized = True
                self.result.set_result(None)
                self.set_finished()

        return await self.communicate(XBoardInitializeCommand)

    def _ping(self, n: int) -> None:
        self.send_line(f"ping {n}")

    def _variant(self, variant: Optional[str]) -> None:
        variants = str(self.features.get("variants", "")).split(",")
        if not variant or variant not in variants:
            raise EngineError("unsupported xboard variant: {} (available: {})".format(variant, ", ".join(variants)))

        self.send_line(f"variant {variant}")

    def _new(self, board: chess.Board, game: object, options: ConfigMapping, opponent: Optional[Opponent] = None) -> None:
        self._configure(options)
        self._configure(self._opponent_configuration(opponent=opponent))

        # Set up starting position.
        root = board.root()
        new_options = any(param in options for param in ("random", "computer"))
        new_game = self.first_game or self.game != game or new_options or opponent or root != self.board.root()
        self.game = game
        self.first_game = False
        if new_game:
            self.board = root
            self.send_line("new")

            variant = type(board).xboard_variant
            if variant == "normal" and board.chess960:
                self._variant("fischerandom")
            elif variant != "normal":
                self._variant(variant)

            if self.config.get("random"):
                self.send_line("random")

            opponent_name = self.config.get("name")
            if opponent_name and self.features.get("name", True):
                self.send_line(f"name {opponent_name}")

            opponent_rating = self.config.get("opponent_rating")
            engine_rating = self.config.get("engine_rating")
            if engine_rating or opponent_rating:
                self.send_line(f"rating {engine_rating or 0} {opponent_rating or 0}")

            if self.config.get("computer"):
                self.send_line("computer")

            self.send_line("force")

            fen = root.fen(shredder=board.chess960, en_passant="fen")
            if variant != "normal" or fen != chess.STARTING_FEN or board.chess960:
                self.send_line(f"setboard {fen}")
        else:
            self.send_line("force")

        # Undo moves until common position.
        common_stack_len = 0
        if not new_game:
            for left, right in zip(self.board.move_stack, board.move_stack):
                if left == right:
                    common_stack_len += 1
                else:
                    break

            while len(self.board.move_stack) > common_stack_len + 1:
                self.send_line("remove")
                self.board.pop()
                self.board.pop()

            while len(self.board.move_stack) > common_stack_len:
                self.send_line("undo")
                self.board.pop()

        # Play moves from board stack.
        for move in board.move_stack[common_stack_len:]:
            if not move:
                LOGGER.warning("Null move (in %s) may not be supported by all XBoard engines", self.board.fen())
            prefix = "usermove " if self.features.get("usermove", 0) else ""
            self.send_line(prefix + self.board.xboard(move))
            self.board.push(move)

    async def ping(self) -> None:
        class XBoardPingCommand(BaseCommand[None]):
            def __init__(self, engine: XBoardProtocol):
                super().__init__(engine)
                self.engine = engine

            @override
            def start(self) -> None:
                n = id(self) & 0xffff
                self.pong = f"pong {n}"
                self.engine._ping(n)

            @override
            def line_received(self, line: str) -> None:
                if line == self.pong:
                    self.result.set_result(None)
                    self.set_finished()
                elif not line.startswith("#"):
                    LOGGER.warning("%s: Unexpected engine output: %r", self.engine, line)
                elif XBOARD_ERROR_REGEX.match(line):
                    raise EngineError(line)

        return await self.communicate(XBoardPingCommand)

    async def play(self, board: chess.Board, limit: Limit, *, game: object = None, info: Info = INFO_NONE, ponder: bool = False, draw_offered: bool = False, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}, opponent: Optional[Opponent] = None) -> PlayResult:
        if root_moves is not None:
            raise EngineError("play with root_moves, but xboard supports 'include' only in analysis mode")

        class XBoardPlayCommand(BaseCommand[PlayResult]):
            def __init__(self, engine: XBoardProtocol):
                super().__init__(engine)
                self.engine = engine

            @override
            def start(self) -> None:
                self.play_result = PlayResult(None, None)
                self.stopped = False
                self.pong_after_move: Optional[str] = None
                self.pong_after_ponder: Optional[str] = None

                # Set game, position and configure.
                self.engine._new(board, game, options, opponent)

                # Limit or time control.
                clock = limit.white_clock if board.turn else limit.black_clock
                increment = limit.white_inc if board.turn else limit.black_inc
                if limit.clock_id is None or limit.clock_id != self.engine.clock_id:
                    self._send_time_control(clock, increment)
                self.engine.clock_id = limit.clock_id
                if limit.nodes is not None:
                    if limit.time is not None or limit.white_clock is not None or limit.black_clock is not None or increment is not None:
                        raise EngineError("xboard does not support mixing node limits with time limits")

                    if "nps" not in self.engine.features:
                        LOGGER.warning("%s: Engine did not explicitly declare support for node limits (feature nps=?)")
                    elif not self.engine.features["nps"]:
                        raise EngineError("xboard engine does not support node limits (feature nps=0)")

                    self.engine.send_line("nps 1")
                    self.engine.send_line(f"st {max(1, int(limit.nodes))}")
                if limit.depth is not None:
                    self.engine.send_line(f"sd {max(1, int(limit.depth))}")
                if limit.white_clock is not None:
                    self.engine.send_line("{} {}".format("time" if board.turn else "otim", max(1, round(limit.white_clock * 100))))
                if limit.black_clock is not None:
                    self.engine.send_line("{} {}".format("otim" if board.turn else "time", max(1, round(limit.black_clock * 100))))

                if draw_offered and self.engine.features.get("draw", 1):
                    self.engine.send_line("draw")

                # Start thinking.
                self.engine.send_line("post" if info else "nopost")
                self.engine.send_line("hard" if ponder else "easy")
                self.engine.send_line("go")

            @override
            def line_received(self, line: str) -> None:
                token, remaining = _next_token(line)
                if token == "move":
                    self._move(remaining.strip())
                elif token == "Hint:":
                    self._hint(remaining.strip())
                elif token == "pong":
                    pong_line = f"{token} {remaining.strip()}"
                    if pong_line == self.pong_after_move:
                        if not self.result.done():
                            self.result.set_result(self.play_result)
                        if not ponder:
                            self.set_finished()
                    elif pong_line == self.pong_after_ponder:
                        if not self.result.done():
                            self.result.set_result(self.play_result)
                        self.set_finished()
                elif f"{token} {remaining.strip()}" == "offer draw":
                    if not self.result.done():
                        self.play_result.draw_offered = True
                    self._ping_after_move()
                elif line.strip() == "resign":
                    if not self.result.done():
                        self.play_result.resigned = True
                    self._ping_after_move()
                elif token in ["1-0", "0-1", "1/2-1/2"]:
                    if "resign" in line and not self.result.done():
                        self.play_result.resigned = True
                    self._ping_after_move()
                elif token.startswith("#"):
                    pass
                elif XBOARD_ERROR_REGEX.match(line):
                    self.engine.first_game = True  # Board state might no longer be in sync
                    raise EngineError(line)
                elif len(line.split()) >= 4 and line.lstrip()[0].isdigit():
                    self._post(line)
                else:
                    LOGGER.warning("%s: Unexpected engine output: %r", self.engine, line)

            def _send_time_control(self, clock: Optional[float], increment: Optional[float]) -> None:
                if limit.remaining_moves or clock is not None or increment is not None:
                    base_mins, base_secs = divmod(int(clock or 0), 60)
                    self.engine.send_line(f"level {limit.remaining_moves or 0} {base_mins}:{base_secs:02d} {increment or 0}")
                if limit.time is not None:
                    self.engine.send_line(f"st {max(0.01, limit.time)}")

            def _post(self, line: str) -> None:
                if not self.result.done():
                    self.play_result.info = _parse_xboard_post(line, self.engine.board, info)

            def _move(self, arg: str) -> None:
                if not self.result.done() and self.play_result.move is None:
                    try:
                        self.play_result.move = self.engine.board.push_xboard(arg)
                    except ValueError as err:
                        self.result.set_exception(EngineError(err))
                    else:
                        self._ping_after_move()
                else:
                    try:
                        self.engine.board.push_xboard(arg)
                    except ValueError:
                        LOGGER.exception("Exception playing unexpected move")

            def _hint(self, arg: str) -> None:
                if not self.result.done() and self.play_result.move is not None and self.play_result.ponder is None:
                    try:
                        self.play_result.ponder = self.engine.board.parse_xboard(arg)
                    except ValueError:
                        LOGGER.exception("Exception parsing hint")
                else:
                    LOGGER.warning("Unexpected hint: %r", arg)

            def _ping_after_move(self) -> None:
                if self.pong_after_move is None:
                    n = id(self) & 0xffff
                    self.pong_after_move = f"pong {n}"
                    self.engine._ping(n)

            @override
            def cancel(self) -> None:
                if self.stopped:
                    return
                self.stopped = True

                if self.result.cancelled():
                    self.engine.send_line("?")

                if ponder:
                    self.engine.send_line("easy")

                    n = (id(self) + 1) & 0xffff
                    self.pong_after_ponder = f"pong {n}"
                    self.engine._ping(n)

            @override
            def engine_terminated(self, exc: Exception) -> None:
                # Allow terminating engine while pondering.
                if not self.result.done():
                    super().engine_terminated(exc)

        return await self.communicate(XBoardPlayCommand)

    async def analysis(self, board: chess.Board, limit: Optional[Limit] = None, *, multipv: Optional[int] = None, game: object = None, info: Info = INFO_ALL, root_moves: Optional[Iterable[chess.Move]] = None, options: ConfigMapping = {}) -> AnalysisResult:
        if multipv is not None:
            raise EngineError("xboard engine does not support multipv")

        if limit is not None and (limit.white_clock is not None or limit.black_clock is not None):
            raise EngineError("xboard analysis does not support clock limits")

        class XBoardAnalysisCommand(BaseCommand[AnalysisResult]):
            def __init__(self, engine: XBoardProtocol):
                super().__init__(engine)
                self.engine = engine

            @override
            def start(self) -> None:
                self.stopped = False
                self.best_move: Optional[chess.Move] = None
                self.analysis = AnalysisResult(stop=lambda: self.cancel())
                self.final_pong: Optional[str] = None

                self.engine._new(board, game, options)

                if root_moves is not None:
                    if not self.engine.features.get("exclude", 0):
                        raise EngineError("xboard engine does not support root_moves (feature exclude=0)")

                    self.engine.send_line("exclude all")
                    for move in root_moves:
                        self.engine.send_line(f"include {self.engine.board.xboard(move)}")

                self.engine.send_line("post")
                self.engine.send_line("analyze")

                self.result.set_result(self.analysis)

                if limit is not None and limit.time is not None:
                    self.time_limit_handle: Optional[asyncio.Handle] = self.engine.loop.call_later(limit.time, lambda: self.cancel())
                else:
                    self.time_limit_handle = None

            @override
            def line_received(self, line: str) -> None:
                token, remaining = _next_token(line)
                if token.startswith("#"):
                    pass
                elif len(line.split()) >= 4 and line.lstrip()[0].isdigit():
                    self._post(line)
                elif f"{token} {remaining.strip()}" == self.final_pong:
                    self.end()
                elif XBOARD_ERROR_REGEX.match(line):
                    self.engine.first_game = True  # Board state might no longer be in sync
                    raise EngineError(line)
                else:
                    LOGGER.warning("%s: Unexpected engine output: %r", self.engine, line)

            def _post(self, line: str) -> None:
                post_info = _parse_xboard_post(line, self.engine.board, info)
                self.analysis.post(post_info)

                pv = post_info.get("pv")
                if pv:
                    self.best_move = pv[0]

                if limit is not None:
                    if limit.time is not None and post_info.get("time", 0) >= limit.time:
                        self.cancel()
                    elif limit.nodes is not None and post_info.get("nodes", 0) >= limit.nodes:
                        self.cancel()
                    elif limit.depth is not None and post_info.get("depth", 0) >= limit.depth:
                        self.cancel()
                    elif limit.mate is not None and "score" in post_info:
                        if post_info["score"].relative >= Mate(limit.mate):
                            self.cancel()

            def end(self) -> None:
                if self.time_limit_handle:
                    self.time_limit_handle.cancel()

                self.set_finished()
                self.analysis.set_finished(BestMove(self.best_move, None))

            @override
            def cancel(self) -> None:
                if self.stopped:
                    return
                self.stopped = True

                self.engine.send_line(".")
                self.engine.send_line("exit")

                n = id(self) & 0xffff
                self.final_pong = f"pong {n}"
                self.engine._ping(n)

            @override
            def engine_terminated(self, exc: Exception) -> None:
                LOGGER.debug("%s: Closing analysis because engine has been terminated (error: %s)", self.engine, exc)

                if self.time_limit_handle:
                    self.time_limit_handle.cancel()

                self.analysis.set_exception(exc)

        return await self.communicate(XBoardAnalysisCommand)

    def _setoption(self, name: str, value: ConfigValue) -> None:
        if value is not None and value == self.config.get(name):
            return

        try:
            option = self.options[name]
        except KeyError:
            raise EngineError(f"unsupported xboard option or command: {name}")

        self.config[name] = value = option.parse(value)

        if name in ["random", "computer", "name", "engine_rating", "opponent_rating"]:
            # Applied in _new.
            pass
        elif name in ["memory", "cores"] or name.startswith("egtpath "):
            self.send_line(f"{name} {value}")
        elif value is None:
            self.send_line(f"option {name}")
        elif value is True:
            self.send_line(f"option {name}=1")
        elif value is False:
            self.send_line(f"option {name}=0")
        else:
            self.send_line(f"option {name}={value}")

    def _configure(self, options: ConfigMapping) -> None:
        for name, value in _chain_config(options, self.target_config):
            if name.lower() in MANAGED_OPTIONS:
                raise EngineError(f"cannot set {name} which is automatically managed")
            self._setoption(name, value)

    async def configure(self, options: ConfigMapping) -> None:
        class XBoardConfigureCommand(BaseCommand[None]):
            def __init__(self, engine: XBoardProtocol):
                super().__init__(engine)
                self.engine = engine

            @override
            def start(self) -> None:
                self.engine._configure(options)
                self.engine.target_config.update({name: value for name, value in options.items() if value is not None})
                self.result.set_result(None)
                self.set_finished()

        return await self.communicate(XBoardConfigureCommand)

    def _opponent_configuration(self, *, opponent: Optional[Opponent] = None, engine_rating: Optional[int] = None) -> ConfigMapping:
        if opponent is None:
            return {}

        opponent_info: Dict[str, Union[int, bool, str]] = {"engine_rating": engine_rating or self.target_config.get("engine_rating") or 0,
                                                           "opponent_rating": opponent.rating or 0,
                                                           "computer": opponent.is_engine or False}

        if opponent.name and self.features.get("name", True):
            opponent_info["name"] = f"{opponent.title or ''} {opponent.name}".strip()

        return opponent_info

    async def send_opponent_information(self, *, opponent: Optional[Opponent] = None, engine_rating: Optional[int] = None) -> None:
        return await self.configure(self._opponent_configuration(opponent=opponent, engine_rating=engine_rating))

    async def send_game_result(self, board: chess.Board, winner: Optional[Color] = None, game_ending: Optional[str] = None, game_complete: bool = True) -> None:
        class XBoardGameResultCommand(BaseCommand[None]):
            def __init__(self, engine: XBoardProtocol):
                super().__init__(engine)
                self.engine = engine

            @override
            def start(self) -> None:
                if game_ending and any(c in game_ending for c in "{}\n\r"):
                    raise EngineError(f"invalid line break or curly braces in game ending message: {game_ending!r}")

                self.engine._new(board, self.engine.game, {})  # Send final moves to engine.

                outcome = board.outcome(claim_draw=True)

                if not game_complete:
                    result = "*"
                    ending = game_ending or ""
                elif winner is not None or game_ending:
                    result = "1-0" if winner == chess.WHITE else "0-1" if winner == chess.BLACK else "1/2-1/2"
                    ending = game_ending or ""
                elif outcome is not None and outcome.winner is not None:
                    result = outcome.result()
                    winning_color = "White" if outcome.winner == chess.WHITE else "Black"
                    is_checkmate = outcome.termination == chess.Termination.CHECKMATE
                    ending = f"{winning_color} {'mates' if is_checkmate else 'variant win'}"
                elif outcome is not None:
                    result = outcome.result()
                    ending = outcome.termination.name.capitalize().replace("_", " ")
                else:
                    result = "*"
                    ending = ""

                ending_text = f"{{{ending}}}" if ending else ""
                self.engine.send_line(f"result {result} {ending_text}".strip())
                self.result.set_result(None)
                self.set_finished()

        return await self.communicate(XBoardGameResultCommand)

    async def quit(self) -> None:
        self.send_line("quit")
        await asyncio.shield(self.returncode)


def _parse_xboard_option(feature: str) -> Option:
    params = feature.split()

    name = params[0]
    type = params[1][1:]
    default: Optional[ConfigValue] = None
    min = None
    max = None
    var = None

    if type == "combo":
        var = []
        choices = params[2:]
        for choice in choices:
            if choice == "///":
                continue
            elif choice[0] == "*":
                default = choice[1:]
                var.append(choice[1:])
            else:
                var.append(choice)
    elif type == "check":
        default = int(params[2])
    elif type in ["string", "file", "path"]:
        if len(params) > 2:
            default = params[2]
        else:
            default = ""
    elif type == "spin":
        default = int(params[2])
        min = int(params[3])
        max = int(params[4])

    return Option(name, type, default, min, max, var)


def _parse_xboard_post(line: str, root_board: chess.Board, selector: Info = INFO_ALL) -> InfoDict:
    # Format: depth score time nodes [seldepth [nps [tbhits]]] pv
    info: InfoDict = {}

    # Split leading integer tokens from pv.
    pv_tokens = line.split()
    integer_tokens = []
    while pv_tokens:
        token = pv_tokens.pop(0)
        try:
            integer_tokens.append(int(token))
        except ValueError:
            pv_tokens.insert(0, token)
            break

    if len(integer_tokens) < 4:
        return info

    # Required integer tokens.
    info["depth"] = integer_tokens.pop(0)
    cp = integer_tokens.pop(0)
    info["time"] = int(integer_tokens.pop(0)) / 100
    info["nodes"] = int(integer_tokens.pop(0))

    # Score.
    if cp <= -100000:
        score: Score = Mate(cp + 100000)
    elif cp == 100000:
        score = MateGiven
    elif cp >= 100000:
        score = Mate(cp - 100000)
    else:
        score = Cp(cp)
    info["score"] = PovScore(score, root_board.turn)

    # Optional integer tokens.
    if integer_tokens:
        info["seldepth"] = integer_tokens.pop(0)
    if integer_tokens:
        info["nps"] = integer_tokens.pop(0)

    while len(integer_tokens) > 1:
        # Reserved for future extensions.
        integer_tokens.pop(0)

    if integer_tokens:
        info["tbhits"] = integer_tokens.pop(0)

    # Principal variation.
    pv = []
    board = root_board.copy(stack=False)
    for token in pv_tokens:
        if token.rstrip(".").isdigit():
            continue

        try:
            pv.append(board.push_xboard(token))
        except ValueError:
            break

        if not (selector & INFO_PV):
            break
    info["pv"] = pv

    return info