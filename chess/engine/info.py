import enum
import dataclasses
import chess
from typing import Optional, TypedDict, List, Dict

from .utils import ConfigValue, MANAGED_OPTIONS
from .error import EngineError
from .score import PovScore
from .wdl import PovWdl

class Info(enum.IntFlag):
    """Used to filter information sent by the chess engine."""
    NONE = 0
    BASIC = 1
    SCORE = 2
    PV = 4
    REFUTATION = 8
    CURRLINE = 16
    ALL = BASIC | SCORE | PV | REFUTATION | CURRLINE

INFO_NONE = Info.NONE
INFO_BASIC = Info.BASIC
INFO_SCORE = Info.SCORE
INFO_PV = Info.PV
INFO_REFUTATION = Info.REFUTATION
INFO_CURRLINE = Info.CURRLINE
INFO_ALL = Info.ALL

@dataclasses.dataclass
class Opponent:
    """Used to store information about an engine's opponent."""

    name: Optional[str]
    """The name of the opponent."""

    title: Optional[str]
    """The opponent's title--for example, GM, IM, or BOT."""

    rating: Optional[int]
    """The opponent's ELO rating."""

    is_engine: Optional[bool]
    """Whether the opponent is a chess engine/computer program."""

class InfoDict(TypedDict, total=False):
    """
    Dictionary of aggregated information sent by the engine.

    Commonly used keys are: ``score`` (a :class:`~chess.engine.PovScore`),
    ``pv`` (a list of :class:`~chess.Move` objects), ``depth``,
    ``seldepth``, ``time`` (in seconds), ``nodes``, ``nps``, ``multipv``
    (``1`` for the mainline).

    Others: ``tbhits``, ``currmove``, ``currmovenumber``, ``hashfull``,
    ``cpuload``, ``refutation``, ``currline``, ``ebf`` (effective branching factor),
    ``wdl`` (a :class:`~chess.engine.PovWdl`), and ``string``.
    """
    score: PovScore
    pv: List[chess.Move]
    depth: int
    seldepth: int
    time: float
    nodes: int
    nps: int
    tbhits: int
    multipv: int
    currmove: chess.Move
    currmovenumber: int
    hashfull: int
    cpuload: int
    refutation: Dict[chess.Move, List[chess.Move]]
    currline: Dict[int, List[chess.Move]]
    ebf: float
    wdl: PovWdl
    string: str

@dataclasses.dataclass(frozen=True)
class Option:
    """Information about an available engine option."""

    name: str
    """The name of the option."""

    type: str
    """
    The type of the option.

    +--------+-----+------+------------------------------------------------+
    | type   | UCI | CECP | value                                          |
    +========+=====+======+================================================+
    | check  | X   | X    | ``True`` or ``False``                          |
    +--------+-----+------+------------------------------------------------+
    | spin   | X   | X    | integer, between *min* and *max*               |
    +--------+-----+------+------------------------------------------------+
    | combo  | X   | X    | string, one of *var*                           |
    +--------+-----+------+------------------------------------------------+
    | button | X   | X    | ``None``                                       |
    +--------+-----+------+------------------------------------------------+
    | reset  |     | X    | ``None``                                       |
    +--------+-----+------+------------------------------------------------+
    | save   |     | X    | ``None``                                       |
    +--------+-----+------+------------------------------------------------+
    | string | X   | X    | string without line breaks                     |
    +--------+-----+------+------------------------------------------------+
    | file   |     | X    | string, interpreted as the path to a file      |
    +--------+-----+------+------------------------------------------------+
    | path   |     | X    | string, interpreted as the path to a directory |
    +--------+-----+------+------------------------------------------------+
    """

    default: ConfigValue
    """The default value of the option."""

    min: Optional[int]
    """The minimum integer value of a *spin* option."""

    max: Optional[int]
    """The maximum integer value of a *spin* option."""

    var: Optional[List[str]]
    """A list of allowed string values for a *combo* option."""

    def parse(self, value: ConfigValue) -> ConfigValue:
        if self.type == "check":
            return value and value != "false"
        elif self.type == "spin":
            try:
                value = int(value)  # type: ignore
            except ValueError:
                raise EngineError(f"expected integer for spin option {self.name!r}, got: {value!r}")
            if self.min is not None and value < self.min:
                raise EngineError(f"expected value for option {self.name!r} to be at least {self.min}, got: {value}")
            if self.max is not None and self.max < value:
                raise EngineError(f"expected value for option {self.name!r} to be at most {self.max}, got: {value}")
            return value
        elif self.type == "combo":
            value = str(value)
            if value not in (self.var or []):
                raise EngineError("invalid value for combo option {!r}, got: {} (available: {})".format(self.name, value, ", ".join(self.var) if self.var else "-"))
            return value
        elif self.type in ["button", "reset", "save"]:
            return None
        elif self.type in ["string", "file", "path"]:
            value = str(value)
            if "\n" in value or "\r" in value:
                raise EngineError(f"invalid line-break in string option {self.name!r}: {value!r}")
            return value
        else:
            raise EngineError(f"unknown option type: {self.type!r}")

    def is_managed(self) -> bool:
        """
        Some options are managed automatically: ``UCI_Chess960``,
        ``UCI_Variant``, ``MultiPV``, ``Ponder``.
        """
        return self.name.lower() in MANAGED_OPTIONS


@dataclasses.dataclass
class Limit:
    """Search-termination condition."""

    time: Optional[float] = None
    """Search exactly *time* seconds."""

    depth: Optional[int] = None
    """Search *depth* ply only."""

    nodes: Optional[int] = None
    """Search only a limited number of *nodes*."""

    mate: Optional[int] = None
    """Search for a mate in *mate* moves."""

    white_clock: Optional[float] = None
    """Time in seconds remaining for White."""

    black_clock: Optional[float] = None
    """Time in seconds remaining for Black."""

    white_inc: Optional[float] = None
    """Fisher increment for White, in seconds."""

    black_inc: Optional[float] = None
    """Fisher increment for Black, in seconds."""

    remaining_moves: Optional[int] = None
    """
    Number of moves to the next time control. If this is not set, but
    *white_clock* and *black_clock* are, then it is sudden death.
    """

    clock_id: object = None
    """
    An identifier to use with XBoard engines to signal that the time
    control has changed. When this field changes, Xboard engines are
    sent level or st commands as appropriate. Otherwise, only time
    and otim commands are sent to update the engine's clock.
    """

    def __repr__(self) -> str:
        # Like default __repr__, but without None values.
        return "{}({})".format(
            type(self).__name__,
            ", ".join("{}={!r}".format(attr, getattr(self, attr))
                      for attr in ["time", "depth", "nodes", "mate", "white_clock", "black_clock", "white_inc", "black_inc", "remaining_moves"]
                      if getattr(self, attr) is not None))
    

class PlayResult:
    """Returned by :func:`chess.engine.Protocol.play()`."""

    move: Optional[chess.Move]
    """The best move according to the engine, or ``None``."""

    ponder: Optional[chess.Move]
    """The response that the engine expects after *move*, or ``None``."""

    info: InfoDict
    """
    A dictionary of extra :class:`information <chess.engine.InfoDict>`
    sent by the engine, if selected with the *info* argument of
    :func:`~chess.engine.Protocol.play()`.
    """

    draw_offered: bool
    """Whether the engine offered a draw before moving."""

    resigned: bool
    """Whether the engine resigned."""

    def __init__(self,
                 move: Optional[chess.Move],
                 ponder: Optional[chess.Move],
                 info: Optional[InfoDict] = None,
                 *,
                 draw_offered: bool = False,
                 resigned: bool = False) -> None:
        self.move = move
        self.ponder = ponder
        self.info = info or {}
        self.draw_offered = draw_offered
        self.resigned = resigned

    def __repr__(self) -> str:
        return "<{} at {:#x} (move={}, ponder={}, info={}, draw_offered={}, resigned={})>".format(
            type(self).__name__, id(self), self.move, self.ponder, self.info,
            self.draw_offered, self.resigned)