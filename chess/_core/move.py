from __future__ import annotations

import dataclasses
import typing
from typing import Optional, List, Optional, Iterator
from .types import PieceType, Square
from .utils import piece_symbol
from .errors import InvalidMoveError
from .constants import PIECE_SYMBOLS
from .squares import SQUARE_NAMES, A1

if typing.TYPE_CHECKING:
    from .board import Board

@dataclasses.dataclass(unsafe_hash=True)
class Move:
    """
    Represents a move from a square to a square and possibly the promotion
    piece type.

    Drops and null moves are supported.
    """

    from_square: Square
    """The source square."""

    to_square: Square
    """The target square."""

    promotion: Optional[PieceType] = None
    """The promotion piece type or ``None``."""

    drop: Optional[PieceType] = None
    """The drop piece type or ``None``."""

    def uci(self) -> str:
        """
        Gets a UCI string for the move.

        For example, a move from a7 to a8 would be ``a7a8`` or ``a7a8q``
        (if the latter is a promotion to a queen).

        The UCI representation of a null move is ``0000``.
        """
        if self.drop:
            return piece_symbol(self.drop).upper() + "@" + SQUARE_NAMES[self.to_square]
        elif self.promotion:
            return SQUARE_NAMES[self.from_square] + SQUARE_NAMES[self.to_square] + piece_symbol(self.promotion)
        elif self:
            return SQUARE_NAMES[self.from_square] + SQUARE_NAMES[self.to_square]
        else:
            return "0000"

    def xboard(self) -> str:
        return self.uci() if self else "@@@@"

    def __bool__(self) -> bool:
        return bool(self.from_square or self.to_square or self.promotion or self.drop)

    def __repr__(self) -> str:
        return f"Move.from_uci({self.uci()!r})"

    def __str__(self) -> str:
        return self.uci()

    @classmethod
    def from_uci(cls, uci: str) -> Move:
        """
        Parses a UCI string.

        :raises: :exc:`InvalidMoveError` if the UCI string is invalid.
        """
        if uci == "0000":
            return cls.null()
        elif len(uci) == 4 and "@" == uci[1]:
            try:
                drop = PIECE_SYMBOLS.index(uci[0].lower())
                square = SQUARE_NAMES.index(uci[2:])
            except ValueError:
                raise InvalidMoveError(f"invalid uci: {uci!r}")
            return cls(square, square, drop=drop)
        elif 4 <= len(uci) <= 5:
            try:
                from_square = SQUARE_NAMES.index(uci[0:2])
                to_square = SQUARE_NAMES.index(uci[2:4])
                promotion = PIECE_SYMBOLS.index(uci[4]) if len(uci) == 5 else None
            except ValueError:
                raise InvalidMoveError(f"invalid uci: {uci!r}")
            if from_square == to_square and from_square != A1:
                raise InvalidMoveError(f"invalid uci (use 0000 for null moves): {uci!r}")
            return cls(from_square, to_square, promotion=promotion)
        else:
            raise InvalidMoveError(f"expected uci string to be of length 4 or 5: {uci!r}")

    @classmethod
    def null(cls) -> Move:
        """
        Gets a null move.

        A null move just passes the turn to the other side (and possibly
        forfeits en passant capturing). Null moves evaluate to ``False`` in
        boolean contexts.

        >>> import chess
        >>>
        >>> bool(chess.Move.null())
        False
        """
        return cls(0, 0)


class PseudoLegalMoveGenerator:

    def __init__(self, board: Board) -> None:
        self.board = board

    def __bool__(self) -> bool:
        return any(self.board.generate_pseudo_legal_moves())

    def count(self) -> int:
        # List conversion is faster than iterating.
        return len(list(self))

    def __iter__(self) -> Iterator[Move]:
        return self.board.generate_pseudo_legal_moves()

    def __contains__(self, move: Move) -> bool:
        return self.board.is_pseudo_legal(move)

    def __repr__(self) -> str:
        builder: List[str] = []

        for move in self:
            if self.board.is_legal(move):
                builder.append(self.board.san(move))
            else:
                builder.append(self.board.uci(move))

        sans = ", ".join(builder)
        return f"<PseudoLegalMoveGenerator at {id(self):#x} ({sans})>"


class LegalMoveGenerator:

    def __init__(self, board: Board) -> None:
        self.board = board

    def __bool__(self) -> bool:
        return any(self.board.generate_legal_moves())

    def count(self) -> int:
        # List conversion is faster than iterating.
        return len(list(self))

    def __iter__(self) -> Iterator[Move]:
        return self.board.generate_legal_moves()

    def __contains__(self, move: Move) -> bool:
        return self.board.is_legal(move)

    def __repr__(self) -> str:
        sans = ", ".join(self.board.san(move) for move in self)
        return f"<LegalMoveGenerator at {id(self):#x} ({sans})>"