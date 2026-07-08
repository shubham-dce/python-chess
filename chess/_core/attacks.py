from typing import List, Iterable, Dict, Tuple, Iterator
from .types import Square, Bitboard
from .squares import SQUARES, square_distance, square_file, square_rank
from .bitboard import BB_EMPTY, BB_SQUARES, BB_ALL, BB_FILES, BB_RANKS, BB_RANK_1, BB_RANK_8, BB_FILE_A, BB_FILE_H


def _sliding_attacks(square: Square, occupied: Bitboard, deltas: Iterable[int]) -> Bitboard:
    attacks = BB_EMPTY

    for delta in deltas:
        sq = square

        while True:
            sq += delta
            if not (0 <= sq < 64) or square_distance(sq, sq - delta) > 2:
                break

            attacks |= BB_SQUARES[sq]

            if occupied & BB_SQUARES[sq]:
                break

    return attacks

def _step_attacks(square: Square, deltas: Iterable[int]) -> Bitboard:
    return _sliding_attacks(square, BB_ALL, deltas)

# The attacked squares by the pieces that moves only one step at a time - knights, king and pawn
BB_KNIGHT_ATTACKS: List[Bitboard] = [_step_attacks(sq, [17, 15, 10, 6, -17, -15, -10, -6]) for sq in SQUARES]
BB_KING_ATTACKS: List[Bitboard] = [_step_attacks(sq, [9, 8, 7, 1, -9, -8, -7, -1]) for sq in SQUARES]
BB_PAWN_ATTACKS: List[List[Bitboard]] = [[_step_attacks(sq, deltas) for sq in SQUARES] for deltas in [[-7, -9], [7, 9]]]


def _edges(square: Square) -> Bitboard:
    return (((BB_RANK_1 | BB_RANK_8) & ~BB_RANKS[square_rank(square)]) |
            ((BB_FILE_A | BB_FILE_H) & ~BB_FILES[square_file(square)]))

def _carry_rippler(mask: Bitboard) -> Iterator[Bitboard]:
    # Carry-Rippler trick to iterate subsets of mask.
    subset = BB_EMPTY
    while True:
        yield subset
        subset = (subset - mask) & mask
        if not subset:
            break

def _attack_table(deltas: List[int]) -> Tuple[List[Bitboard], List[Dict[Bitboard, Bitboard]]]:
    mask_table: List[Bitboard] = []
    attack_table: List[Dict[Bitboard, Bitboard]] = []

    for square in SQUARES:
        attacks = {}

        # replaced 0 with the BB_EMPTY
        mask = _sliding_attacks(square, BB_EMPTY, deltas) & ~_edges(square)
        for subset in _carry_rippler(mask):
            attacks[subset] = _sliding_attacks(square, subset, deltas)

        attack_table.append(attacks)
        mask_table.append(mask)

    return mask_table, attack_table 

BB_DIAG_MASKS, BB_DIAG_ATTACKS = _attack_table([-9, -7, 7, 9])
BB_FILE_MASKS, BB_FILE_ATTACKS = _attack_table([-8, 8])
BB_RANK_MASKS, BB_RANK_ATTACKS = _attack_table([-1, 1])


def _rays() -> List[List[Bitboard]]:
    rays: List[List[Bitboard]] = []
    for a, bb_a in enumerate(BB_SQUARES):
        rays_row: List[Bitboard] = []
        for b, bb_b in enumerate(BB_SQUARES):
            if BB_DIAG_ATTACKS[a][0] & bb_b:
                rays_row.append((BB_DIAG_ATTACKS[a][0] & BB_DIAG_ATTACKS[b][0]) | bb_a | bb_b)
            elif BB_RANK_ATTACKS[a][0] & bb_b:
                rays_row.append(BB_RANK_ATTACKS[a][0] | bb_a)
            elif BB_FILE_ATTACKS[a][0] & bb_b:
                rays_row.append(BB_FILE_ATTACKS[a][0] | bb_a)
            else:
                rays_row.append(BB_EMPTY)
        rays.append(rays_row)
    return rays

BB_RAYS = _rays()

def ray(a: Square, b: Square) -> Bitboard:
    return BB_RAYS[a][b]

def between(a: Square, b: Square) -> Bitboard:
    bb = BB_RAYS[a][b] & ((BB_ALL << a) ^ (BB_ALL << b))
    return bb & (bb - 1)