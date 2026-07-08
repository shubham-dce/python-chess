from __future__ import annotations

import dataclasses

from .types import PieceType, Color
from .utils import piece_symbol
from .constants import UNICODE_PIECE_SYMBOLS, PIECE_SYMBOLS

@dataclasses.dataclass
class Piece:
    """A piece with type and color."""

    piece_type: PieceType
    """The piece type."""

    color: Color
    """The piece color."""

    def symbol(self) -> str:
        """
        Gets the symbol ``P``, ``N``, ``B``, ``R``, ``Q`` or ``K`` for white
        pieces or the lower-case variants for the black pieces.
        """
        symbol = piece_symbol(self.piece_type)
        return symbol.upper() if self.color else symbol

    def unicode_symbol(self, *, invert_color: bool = False) -> str:
        """
        Gets the Unicode character for the piece.
        """
        symbol = self.symbol().swapcase() if invert_color else self.symbol()
        return UNICODE_PIECE_SYMBOLS[symbol]

    def __hash__(self) -> int:
        return self.piece_type + (-1 if self.color else 5)

    def __repr__(self) -> str:
        return f"Piece.from_symbol({self.symbol()!r})"

    def __str__(self) -> str:
        return self.symbol()

    def _repr_svg_(self) -> str:
        import chess.svg
        return chess.svg.piece(self, size=45)

    @classmethod
    def from_symbol(cls, symbol: str) -> Piece:
        """
        Creates a :class:`~chess.Piece` instance from a piece symbol.

        :raises: :exc:`ValueError` if the symbol is invalid.
        """
        return cls(PIECE_SYMBOLS.index(symbol.lower()), symbol.isupper())