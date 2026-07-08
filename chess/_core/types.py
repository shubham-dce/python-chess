from typing_extensions import TypeAlias
from typing import Literal

Color: TypeAlias = bool
ColorName = Literal["white", "black"]
EnPassantSpec = Literal["legal", "fen", "xfen"]
PieceType: TypeAlias = int
File: TypeAlias = int
Rank: TypeAlias = int
Square: TypeAlias = int
Bitboard: TypeAlias = int