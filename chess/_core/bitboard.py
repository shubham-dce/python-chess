from .types import Bitboard, Square
from .squares import A1, B1, C1, D1, E1, F1, G1, H1, A2, B2, C2, D2, E2, F2, G2, H2, A3, B3, C3, D3, E3, F3, G3, H3, A4, B4, C4, D4, E4, F4, G4, H4, A5, B5, C5, D5, E5, F5, G5, H5, A6, B6, C6, D6, E6, F6, G6, H6, A7, B7, C7, D7, E7, F7, G7, H7, A8, B8, C8, D8, E8, F8, G8, H8, SQUARES
from .constants import FILE_A, FILE_B, FILE_C, FILE_D, FILE_E, FILE_F, FILE_G, FILE_H, RANK_1, RANK_2, RANK_3, RANK_4, RANK_5, RANK_6, RANK_7, RANK_8
from typing import List, Callable, Iterator

"""
    Presentation of the chess board using bits. Chess board has 64 squares and the bitboard contains a 64 bits with 1 bit representing each square. 
"""

BB_EMPTY: Bitboard = 0
BB_ALL: Bitboard = 0xffff_ffff_ffff_ffff

BB_A1: Bitboard = 1 << A1
BB_B1: Bitboard = 1 << B1
BB_C1: Bitboard = 1 << C1
BB_D1: Bitboard = 1 << D1
BB_E1: Bitboard = 1 << E1
BB_F1: Bitboard = 1 << F1
BB_G1: Bitboard = 1 << G1
BB_H1: Bitboard = 1 << H1
BB_A2: Bitboard = 1 << A2
BB_B2: Bitboard = 1 << B2
BB_C2: Bitboard = 1 << C2
BB_D2: Bitboard = 1 << D2
BB_E2: Bitboard = 1 << E2
BB_F2: Bitboard = 1 << F2
BB_G2: Bitboard = 1 << G2
BB_H2: Bitboard = 1 << H2
BB_A3: Bitboard = 1 << A3
BB_B3: Bitboard = 1 << B3
BB_C3: Bitboard = 1 << C3
BB_D3: Bitboard = 1 << D3
BB_E3: Bitboard = 1 << E3
BB_F3: Bitboard = 1 << F3
BB_G3: Bitboard = 1 << G3
BB_H3: Bitboard = 1 << H3
BB_A4: Bitboard = 1 << A4
BB_B4: Bitboard = 1 << B4
BB_C4: Bitboard = 1 << C4
BB_D4: Bitboard = 1 << D4
BB_E4: Bitboard = 1 << E4
BB_F4: Bitboard = 1 << F4
BB_G4: Bitboard = 1 << G4
BB_H4: Bitboard = 1 << H4
BB_A5: Bitboard = 1 << A5
BB_B5: Bitboard = 1 << B5
BB_C5: Bitboard = 1 << C5
BB_D5: Bitboard = 1 << D5
BB_E5: Bitboard = 1 << E5
BB_F5: Bitboard = 1 << F5
BB_G5: Bitboard = 1 << G5
BB_H5: Bitboard = 1 << H5
BB_A6: Bitboard = 1 << A6
BB_B6: Bitboard = 1 << B6
BB_C6: Bitboard = 1 << C6
BB_D6: Bitboard = 1 << D6
BB_E6: Bitboard = 1 << E6
BB_F6: Bitboard = 1 << F6
BB_G6: Bitboard = 1 << G6
BB_H6: Bitboard = 1 << H6
BB_A7: Bitboard = 1 << A7
BB_B7: Bitboard = 1 << B7
BB_C7: Bitboard = 1 << C7
BB_D7: Bitboard = 1 << D7
BB_E7: Bitboard = 1 << E7
BB_F7: Bitboard = 1 << F7
BB_G7: Bitboard = 1 << G7
BB_H7: Bitboard = 1 << H7
BB_A8: Bitboard = 1 << A8
BB_B8: Bitboard = 1 << B8
BB_C8: Bitboard = 1 << C8
BB_D8: Bitboard = 1 << D8
BB_E8: Bitboard = 1 << E8
BB_F8: Bitboard = 1 << F8
BB_G8: Bitboard = 1 << G8
BB_H8: Bitboard = 1 << H8
BB_SQUARES: List[Bitboard] = [1 << sq for sq in SQUARES]

BB_CORNERS: Bitboard = BB_A1 | BB_H1 | BB_A8 | BB_H8
BB_CENTER: Bitboard = BB_D4 | BB_E4 | BB_D5 | BB_E5

BB_LIGHT_SQUARES: Bitboard = 0x55aa_55aa_55aa_55aa
BB_DARK_SQUARES: Bitboard = 0xaa55_aa55_aa55_aa55

BB_FILE_A: Bitboard = 0x0101_0101_0101_0101 << FILE_A
BB_FILE_B: Bitboard = 0x0101_0101_0101_0101 << FILE_B
BB_FILE_C: Bitboard = 0x0101_0101_0101_0101 << FILE_C
BB_FILE_D: Bitboard = 0x0101_0101_0101_0101 << FILE_D
BB_FILE_E: Bitboard = 0x0101_0101_0101_0101 << FILE_E
BB_FILE_F: Bitboard = 0x0101_0101_0101_0101 << FILE_F
BB_FILE_G: Bitboard = 0x0101_0101_0101_0101 << FILE_G
BB_FILE_H: Bitboard = 0x0101_0101_0101_0101 << FILE_H
BB_FILES: List[Bitboard] = [BB_FILE_A, BB_FILE_B, BB_FILE_C, BB_FILE_D, BB_FILE_E, BB_FILE_F, BB_FILE_G, BB_FILE_H]

BB_RANK_1: Bitboard = 0xff << (8 * RANK_1)
BB_RANK_2: Bitboard = 0xff << (8 * RANK_2)
BB_RANK_3: Bitboard = 0xff << (8 * RANK_3)
BB_RANK_4: Bitboard = 0xff << (8 * RANK_4)
BB_RANK_5: Bitboard = 0xff << (8 * RANK_5)
BB_RANK_6: Bitboard = 0xff << (8 * RANK_6)
BB_RANK_7: Bitboard = 0xff << (8 * RANK_7)
BB_RANK_8: Bitboard = 0xff << (8 * RANK_8)
BB_RANKS: List[Bitboard] = [BB_RANK_1, BB_RANK_2, BB_RANK_3, BB_RANK_4, BB_RANK_5, BB_RANK_6, BB_RANK_7, BB_RANK_8]

BB_BACKRANKS: Bitboard = BB_RANK_1 | BB_RANK_8

def least_significant_bit(bb: Bitboard) -> int:
    return (bb & -bb).bit_length() - 1

lsb = least_significant_bit

def scan_forward(bb: Bitboard) -> Iterator[Square]:
    while bb:
        r = bb & -bb
        yield r.bit_length() - 1
        bb ^= r

def most_significant_bit(bb: Bitboard) -> int:
    return bb.bit_length() - 1

msb = most_significant_bit

def scan_reversed(bb: Bitboard) -> Iterator[Square]:
    while bb:
        r = bb.bit_length() - 1
        yield r
        bb ^= BB_SQUARES[r]

# Python 3.10 or fallback.

population_chess_board: Callable[[Bitboard], int] = getattr(int, "bit_count", lambda bb: bin(bb).count("1"))

popcount = population_chess_board

def flip_vertical(bb: Bitboard) -> Bitboard:
    # https://www.chessprogramming.org/Flipping_Mirroring_and_Rotating#FlipVertically
    bb = ((bb >> 8) & 0x00ff_00ff_00ff_00ff) | ((bb & 0x00ff_00ff_00ff_00ff) << 8)
    bb = ((bb >> 16) & 0x0000_ffff_0000_ffff) | ((bb & 0x0000_ffff_0000_ffff) << 16)
    bb = (bb >> 32) | ((bb & 0x0000_0000_ffff_ffff) << 32)
    return bb

def flip_horizontal(bb: Bitboard) -> Bitboard:
    # https://www.chessprogramming.org/Flipping_Mirroring_and_Rotating#MirrorHorizontally
    bb = ((bb >> 1) & 0x5555_5555_5555_5555) | ((bb & 0x5555_5555_5555_5555) << 1)
    bb = ((bb >> 2) & 0x3333_3333_3333_3333) | ((bb & 0x3333_3333_3333_3333) << 2)
    bb = ((bb >> 4) & 0x0f0f_0f0f_0f0f_0f0f) | ((bb & 0x0f0f_0f0f_0f0f_0f0f) << 4)
    return bb

def flip_diagonal(bb: Bitboard) -> Bitboard:
    # https://www.chessprogramming.org/Flipping_Mirroring_and_Rotating#FlipabouttheDiagonal
    t = (bb ^ (bb << 28)) & 0x0f0f_0f0f_0000_0000
    bb = bb ^ t ^ (t >> 28)
    t = (bb ^ (bb << 14)) & 0x3333_0000_3333_0000
    bb = bb ^ t ^ (t >> 14)
    t = (bb ^ (bb << 7)) & 0x5500_5500_5500_5500
    bb = bb ^ t ^ (t >> 7)
    return bb

def flip_anti_diagonal(bb: Bitboard) -> Bitboard:
    # https://www.chessprogramming.org/Flipping_Mirroring_and_Rotating#FlipabouttheAntidiagonal
    t = bb ^ (bb << 36)
    bb = bb ^ ((t ^ (bb >> 36)) & 0xf0f0_f0f0_0f0f_0f0f)
    t = (bb ^ (bb << 18)) & 0xcccc_0000_cccc_0000
    bb = bb ^ t ^ (t >> 18)
    t = (bb ^ (bb << 9)) & 0xaa00_aa00_aa00_aa00
    bb = bb ^ t ^ (t >> 9)
    return bb


def shift_down(b: Bitboard) -> Bitboard:
    return b >> 8

def shift_2_down(b: Bitboard) -> Bitboard:
    return b >> 16

def shift_up(b: Bitboard) -> Bitboard:
    return (b << 8) & BB_ALL

def shift_2_up(b: Bitboard) -> Bitboard:
    return (b << 16) & BB_ALL

def shift_right(b: Bitboard) -> Bitboard:
    return (b << 1) & ~BB_FILE_A & BB_ALL

def shift_2_right(b: Bitboard) -> Bitboard:
    return (b << 2) & ~BB_FILE_A & ~BB_FILE_B & BB_ALL

def shift_left(b: Bitboard) -> Bitboard:
    return (b >> 1) & ~BB_FILE_H

def shift_2_left(b: Bitboard) -> Bitboard:
    return (b >> 2) & ~BB_FILE_G & ~BB_FILE_H

def shift_up_left(b: Bitboard) -> Bitboard:
    return (b << 7) & ~BB_FILE_H & BB_ALL

def shift_up_right(b: Bitboard) -> Bitboard:
    return (b << 9) & ~BB_FILE_A & BB_ALL

def shift_down_left(b: Bitboard) -> Bitboard:
    return (b >> 9) & ~BB_FILE_H

def shift_down_right(b: Bitboard) -> Bitboard:
    return (b >> 7) & ~BB_FILE_A