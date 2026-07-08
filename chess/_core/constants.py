import re
from typing import List
from .types import Color, ColorName, PieceType, File, Rank

WHITE: Color = True
BLACK: Color = False
COLORS: List[Color] = [WHITE, BLACK]
COLOR_NAMES: List[ColorName] = ["black", "white"]

PAWN: PieceType = 1
KNIGHT: PieceType = 2
BISHOP: PieceType = 3
ROOK: PieceType = 4
QUEEN: PieceType = 5
KING: PieceType = 6
PIECE_TYPES: List[PieceType] = [PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING]
PIECE_SYMBOLS = [None, "p", "n", "b", "r", "q", "k"]
PIECE_NAMES = [None, "pawn", "knight", "bishop", "rook", "queen", "king"]

UNICODE_PIECE_SYMBOLS = {
    "R": "♖", "r": "♜",
    "N": "♘", "n": "♞",
    "B": "♗", "b": "♝",
    "Q": "♕", "q": "♛",
    "K": "♔", "k": "♚",
    "P": "♙", "p": "♟",
}

FILE_A: File = 0
FILE_B: File = 1
FILE_C: File = 2
FILE_D: File = 3
FILE_E: File = 4
FILE_F: File = 5
FILE_G: File = 6
FILE_H: File = 7
FILES = [FILE_A, FILE_B, FILE_C, FILE_D, FILE_E, FILE_F, FILE_G, FILE_H]
FILE_NAMES = ["a", "b", "c", "d", "e", "f", "g", "h"]

RANK_1: Rank = 0
RANK_2: Rank = 1
RANK_3: Rank = 2
RANK_4: Rank = 3
RANK_5: Rank = 4
RANK_6: Rank = 5
RANK_7: Rank = 6
RANK_8: Rank = 7
RANKS = [RANK_1, RANK_2, RANK_3, RANK_4, RANK_5, RANK_6, RANK_7, RANK_8]
RANK_NAMES = ["1", "2", "3", "4", "5", "6", "7", "8"]

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
"""The FEN for the standard chess starting position."""

STARTING_BOARD_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
"""The board part of the FEN for the standard chess starting position."""

SAN_REGEX = re.compile(r"^([NBKRQ])?([a-h])?([1-8])?[\-x]?([a-h][1-8])(=?[nbrqkNBRQK])?[\+#]?\Z")

FEN_CASTLING_REGEX = re.compile(r"^(?:-|[KQABCDEFGH]{0,2}[kqabcdefgh]{0,2})\Z")
