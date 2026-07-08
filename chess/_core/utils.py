from .types import PieceType
from .constants import PIECE_SYMBOLS, PIECE_NAMES
import typing

'''
    provides the either the piece symbol or piece name using the piece type
    piece_type: int = 4 (ROOK) -> PIECE_SYMBOLS[4] = "r"
    piece_type: int = 4 (ROOK) -> PIECE_NAMES[4] = "rook"

    ---- In constants.py ----
    PIECE_SYMBOLS = [None, "p", "n", "b", "r", "q", "k"]
    PIECE_NAMES = [None, "pawn", "knight", "bishop", "rook", "queen", "king"]
'''
def piece_symbol(piece_type: PieceType) -> str:
    return typing.cast(str, PIECE_SYMBOLS[piece_type])

def piece_name(piece_type: PieceType) -> str:
    return typing.cast(str, PIECE_NAMES[piece_type])