from __future__ import annotations

from typing import List, Dict, Optional, Callable, TypeVar, Self, Mapping, Type
import typing

from .bitboard import popcount, lsb, msb

from .types import PieceType, Color, Bitboard, Square

from .constants import STARTING_BOARD_FEN, WHITE, BLACK, PAWN, BISHOP, KNIGHT, ROOK, QUEEN, KING, PIECE_SYMBOLS, RANK_NAMES

from .bitboard import BB_EMPTY, BB_RANK_2, BB_RANK_7, BB_B1, BB_G1, BB_SQUARES, BB_RANK_1, BB_RANK_8, BB_G1, BB_B8, BB_G8, BB_C1, BB_F1, BB_C8, BB_F8, BB_CORNERS, BB_D1, BB_D8, BB_E1, BB_E8, BB_BACKRANKS, flip_vertical, scan_reversed

from .piece import Piece

from .attacks import BB_PAWN_ATTACKS, BB_KNIGHT_ATTACKS, BB_DIAG_ATTACKS, BB_DIAG_MASKS, BB_RANK_ATTACKS, BB_RANK_MASKS, BB_FILE_ATTACKS, BB_KING_ATTACKS, BB_FILE_MASKS, BB_SQUARES, BB_FILES, BB_EMPTY, BB_ALL, BB_FILE_H, BB_RANK_1, BB_RANK_8, Bitboard

from .squares import SQUARES_180, A1, H1, square

from .attacks import ray, between

from .squareset import *

BaseBoardT = TypeVar("BaseBoardT", bound="BaseBoard")

class BaseBoard:
    """
    A board representing the position of chess pieces. See
    :class:`~chess.Board` for a full board with move generation.

    The board is initialized with the standard chess starting position, unless
    otherwise specified in the optional *board_fen* argument. If *board_fen*
    is ``None``, an empty board is created.
    """

    def __init__(self, board_fen: Optional[str] = STARTING_BOARD_FEN) -> None:
        self.occupied_co = [BB_EMPTY, BB_EMPTY]

        if board_fen is None:
            self._clear_board()
        elif board_fen == STARTING_BOARD_FEN:
            self._reset_board()
        else:
            self._set_board_fen(board_fen)

    def _reset_board(self) -> None:
        self.pawns = BB_RANK_2 | BB_RANK_7
        self.knights = BB_B1 | BB_G1 | BB_B8 | BB_G8
        self.bishops = BB_C1 | BB_F1 | BB_C8 | BB_F8
        self.rooks = BB_CORNERS
        self.queens = BB_D1 | BB_D8
        self.kings = BB_E1 | BB_E8

        self.promoted = BB_EMPTY

        self.occupied_co[WHITE] = BB_RANK_1 | BB_RANK_2
        self.occupied_co[BLACK] = BB_RANK_7 | BB_RANK_8
        self.occupied = BB_RANK_1 | BB_RANK_2 | BB_RANK_7 | BB_RANK_8

    def reset_board(self) -> None:
        """
        Resets pieces to the starting position.

        :class:`~chess.Board` also resets the move stack, but not turn,
        castling rights and move counters. Use :func:`chess.Board.reset()` to
        fully restore the starting position.
        """
        self._reset_board()

    def _clear_board(self) -> None:
        self.pawns = BB_EMPTY
        self.knights = BB_EMPTY
        self.bishops = BB_EMPTY
        self.rooks = BB_EMPTY
        self.queens = BB_EMPTY
        self.kings = BB_EMPTY

        self.promoted = BB_EMPTY

        self.occupied_co[WHITE] = BB_EMPTY
        self.occupied_co[BLACK] = BB_EMPTY
        self.occupied = BB_EMPTY

    def clear_board(self) -> None:
        """
        Clears the board.

        :class:`~chess.Board` also clears the move stack.
        """
        self._clear_board()

    def piece_count(self) -> int:
        """
        Gets the number of pieces on the board.

        Does not include Crazyhouse pockets.
        """
        return popcount(self.occupied)

    def pieces_mask(self, piece_type: PieceType, color: Color) -> Bitboard:
        if piece_type == PAWN:
            bb = self.pawns
        elif piece_type == KNIGHT:
            bb = self.knights
        elif piece_type == BISHOP:
            bb = self.bishops
        elif piece_type == ROOK:
            bb = self.rooks
        elif piece_type == QUEEN:
            bb = self.queens
        elif piece_type == KING:
            bb = self.kings
        else:
            assert False, f"expected PieceType, got {piece_type!r}"

        return bb & self.occupied_co[color]

    def pieces(self, piece_type: PieceType, color: Color) -> SquareSet:
        """
        Gets pieces of the given type and color.

        Returns a :class:`set of squares <chess.SquareSet>`.
        """
        return SquareSet(self.pieces_mask(piece_type, color))

    def piece_at(self, square: Square) -> Optional[Piece]:
        """Gets the :class:`piece <chess.Piece>` at the given square."""
        piece_type = self.piece_type_at(square)
        if piece_type:
            mask = BB_SQUARES[square]
            color = bool(self.occupied_co[WHITE] & mask)
            return Piece(piece_type, color)
        else:
            return None

    def piece_type_at(self, square: Square) -> Optional[PieceType]:
        """Gets the piece type at the given square."""
        mask = BB_SQUARES[square]

        if not self.occupied & mask:
            return None  # Early return
        elif self.pawns & mask:
            return PAWN
        elif self.knights & mask:
            return KNIGHT
        elif self.bishops & mask:
            return BISHOP
        elif self.rooks & mask:
            return ROOK
        elif self.queens & mask:
            return QUEEN
        else:
            return KING

    def color_at(self, square: Square) -> Optional[Color]:
        """Gets the color of the piece at the given square."""
        mask = BB_SQUARES[square]
        if self.occupied_co[WHITE] & mask:
            return WHITE
        elif self.occupied_co[BLACK] & mask:
            return BLACK
        else:
            return None

    def _effective_promoted(self) -> Bitboard:
        return BB_EMPTY

    def king(self, color: Color) -> Optional[Square]:
        """
        Finds the unique king square of the given side. Returns ``None`` if
        there is no king or multiple kings of that color.

        In variants with king promotions, only non-promoted kings are
        considered.
        """
        king_mask = self.occupied_co[color] & self.kings & ~self._effective_promoted()
        return msb(king_mask) if king_mask and not king_mask & (king_mask - 1) else None

    def attacks_mask(self, square: Square) -> Bitboard:
        bb_square = BB_SQUARES[square]

        if bb_square & self.pawns:
            color = bool(bb_square & self.occupied_co[WHITE])
            return BB_PAWN_ATTACKS[color][square]
        elif bb_square & self.knights:
            return BB_KNIGHT_ATTACKS[square]
        elif bb_square & self.kings:
            return BB_KING_ATTACKS[square]
        else:
            attacks = 0
            if bb_square & self.bishops or bb_square & self.queens:
                attacks = BB_DIAG_ATTACKS[square][BB_DIAG_MASKS[square] & self.occupied]
            if bb_square & self.rooks or bb_square & self.queens:
                attacks |= (BB_RANK_ATTACKS[square][BB_RANK_MASKS[square] & self.occupied] |
                            BB_FILE_ATTACKS[square][BB_FILE_MASKS[square] & self.occupied])
            return attacks

    def attacks(self, square: Square) -> SquareSet:
        """
        Gets the set of attacked squares from the given square.

        There will be no attacks if the square is empty. Pinned pieces are
        still attacking other squares.

        Returns a :class:`set of squares <chess.SquareSet>`.
        """
        return SquareSet(self.attacks_mask(square))

    def attackers_mask(self, color: Color, square: Square, occupied: Optional[Bitboard] = None) -> Bitboard:
        occupied = self.occupied if occupied is None else occupied

        rank_pieces = BB_RANK_MASKS[square] & occupied
        file_pieces = BB_FILE_MASKS[square] & occupied
        diag_pieces = BB_DIAG_MASKS[square] & occupied

        queens_and_rooks = self.queens | self.rooks
        queens_and_bishops = self.queens | self.bishops

        attackers = (
            (BB_KING_ATTACKS[square] & self.kings) |
            (BB_KNIGHT_ATTACKS[square] & self.knights) |
            (BB_RANK_ATTACKS[square][rank_pieces] & queens_and_rooks) |
            (BB_FILE_ATTACKS[square][file_pieces] & queens_and_rooks) |
            (BB_DIAG_ATTACKS[square][diag_pieces] & queens_and_bishops) |
            (BB_PAWN_ATTACKS[not color][square] & self.pawns))

        return attackers & self.occupied_co[color]

    def is_attacked_by(self, color: Color, square: Square, occupied: Optional[IntoSquareSet] = None) -> bool:
        """
        Checks if the given side attacks the given square.

        Pinned pieces still count as attackers. Pawns that can be captured
        en passant are **not** considered attacked.

        *occupied* determines which squares are considered to block attacks.
        For example,
        ``board.occupied ^ board.pieces_mask(chess.KING, board.turn)`` can be
        used to consider X-ray attacks through the king.
        Defaults to ``board.occupied`` (all pieces including the king,
        no X-ray attacks).
        """
        return bool(self.attackers_mask(color, square, None if occupied is None else SquareSet(occupied).mask))

    def attackers(self, color: Color, square: Square, occupied: Optional[IntoSquareSet] = None) -> SquareSet:
        """
        Gets the set of attackers of the given color for the given square.

        Pinned pieces still count as attackers.

        *occupied* determines which squares are considered to block attacks.
        For example,
        ``board.occupied ^ board.pieces_mask(chess.KING, board.turn)`` can be
        used to consider X-ray attacks through the king.
        Defaults to ``board.occupied`` (all pieces including the king,
        no X-ray attacks).

        Returns a :class:`set of squares <chess.SquareSet>`.
        """
        return SquareSet(self.attackers_mask(color, square, None if occupied is None else SquareSet(occupied).mask))

    def pin_mask(self, color: Color, square: Square) -> Bitboard:
        king = self.king(color)
        if king is None:
            return BB_ALL

        square_mask = BB_SQUARES[square]

        for attacks, sliders in [(BB_FILE_ATTACKS, self.rooks | self.queens),
                                 (BB_RANK_ATTACKS, self.rooks | self.queens),
                                 (BB_DIAG_ATTACKS, self.bishops | self.queens)]:
            rays = attacks[king][0]
            if rays & square_mask:
                snipers = rays & sliders & self.occupied_co[not color]
                for sniper in scan_reversed(snipers):
                    if between(sniper, king) & (self.occupied | square_mask) == square_mask:
                        return ray(king, sniper)

                break

        return BB_ALL

    def pin(self, color: Color, square: Square) -> SquareSet:
        """
        Detects an absolute pin (and its direction) of the given square to
        the king of the given color.

        >>> import chess
        >>>
        >>> board = chess.Board("rnb1k2r/ppp2ppp/5n2/3q4/1b1P4/2N5/PP3PPP/R1BQKBNR w KQkq - 3 7")
        >>> board.is_pinned(chess.WHITE, chess.C3)
        True
        >>> direction = board.pin(chess.WHITE, chess.C3)
        >>> direction
        SquareSet(0x0000_0001_0204_0810)
        >>> print(direction)
        . . . . . . . .
        . . . . . . . .
        . . . . . . . .
        1 . . . . . . .
        . 1 . . . . . .
        . . 1 . . . . .
        . . . 1 . . . .
        . . . . 1 . . .

        Returns a :class:`set of squares <chess.SquareSet>` that mask the rank,
        file or diagonal of the pin. If there is no pin, then a mask of the
        entire board is returned.
        """
        return SquareSet(self.pin_mask(color, square))

    def is_pinned(self, color: Color, square: Square) -> bool:
        """
        Detects if the given square is pinned to the king of the given color.
        """
        return self.pin_mask(color, square) != BB_ALL

    def _remove_piece_at(self, square: Square) -> Optional[PieceType]:
        piece_type = self.piece_type_at(square)
        mask = BB_SQUARES[square]

        if piece_type == PAWN:
            self.pawns ^= mask
        elif piece_type == KNIGHT:
            self.knights ^= mask
        elif piece_type == BISHOP:
            self.bishops ^= mask
        elif piece_type == ROOK:
            self.rooks ^= mask
        elif piece_type == QUEEN:
            self.queens ^= mask
        elif piece_type == KING:
            self.kings ^= mask
        else:
            return None

        self.occupied ^= mask
        self.occupied_co[WHITE] &= ~mask
        self.occupied_co[BLACK] &= ~mask

        self.promoted &= ~mask

        return piece_type

    def remove_piece_at(self, square: Square) -> Optional[Piece]:
        """
        Removes the piece from the given square. Returns the
        :class:`~chess.Piece` or ``None`` if the square was already empty.

        :class:`~chess.Board` also clears the move stack.
        """
        color = bool(self.occupied_co[WHITE] & BB_SQUARES[square])
        piece_type = self._remove_piece_at(square)
        return Piece(piece_type, color) if piece_type else None

    def _set_piece_at(self, square: Square, piece_type: PieceType, color: Color, promoted: bool = False) -> None:
        self._remove_piece_at(square)

        mask = BB_SQUARES[square]

        if piece_type == PAWN:
            self.pawns |= mask
        elif piece_type == KNIGHT:
            self.knights |= mask
        elif piece_type == BISHOP:
            self.bishops |= mask
        elif piece_type == ROOK:
            self.rooks |= mask
        elif piece_type == QUEEN:
            self.queens |= mask
        elif piece_type == KING:
            self.kings |= mask
        else:
            return

        self.occupied ^= mask
        self.occupied_co[color] ^= mask

        if promoted:
            self.promoted ^= mask

    def set_piece_at(self, square: Square, piece: Optional[Piece], promoted: bool = False) -> None:
        """
        Sets a piece at the given square.

        An existing piece is replaced. Setting *piece* to ``None`` is
        equivalent to :func:`~chess.Board.remove_piece_at()`.

        :class:`~chess.Board` also clears the move stack.
        """
        if piece is None:
            self._remove_piece_at(square)
        else:
            self._set_piece_at(square, piece.piece_type, piece.color, promoted)

    def board_fen(self, *, promoted: Optional[bool] = None) -> str:
        """
        Gets the board FEN (e.g.,
        ``rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR``).
        """
        builder: List[str] = []
        empty = 0

        for square in SQUARES_180:
            piece = self.piece_at(square)

            if not piece:
                empty += 1
            else:
                if empty:
                    builder.append(str(empty))
                    empty = 0
                builder.append(piece.symbol())

                if promoted is None:
                    promoted_mask = self._effective_promoted()
                elif promoted:
                    promoted_mask = self.promoted
                else:
                    promoted_mask = BB_EMPTY
                if BB_SQUARES[square] & promoted_mask:
                    builder.append("~")

            if BB_SQUARES[square] & BB_FILE_H:
                if empty:
                    builder.append(str(empty))
                    empty = 0

                if square != H1:
                    builder.append("/")

        return "".join(builder)

    def _set_board_fen(self, fen: str) -> None:
        # Compatibility with set_fen().
        fen = fen.strip()
        if " " in fen:
            raise ValueError(f"expected position part of fen, got multiple parts: {fen!r}")

        # Ensure the FEN is valid.
        rows = fen.split("/")
        if len(rows) != 8:
            raise ValueError(f"expected 8 rows in position part of fen: {fen!r}")

        # Validate each row.
        for row in rows:
            field_sum = 0
            previous_was_digit = False
            previous_was_piece = False

            for c in row:
                if c in ["1", "2", "3", "4", "5", "6", "7", "8"]:
                    if previous_was_digit:
                        raise ValueError(f"two subsequent digits in position part of fen: {fen!r}")
                    field_sum += int(c)
                    previous_was_digit = True
                    previous_was_piece = False
                elif c == "~":
                    if not previous_was_piece:
                        raise ValueError(f"'~' not after piece in position part of fen: {fen!r}")
                    previous_was_digit = False
                    previous_was_piece = False
                elif c.lower() in PIECE_SYMBOLS:
                    field_sum += 1
                    previous_was_digit = False
                    previous_was_piece = True
                else:
                    raise ValueError(f"invalid character in position part of fen: {fen!r}")

            if field_sum != 8:
                raise ValueError(f"expected 8 columns per row in position part of fen: {fen!r}")

        # Clear the board.
        self._clear_board()

        # Put pieces on the board.
        square_index = 0
        for c in fen:
            if c in ["1", "2", "3", "4", "5", "6", "7", "8"]:
                square_index += int(c)
            elif c.lower() in PIECE_SYMBOLS:
                piece = Piece.from_symbol(c)
                self._set_piece_at(SQUARES_180[square_index], piece.piece_type, piece.color)
                square_index += 1
            elif c == "~":
                self.promoted |= BB_SQUARES[SQUARES_180[square_index - 1]]

    def set_board_fen(self, fen: str) -> None:
        """
        Parses *fen* and sets up the board, where *fen* is the board part of
        a FEN.

        :class:`~chess.Board` also clears the move stack.

        :raises: :exc:`ValueError` if syntactically invalid.
        """
        self._set_board_fen(fen)

    def piece_map(self, *, mask: Bitboard = BB_ALL) -> Dict[Square, Piece]:
        """
        Gets a dictionary of :class:`pieces <chess.Piece>` by square index.
        """
        result: Dict[Square, Piece] = {}
        for square in scan_reversed(self.occupied & mask):
            result[square] = typing.cast(Piece, self.piece_at(square))
        return result

    def _set_piece_map(self, pieces: Mapping[Square, Piece]) -> None:
        self._clear_board()
        for square, piece in pieces.items():
            self._set_piece_at(square, piece.piece_type, piece.color)

    def set_piece_map(self, pieces: Mapping[Square, Piece]) -> None:
        """
        Sets up the board from a dictionary of :class:`pieces <chess.Piece>`
        by square index.

        :class:`~chess.Board` also clears the move stack.
        """
        self._set_piece_map(pieces)

    def _set_chess960_pos(self, scharnagl: int) -> None:
        if not 0 <= scharnagl <= 959:
            raise ValueError(f"chess960 position index not 0 <= {scharnagl!r} <= 959")

        # See http://www.russellcottrell.com/Chess/Chess960.htm for
        # a description of the algorithm.
        n, bw = divmod(scharnagl, 4)
        n, bb = divmod(n, 4)
        n, q = divmod(n, 6)

        n1 = 0
        n2 = 0
        for n1 in range(0, 4):
            n2 = n + (3 - n1) * (4 - n1) // 2 - 5
            if n1 < n2 and 1 <= n2 <= 4:
                break

        # Bishops.
        bw_file = bw * 2 + 1
        bb_file = bb * 2
        self.bishops = (BB_FILES[bw_file] | BB_FILES[bb_file]) & BB_BACKRANKS

        # Queens.
        q_file = q
        q_file += int(min(bw_file, bb_file) <= q_file)
        q_file += int(max(bw_file, bb_file) <= q_file)
        self.queens = BB_FILES[q_file] & BB_BACKRANKS

        used = [bw_file, bb_file, q_file]

        # Knights.
        self.knights = BB_EMPTY
        for i in range(0, 8):
            if i not in used:
                if n1 == 0 or n2 == 0:
                    self.knights |= BB_FILES[i] & BB_BACKRANKS
                    used.append(i)
                n1 -= 1
                n2 -= 1

        # RKR.
        for i in range(0, 8):
            if i not in used:
                self.rooks = BB_FILES[i] & BB_BACKRANKS
                used.append(i)
                break
        for i in range(1, 8):
            if i not in used:
                self.kings = BB_FILES[i] & BB_BACKRANKS
                used.append(i)
                break
        for i in range(2, 8):
            if i not in used:
                self.rooks |= BB_FILES[i] & BB_BACKRANKS
                break

        # Finalize.
        self.pawns = BB_RANK_2 | BB_RANK_7
        self.occupied_co[WHITE] = BB_RANK_1 | BB_RANK_2
        self.occupied_co[BLACK] = BB_RANK_7 | BB_RANK_8
        self.occupied = BB_RANK_1 | BB_RANK_2 | BB_RANK_7 | BB_RANK_8
        self.promoted = BB_EMPTY

    def set_chess960_pos(self, scharnagl: int) -> None:
        """
        Sets up a Chess960 starting position given its index between 0 and 959.
        Also see :func:`~chess.BaseBoard.from_chess960_pos()`.
        """
        self._set_chess960_pos(scharnagl)

    def chess960_pos(self) -> Optional[int]:
        """
        Gets the Chess960 starting position index between 0 and 959,
        or ``None``.
        """
        if self.occupied_co[WHITE] != BB_RANK_1 | BB_RANK_2:
            return None
        if self.occupied_co[BLACK] != BB_RANK_7 | BB_RANK_8:
            return None
        if self.pawns != BB_RANK_2 | BB_RANK_7:
            return None
        if self._effective_promoted():
            return None

        # Piece counts.
        brnqk = [self.bishops, self.rooks, self.knights, self.queens, self.kings]
        if [popcount(pieces) for pieces in brnqk] != [4, 4, 4, 2, 2]:
            return None

        # Symmetry.
        if any((BB_RANK_1 & pieces) << 56 != BB_RANK_8 & pieces for pieces in brnqk):
            return None

        # Algorithm from ChessX, src/database/bitboard.cpp, r2254.
        x = self.bishops & (2 + 8 + 32 + 128)
        if not x:
            return None
        bs1 = (lsb(x) - 1) // 2
        cc_pos = bs1
        x = self.bishops & (1 + 4 + 16 + 64)
        if not x:
            return None
        bs2 = lsb(x) * 2
        cc_pos += bs2

        q = 0
        qf = False
        n0 = 0
        n1 = 0
        n0f = False
        n1f = False
        rf = 0
        n0s = [0, 4, 7, 9]
        for square in range(A1, H1 + 1):
            bb = BB_SQUARES[square]
            if bb & self.queens:
                qf = True
            elif bb & self.rooks or bb & self.kings:
                if bb & self.kings:
                    if rf != 1:
                        return None
                else:
                    rf += 1

                if not qf:
                    q += 1

                if not n0f:
                    n0 += 1
                elif not n1f:
                    n1 += 1
            elif bb & self.knights:
                if not qf:
                    q += 1

                if not n0f:
                    n0f = True
                elif not n1f:
                    n1f = True

        if n0 < 4 and n1f and qf:
            cc_pos += q * 16
            krn = n0s[n0] + n1
            cc_pos += krn * 96
            return cc_pos
        else:
            return None

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.board_fen()!r})"

    def __str__(self) -> str:
        builder: List[str] = []

        for square in SQUARES_180:
            piece = self.piece_at(square)

            if piece:
                builder.append(piece.symbol())
            else:
                builder.append(".")

            if BB_SQUARES[square] & BB_FILE_H:
                if square != H1:
                    builder.append("\n")
            else:
                builder.append(" ")

        return "".join(builder)

    def unicode(self, *, invert_color: bool = False, borders: bool = False, empty_square: str = "⭘", orientation: Color = WHITE) -> str:
        """
        Returns a string representation of the board with Unicode pieces.
        Useful for pretty-printing to a terminal.

        :param invert_color: Invert color of the Unicode pieces.
        :param borders: Show borders and a coordinate margin.
        """
        builder: List[str] = []
        for rank_index in (range(7, -1, -1) if orientation else range(8)):
            if borders:
                builder.append("  ")
                builder.append("-" * 17)
                builder.append("\n")

                builder.append(RANK_NAMES[rank_index])
                builder.append(" ")

            for i, file_index in enumerate(range(8) if orientation else range(7, -1, -1)):
                square_index = square(file_index, rank_index)

                if borders:
                    builder.append("|")
                elif i > 0:
                    builder.append(" ")

                piece = self.piece_at(square_index)

                if piece:
                    builder.append(piece.unicode_symbol(invert_color=invert_color))
                else:
                    builder.append(empty_square)

            if borders:
                builder.append("|")

            if borders or (rank_index > 0 if orientation else rank_index < 7):
                builder.append("\n")

        if borders:
            builder.append("  ")
            builder.append("-" * 17)
            builder.append("\n")
            letters = "a b c d e f g h" if orientation else "h g f e d c b a"
            builder.append("   " + letters)

        return "".join(builder)

    def _repr_svg_(self) -> str:
        import chess.svg
        return chess.svg.board(board=self, size=400)

    def __eq__(self, board: object) -> bool:
        if isinstance(board, BaseBoard):
            return (
                self.occupied == board.occupied and
                self.occupied_co[WHITE] == board.occupied_co[WHITE] and
                self.pawns == board.pawns and
                self.knights == board.knights and
                self.bishops == board.bishops and
                self.rooks == board.rooks and
                self.queens == board.queens and
                self.kings == board.kings)
        else:
            return NotImplemented

    def apply_transform(self, f: Callable[[Bitboard], Bitboard]) -> None:
        self.pawns = f(self.pawns)
        self.knights = f(self.knights)
        self.bishops = f(self.bishops)
        self.rooks = f(self.rooks)
        self.queens = f(self.queens)
        self.kings = f(self.kings)

        self.occupied_co[WHITE] = f(self.occupied_co[WHITE])
        self.occupied_co[BLACK] = f(self.occupied_co[BLACK])
        self.occupied = f(self.occupied)
        self.promoted = f(self.promoted)

    def transform(self, f: Callable[[Bitboard], Bitboard]) -> Self:
        """
        Returns a transformed copy of the board (without move stack)
        by applying a bitboard transformation function.

        Available transformations include :func:`chess.flip_vertical()`,
        :func:`chess.flip_horizontal()`, :func:`chess.flip_diagonal()`,
        :func:`chess.flip_anti_diagonal()`, :func:`chess.shift_down()`,
        :func:`chess.shift_up()`, :func:`chess.shift_left()`, and
        :func:`chess.shift_right()`.

        Alternatively, :func:`~chess.BaseBoard.apply_transform()` can be used
        to apply the transformation on the board.
        """
        board = self.copy()
        board.apply_transform(f)
        return board

    def apply_mirror(self) -> None:
        self.apply_transform(flip_vertical)
        self.occupied_co[WHITE], self.occupied_co[BLACK] = self.occupied_co[BLACK], self.occupied_co[WHITE]

    def mirror(self) -> Self:
        """
        Returns a mirrored copy of the board (without move stack).

        The board is mirrored vertically and piece colors are swapped, so that
        the position is equivalent modulo color.

        Alternatively, :func:`~chess.BaseBoard.apply_mirror()` can be used
        to mirror the board.
        """
        board = self.copy()
        board.apply_mirror()
        return board

    def copy(self) -> Self:
        """Creates a copy of the board."""
        board = type(self)(None)

        board.pawns = self.pawns
        board.knights = self.knights
        board.bishops = self.bishops
        board.rooks = self.rooks
        board.queens = self.queens
        board.kings = self.kings

        board.occupied_co[WHITE] = self.occupied_co[WHITE]
        board.occupied_co[BLACK] = self.occupied_co[BLACK]
        board.occupied = self.occupied
        board.promoted = self.promoted

        return board

    def __copy__(self) -> Self:
        return self.copy()

    def __deepcopy__(self, memo: Dict[int, object]) -> Self:
        board = self.copy()
        memo[id(self)] = board
        return board

    @classmethod
    def empty(cls: Type[BaseBoardT]) -> BaseBoardT:
        """
        Creates a new empty board. Also see
        :func:`~chess.BaseBoard.clear_board()`.
        """
        return cls(None)

    @classmethod
    def from_chess960_pos(cls: Type[BaseBoardT], scharnagl: int) -> BaseBoardT:
        """
        Creates a new board, initialized with a Chess960 starting position.

        >>> import chess
        >>> import random
        >>>
        >>> board = chess.Board.from_chess960_pos(random.randint(0, 959))
        """
        board = cls.empty()
        board.set_chess960_pos(scharnagl)
        return board


