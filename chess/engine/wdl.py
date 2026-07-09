from __future__ import annotations

import dataclasses
import math

import chess
from chess import Color
from typing import Literal

WdlModel = Literal["sf", "sf16.1", "sf16", "sf15.1", "sf15", "sf14", "sf12", "lichess"]

def _sf16_1_wins(cp: int, *, ply: int) -> int:
    # https://github.com/official-stockfish/Stockfish/blob/sf_16.1/src/uci.cpp#L48
    NormalizeToPawnValue = 356
    # https://github.com/official-stockfish/Stockfish/blob/sf_16.1/src/uci.cpp#L383-L384
    m = min(120, max(8, ply / 2 + 1)) / 32
    a = (((-1.06249702 * m + 7.42016937) * m + 0.89425629) * m) + 348.60356174
    b = (((-5.33122190 * m + 39.57831533) * m + -90.84473771) * m) + 123.40620748
    x = min(4000, max(cp * NormalizeToPawnValue / 100, -4000))
    return int(0.5 + 1000 / (1 + math.exp((a - x) / b)))

def _sf16_wins(cp: int, *, ply: int) -> int:
    # https://github.com/official-stockfish/Stockfish/blob/sf_16/src/uci.h#L38
    NormalizeToPawnValue = 328
    # https://github.com/official-stockfish/Stockfish/blob/sf_16/src/uci.cpp#L200-L224
    m = min(240, max(ply, 0)) / 64
    a = (((0.38036525 * m + -2.82015070) * m + 23.17882135) * m) + 307.36768407
    b = (((-2.29434733 * m + 13.27689788) * m + -14.26828904) * m) + 63.45318330
    x = min(4000, max(cp * NormalizeToPawnValue / 100, -4000))
    return int(0.5 + 1000 / (1 + math.exp((a - x) / b)))

def _sf15_1_wins(cp: int, *, ply: int) -> int:
    # https://github.com/official-stockfish/Stockfish/blob/sf_15.1/src/uci.h#L38
    NormalizeToPawnValue = 361
    # https://github.com/official-stockfish/Stockfish/blob/sf_15.1/src/uci.cpp#L200-L224
    m = min(240, max(ply, 0)) / 64
    a = (((-0.58270499 * m + 2.68512549) * m + 15.24638015) * m) + 344.49745382
    b = (((-2.65734562 * m + 15.96509799) * m + -20.69040836) * m) + 73.61029937
    x = min(4000, max(cp * NormalizeToPawnValue / 100, -4000))
    return int(0.5 + 1000 / (1 + math.exp((a - x) / b)))

def _sf15_wins(cp: int, *, ply: int) -> int:
    # https://github.com/official-stockfish/Stockfish/blob/sf_15/src/uci.cpp#L200-L220
    m = min(240, max(ply, 0)) / 64
    a = (((-1.17202460e-1 * m + 5.94729104e-1) * m + 1.12065546e+1) * m) + 1.22606222e+2
    b = (((-1.79066759 * m + 11.30759193) * m + -17.43677612) * m) + 36.47147479
    x = min(2000, max(cp, -2000))
    return int(0.5 + 1000 / (1 + math.exp((a - x) / b)))

def _sf14_wins(cp: int, *, ply: int) -> int:
    # https://github.com/official-stockfish/Stockfish/blob/sf_14/src/uci.cpp#L200-L220
    m = min(240, max(ply, 0)) / 64
    a = (((-3.68389304 * m + 30.07065921) * m + -60.52878723) * m) + 149.53378557
    b = (((-2.01818570 * m + 15.85685038) * m + -29.83452023) * m) + 47.59078827
    x = min(2000, max(cp, -2000))
    return int(0.5 + 1000 / (1 + math.exp((a - x) / b)))

def _sf12_wins(cp: int, *, ply: int) -> int:
    # https://github.com/official-stockfish/Stockfish/blob/sf_12/src/uci.cpp#L198-L218
    m = min(240, max(ply, 0)) / 64
    a = (((-8.24404295 * m + 64.23892342) * m + -95.73056462) * m) + 153.86478679
    b = (((-3.37154371 * m + 28.44489198) * m + -56.67657741) * m) + 72.05858751
    x = min(1000, max(cp, -1000))
    return int(0.5 + 1000 / (1 + math.exp((a - x) / b)))

def _lichess_raw_wins(cp: int) -> int:
    # https://github.com/lichess-org/lila/pull/11148
    # https://github.com/lichess-org/lila/blob/2242b0a08faa06e7be5508d338ede7bb09049777/modules/analyse/src/main/WinPercent.scala#L26-L30
    return round(1000 / (1 + math.exp(-0.00368208 * cp)))

@dataclasses.dataclass
class PovWdl:
    """
    Relative :class:`win/draw/loss statistics <chess.engine.Wdl>` and the point
    of view.
    """

    relative: Wdl
    """The relative :class:`~chess.engine.Wdl`."""

    turn: Color
    """The point of view (``chess.WHITE`` or ``chess.BLACK``)."""

    def white(self) -> Wdl:
        """Gets the :class:`~chess.engine.Wdl` from White's point of view."""
        return self.pov(chess.WHITE)

    def black(self) -> Wdl:
        """Gets the :class:`~chess.engine.Wdl` from Black's point of view."""
        return self.pov(chess.BLACK)

    def pov(self, color: Color) -> Wdl:
        """
        Gets the :class:`~chess.engine.Wdl` from the point of view of the given
        *color*.
        """
        return self.relative if self.turn == color else -self.relative

    def __bool__(self) -> bool:
        return bool(self.relative)

    def __repr__(self) -> str:
        return "PovWdl({!r}, {})".format(self.relative, "WHITE" if self.turn else "BLACK")


@dataclasses.dataclass
class Wdl:
    """Win/draw/loss statistics."""

    wins: int
    """The number of wins."""

    draws: int
    """The number of draws."""

    losses: int
    """The number of losses."""

    def total(self) -> int:
        """
        Returns the total number of games. Usually, ``wdl`` reported by engines
        is scaled to 1000 games.
        """
        return self.wins + self.draws + self.losses

    def winning_chance(self) -> float:
        """Returns the relative frequency of wins."""
        return self.wins / self.total()

    def drawing_chance(self) -> float:
        """Returns the relative frequency of draws."""
        return self.draws / self.total()

    def losing_chance(self) -> float:
        """Returns the relative frequency of losses."""
        return self.losses / self.total()

    def expectation(self) -> float:
        """
        Returns the expectation value, where a win is valued 1, a draw is
        valued 0.5, and a loss is valued 0.
        """
        return (self.wins + 0.5 * self.draws) / self.total()

    def __bool__(self) -> bool:
        return bool(self.total())

    def __pos__(self) -> Wdl:
        return self

    def __neg__(self) -> Wdl:
        return Wdl(self.losses, self.draws, self.wins)