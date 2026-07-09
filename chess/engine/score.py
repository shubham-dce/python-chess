from __future__ import annotations

import abc
import typing

import chess
from chess import Color
from typing import Optional, Tuple, Union

from .wdl import PovWdl, Wdl, _lichess_raw_wins, _sf12_wins, _sf14_wins, _sf15_1_wins, _sf15_wins, _sf16_1_wins, _sf16_wins, WdlModel

class PovScore:
    """A relative :class:`~chess.engine.Score` and the point of view."""

    relative: Score
    """The relative :class:`~chess.engine.Score`."""

    turn: Color
    """The point of view (``chess.WHITE`` or ``chess.BLACK``)."""

    def __init__(self, relative: Score, turn: Color) -> None:
        self.relative = relative
        self.turn = turn

    def white(self) -> Score:
        """Gets the score from White's point of view."""
        return self.pov(chess.WHITE)

    def black(self) -> Score:
        """Gets the score from Black's point of view."""
        return self.pov(chess.BLACK)

    def pov(self, color: Color) -> Score:
        """Gets the score from the point of view of the given *color*."""
        return self.relative if self.turn == color else -self.relative

    def is_mate(self) -> bool:
        """Tests if this is a mate score."""
        return self.relative.is_mate()

    def wdl(self, *, model: WdlModel = "sf", ply: int = 30) -> PovWdl:
        """See :func:`~chess.engine.Score.wdl()`."""
        return PovWdl(self.relative.wdl(model=model, ply=ply), self.turn)

    def __repr__(self) -> str:
        return "PovScore({!r}, {})".format(self.relative, "WHITE" if self.turn else "BLACK")

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PovScore):
            return self.white() == other.white()
        else:
            return NotImplemented


class Score(abc.ABC):
    """
    Evaluation of a position.

    The score can be :class:`~chess.engine.Cp` (centi-pawns),
    :class:`~chess.engine.Mate` or :py:data:`~chess.engine.MateGiven`.
    A positive value indicates an advantage.

    There is a total order defined on centi-pawn and mate scores.

    >>> from chess.engine import Cp, Mate, MateGiven
    >>>
    >>> Mate(-0) < Mate(-1) < Cp(-50) < Cp(200) < Mate(4) < Mate(1) < MateGiven
    True

    Scores can be negated to change the point of view:

    >>> -Cp(20)
    Cp(-20)

    >>> -Mate(-4)
    Mate(+4)

    >>> -Mate(0)
    MateGiven
    """

    @typing.overload
    @abc.abstractmethod
    def score(self, *, mate_score: int) -> int: ...
    @typing.overload
    @abc.abstractmethod
    def score(self, *, mate_score: Optional[int] = None) -> Optional[int]: ...
    @abc.abstractmethod
    def score(self, *, mate_score: Optional[int] = None) -> Optional[int]:
        """
        Returns the centi-pawn score as an integer or ``None``.

        You can optionally pass a large value to convert mate scores to
        centi-pawn scores.

        >>> Cp(-300).score()
        -300
        >>> Mate(5).score() is None
        True
        >>> Mate(5).score(mate_score=100000)
        99995
        """

    @abc.abstractmethod
    def mate(self) -> Optional[int]:
        """
        Returns the number of plies to mate, negative if we are getting
        mated, or ``None``.

        .. warning::
            This conflates ``Mate(0)`` (we lost) and ``MateGiven``
            (we won) to ``0``.
        """

    def is_mate(self) -> bool:
        """Tests if this is a mate score."""
        return self.mate() is not None

    @abc.abstractmethod
    def wdl(self, *, model: WdlModel = "sf", ply: int = 30) -> Wdl:
        """
        Returns statistics for the expected outcome of this game, based on
        a *model*, given that this score is reached at *ply*.

        Scores have a total order, but it makes little sense to compute
        the difference between two scores. For example, going from
        ``Cp(-100)`` to ``Cp(+100)`` is much more significant than going
        from ``Cp(+300)`` to ``Cp(+500)``. It is better to compute differences
        of the expectation values for the outcome of the game (based on winning
        chances and drawing chances).

        >>> Cp(100).wdl().expectation() - Cp(-100).wdl().expectation()  # doctest: +ELLIPSIS
        0.379...

        >>> Cp(500).wdl().expectation() - Cp(300).wdl().expectation()  # doctest: +ELLIPSIS
        0.015...

        :param model:
            * ``sf``, the WDL model used by the latest Stockfish
              (currently ``sf16``).
            * ``sf16``, the WDL model used by Stockfish 16.
            * ``sf15.1``, the WDL model used by Stockfish 15.1.
            * ``sf15``, the WDL model used by Stockfish 15.
            * ``sf14``, the WDL model used by Stockfish 14.
            * ``sf12``, the WDL model used by Stockfish 12.
            * ``lichess``, the win rate model used by Lichess.
              Does not use *ply*, and does not consider drawing chances.
        :param ply: The number of half-moves played since the starting
            position. Models may scale scores slightly differently based on
            this. Defaults to middle game.
        """

    @abc.abstractmethod
    def __neg__(self) -> Score:
        ...

    @abc.abstractmethod
    def __pos__(self) -> Score:
        ...

    @abc.abstractmethod
    def __abs__(self) -> Score:
        ...

    def _score_tuple(self) -> Tuple[bool, bool, bool, int, Optional[int]]:
        mate = self.mate()
        return (
            isinstance(self, MateGivenType),
            mate is not None and mate > 0,
            mate is None,
            -(mate or 0),
            self.score(),
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Score):
            return self._score_tuple() == other._score_tuple()
        else:
            return NotImplemented

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Score):
            return self._score_tuple() < other._score_tuple()
        else:
            return NotImplemented

    def __le__(self, other: object) -> bool:
        if isinstance(other, Score):
            return self._score_tuple() <= other._score_tuple()
        else:
            return NotImplemented

    def __gt__(self, other: object) -> bool:
        if isinstance(other, Score):
            return self._score_tuple() > other._score_tuple()
        else:
            return NotImplemented

    def __ge__(self, other: object) -> bool:
        if isinstance(other, Score):
            return self._score_tuple() >= other._score_tuple()
        else:
            return NotImplemented

class Cp(Score):
    """Centi-pawn score."""

    def __init__(self, cp: int) -> None:
        self.cp = cp

    def mate(self) -> None:
        return None

    def score(self, *, mate_score: Optional[int] = None) -> int:
        return self.cp

    def wdl(self, *, model: WdlModel = "sf", ply: int = 30) -> Wdl:
        if model == "lichess":
            wins = _lichess_raw_wins(max(-1000, min(self.cp, 1000)))
            losses = 1000 - wins
        elif model == "sf12":
            wins = _sf12_wins(self.cp, ply=ply)
            losses = _sf12_wins(-self.cp, ply=ply)
        elif model == "sf14":
            wins = _sf14_wins(self.cp, ply=ply)
            losses = _sf14_wins(-self.cp, ply=ply)
        elif model == "sf15":
            wins = _sf15_wins(self.cp, ply=ply)
            losses = _sf15_wins(-self.cp, ply=ply)
        elif model == "sf15.1":
            wins = _sf15_1_wins(self.cp, ply=ply)
            losses = _sf15_1_wins(-self.cp, ply=ply)
        elif model == "sf16":
            wins = _sf16_wins(self.cp, ply=ply)
            losses = _sf16_wins(-self.cp, ply=ply)
        else:
            wins = _sf16_1_wins(self.cp, ply=ply)
            losses = _sf16_1_wins(-self.cp, ply=ply)
        draws = 1000 - wins - losses
        return Wdl(wins, draws, losses)

    def __str__(self) -> str:
        return f"+{self.cp:d}" if self.cp > 0 else str(self.cp)

    def __repr__(self) -> str:
        return f"Cp({self})"

    def __neg__(self) -> Cp:
        return Cp(-self.cp)

    def __pos__(self) -> Cp:
        return Cp(self.cp)

    def __abs__(self) -> Cp:
        return Cp(abs(self.cp))


class Mate(Score):
    """Mate score."""

    def __init__(self, moves: int) -> None:
        self.moves = moves

    def mate(self) -> int:
        return self.moves

    @typing.overload
    def score(self, *, mate_score: int) -> int: ...
    @typing.overload
    def score(self, *, mate_score: Optional[int] = None) -> Optional[int]: ...
    def score(self, *, mate_score: Optional[int] = None) -> Optional[int]:
        if mate_score is None:
            return None
        elif self.moves > 0:
            return mate_score - self.moves
        else:
            return -mate_score - self.moves

    def wdl(self, *, model: WdlModel = "sf", ply: int = 30) -> Wdl:
        if model == "lichess":
            cp = (21 - min(10, abs(self.moves))) * 100
            wins = _lichess_raw_wins(cp)
            return Wdl(wins, 0, 1000 - wins) if self.moves > 0 else Wdl(1000 - wins, 0, wins)
        else:
            return Wdl(1000, 0, 0) if self.moves > 0 else Wdl(0, 0, 1000)

    def __str__(self) -> str:
        return f"#+{self.moves}" if self.moves > 0 else f"#-{abs(self.moves)}"

    def __repr__(self) -> str:
        return "Mate({})".format(str(self).lstrip("#"))

    def __neg__(self) -> Union[MateGivenType, Mate]:
        return MateGiven if not self.moves else Mate(-self.moves)

    def __pos__(self) -> Mate:
        return Mate(self.moves)

    def __abs__(self) -> Union[MateGivenType, Mate]:
        return MateGiven if not self.moves else Mate(abs(self.moves))


class MateGivenType(Score):
    """Winning mate score, equivalent to ``-Mate(0)``."""

    def mate(self) -> int:
        return 0

    @typing.overload
    def score(self, *, mate_score: int) -> int: ...
    @typing.overload
    def score(self, *, mate_score: Optional[int] = None) -> Optional[int]: ...
    def score(self, *, mate_score: Optional[int] = None) -> Optional[int]:
        return mate_score

    def wdl(self, *, model: WdlModel = "sf", ply: int = 30) -> Wdl:
        return Wdl(1000, 0, 0)

    def __neg__(self) -> Mate:
        return Mate(0)

    def __pos__(self) -> MateGivenType:
        return self

    def __abs__(self) -> MateGivenType:
        return self

    def __repr__(self) -> str:
        return "MateGiven"

    def __str__(self) -> str:
        return "#+0"

MateGiven = MateGivenType()