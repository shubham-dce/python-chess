import enum
import dataclasses
from typing import Optional
from .types import Color

"""
    The game_state.py handles the state of the game - including the various possible scenarios in the game, the termination states, and the outcome states. 
"""

class Status(enum.IntFlag):
    VALID = 0
    NO_WHITE_KING = 1 << 0
    NO_BLACK_KING = 1 << 1
    TOO_MANY_KINGS = 1 << 2
    TOO_MANY_WHITE_PAWNS = 1 << 3
    TOO_MANY_BLACK_PAWNS = 1 << 4
    PAWNS_ON_BACKRANK = 1 << 5
    TOO_MANY_WHITE_PIECES = 1 << 6
    TOO_MANY_BLACK_PIECES = 1 << 7
    BAD_CASTLING_RIGHTS = 1 << 8
    INVALID_EP_SQUARE = 1 << 9
    OPPOSITE_CHECK = 1 << 10
    EMPTY = 1 << 11
    RACE_CHECK = 1 << 12
    RACE_OVER = 1 << 13
    RACE_MATERIAL = 1 << 14
    TOO_MANY_CHECKERS = 1 << 15
    IMPOSSIBLE_CHECK = 1 << 16

STATUS_VALID = Status.VALID
STATUS_NO_WHITE_KING = Status.NO_WHITE_KING
STATUS_NO_BLACK_KING = Status.NO_BLACK_KING
STATUS_TOO_MANY_KINGS = Status.TOO_MANY_KINGS
STATUS_TOO_MANY_WHITE_PAWNS = Status.TOO_MANY_WHITE_PAWNS
STATUS_TOO_MANY_BLACK_PAWNS = Status.TOO_MANY_BLACK_PAWNS
STATUS_PAWNS_ON_BACKRANK = Status.PAWNS_ON_BACKRANK
STATUS_TOO_MANY_WHITE_PIECES = Status.TOO_MANY_WHITE_PIECES
STATUS_TOO_MANY_BLACK_PIECES = Status.TOO_MANY_BLACK_PIECES
STATUS_BAD_CASTLING_RIGHTS = Status.BAD_CASTLING_RIGHTS
STATUS_INVALID_EP_SQUARE = Status.INVALID_EP_SQUARE
STATUS_OPPOSITE_CHECK = Status.OPPOSITE_CHECK
STATUS_EMPTY = Status.EMPTY
STATUS_RACE_CHECK = Status.RACE_CHECK
STATUS_RACE_OVER = Status.RACE_OVER
STATUS_RACE_MATERIAL = Status.RACE_MATERIAL
STATUS_TOO_MANY_CHECKERS = Status.TOO_MANY_CHECKERS
STATUS_IMPOSSIBLE_CHECK = Status.IMPOSSIBLE_CHECK


class Termination(enum.Enum):
    """Enum with reasons for a game to be over."""

    CHECKMATE = enum.auto()
    """See :func:`chess.Board.is_checkmate()`."""
    STALEMATE = enum.auto()
    """See :func:`chess.Board.is_stalemate()`."""
    INSUFFICIENT_MATERIAL = enum.auto()
    """See :func:`chess.Board.is_insufficient_material()`."""
    SEVENTYFIVE_MOVES = enum.auto()
    """See :func:`chess.Board.is_seventyfive_moves()`."""
    FIVEFOLD_REPETITION = enum.auto()
    """See :func:`chess.Board.is_fivefold_repetition()`."""
    FIFTY_MOVES = enum.auto()
    """See :func:`chess.Board.can_claim_fifty_moves()`."""
    THREEFOLD_REPETITION = enum.auto()
    """See :func:`chess.Board.can_claim_threefold_repetition()`."""
    VARIANT_WIN = enum.auto()
    """See :func:`chess.Board.is_variant_win()`."""
    VARIANT_LOSS = enum.auto()
    """See :func:`chess.Board.is_variant_loss()`."""
    VARIANT_DRAW = enum.auto()
    """See :func:`chess.Board.is_variant_draw()`."""

@dataclasses.dataclass
class Outcome:
    """
    Information about the outcome of an ended game, usually obtained from
    :func:`chess.Board.outcome()`.
    """

    termination: Termination
    """The reason for the game to have ended."""

    winner: Optional[Color]
    """The winning color or ``None`` if drawn."""

    def result(self) -> str:
        """Returns ``1-0``, ``0-1`` or ``1/2-1/2``."""
        return "1/2-1/2" if self.winner is None else ("1-0" if self.winner else "0-1")