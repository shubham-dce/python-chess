from __future__ import annotations
from .constants import *
from .types import *
from typing import Callable, ClassVar, Counter, Dict, Hashable, Iterable, Iterator, List, Mapping, Optional, Self, Tuple, Type, TypeVar, Union
from .baseboard import *
from .move import *
from .game_state import *
from .errors import *


import collections
import itertools
import copy

BoardT = TypeVar("BoardT", bound="Board")

class _BoardState:

    def __init__(self, board: Board) -> None:
        self.pawns = board.pawns
        self.knights = board.knights
        self.bishops = board.bishops
        self.rooks = board.rooks
        self.queens = board.queens
        self.kings = board.kings

        self.occupied_w = board.occupied_co[WHITE]
        self.occupied_b = board.occupied_co[BLACK]
        self.occupied = board.occupied

        self.promoted = board.promoted

        self.turn = board.turn
        self.castling_rights = board.castling_rights
        self.ep_square = board.ep_square
        self.halfmove_clock = board.halfmove_clock
        self.fullmove_number = board.fullmove_number

    def restore(self, board: Board) -> None:
        board.pawns = self.pawns
        board.knights = self.knights
        board.bishops = self.bishops
        board.rooks = self.rooks
        board.queens = self.queens
        board.kings = self.kings

        board.occupied_co[WHITE] = self.occupied_w
        board.occupied_co[BLACK] = self.occupied_b
        board.occupied = self.occupied

        board.promoted = self.promoted

        board.turn = self.turn
        board.castling_rights = self.castling_rights
        board.ep_square = self.ep_square
        board.halfmove_clock = self.halfmove_clock
        board.fullmove_number = self.fullmove_number

class Board(BaseBoard):
    """
    A :class:`~chess.BaseBoard`, additional information representing
    a chess position, and a :data:`move stack <chess.Board.move_stack>`.

    Provides :data:`move generation <chess.Board.legal_moves>`, validation,
    :func:`parsing <chess.Board.parse_san()>`, attack generation,
    :func:`game end detection <chess.Board.is_game_over()>`,
    and the capability to :func:`make <chess.Board.push()>` and
    :func:`unmake <chess.Board.pop()>` moves.

    The board is initialized to the standard chess starting position,
    unless otherwise specified in the optional *fen* argument.
    If *fen* is ``None``, an empty board is created.

    Optionally supports *chess960*. In Chess960, castling moves are encoded
    by a king move to the corresponding rook square.
    Use :func:`chess.Board.from_chess960_pos()` to create a board with one
    of the Chess960 starting positions.

    It's safe to set :data:`~Board.turn`, :data:`~Board.castling_rights`,
    :data:`~Board.ep_square`, :data:`~Board.halfmove_clock` and
    :data:`~Board.fullmove_number` directly.

    .. warning::
        It is possible to set up and work with invalid positions. In this
        case, :class:`~chess.Board` implements a kind of "pseudo-chess"
        (useful to gracefully handle errors or to implement chess variants).
        Use :func:`~chess.Board.is_valid()` to detect invalid positions.
    """

    aliases: ClassVar[List[str]] = ["Standard", "Chess", "Classical", "Normal", "Illegal", "From Position"]
    uci_variant: ClassVar[Optional[str]] = "chess"
    xboard_variant: ClassVar[Optional[str]] = "normal"
    starting_fen: ClassVar[str] = STARTING_FEN

    tbw_suffix: ClassVar[Optional[str]] = ".rtbw"
    tbz_suffix: ClassVar[Optional[str]] = ".rtbz"
    tbw_magic: ClassVar[Optional[bytes]] = b"\x71\xe8\x23\x5d"
    tbz_magic: ClassVar[Optional[bytes]] = b"\xd7\x66\x0c\xa5"
    pawnless_tbw_suffix: ClassVar[Optional[str]] = None
    pawnless_tbz_suffix: ClassVar[Optional[str]] = None
    pawnless_tbw_magic: ClassVar[Optional[bytes]] = None
    pawnless_tbz_magic: ClassVar[Optional[bytes]] = None
    connected_kings: ClassVar[bool] = False
    one_king: ClassVar[bool] = True
    captures_compulsory: ClassVar[bool] = False

    turn: Color
    """The side to move (``chess.WHITE`` or ``chess.BLACK``)."""

    castling_rights: Bitboard
    """
    Bitmask of the rooks with castling rights.

    To test for specific squares:

    >>> import chess
    >>>
    >>> board = chess.Board()
    >>> bool(board.castling_rights & chess.BB_H1)  # White can castle with the h1 rook
    True

    To add a specific square:

    >>> board.castling_rights |= chess.BB_A1

    Use :func:`~chess.Board.set_castling_fen()` to set multiple castling
    rights. Also see :func:`~chess.Board.has_castling_rights()`,
    :func:`~chess.Board.has_kingside_castling_rights()`,
    :func:`~chess.Board.has_queenside_castling_rights()`,
    :func:`~chess.Board.has_chess960_castling_rights()`,
    :func:`~chess.Board.clean_castling_rights()`.
    """

    ep_square: Optional[Square]
    """
    The potential en passant square on the third or sixth rank or ``None``.

    Use :func:`~chess.Board.has_legal_en_passant()` to test if en passant
    capturing would actually be possible on the next move.
    """

    fullmove_number: int
    """
    Counts move pairs. Starts at `1` and is incremented after every move
    of the black side.
    """

    halfmove_clock: int
    """The number of half-moves since the last capture or pawn move."""

    promoted: Bitboard
    """A bitmask of pieces that have been promoted."""

    chess960: bool
    """
    Whether the board is in Chess960 mode. In Chess960 castling moves are
    represented as king moves to the corresponding rook square.
    """

    move_stack: List[Move]
    """
    The move stack. Use :func:`Board.push() <chess.Board.push()>`,
    :func:`Board.pop() <chess.Board.pop()>`,
    :func:`Board.peek() <chess.Board.peek()>` and
    :func:`Board.clear_stack() <chess.Board.clear_stack()>` for
    manipulation.
    """

    def __init__(self, fen: Optional[str] = STARTING_FEN, *, chess960: bool = False) -> None:
        BaseBoard.__init__(self, None)

        self.chess960 = chess960

        self.ep_square = None
        self.move_stack = []
        self._stack: List[_BoardState] = []

        if fen is None:
            self.clear()
        elif fen == type(self).starting_fen:
            self.reset()
        else:
            self.set_fen(fen)

    @property
    def legal_moves(self) -> LegalMoveGenerator:
        """
        A dynamic list of legal moves.

        >>> import chess
        >>>
        >>> board = chess.Board()
        >>> board.legal_moves.count()
        20
        >>> bool(board.legal_moves)
        True
        >>> move = chess.Move.from_uci("g1f3")
        >>> move in board.legal_moves
        True

        Wraps :func:`~chess.Board.generate_legal_moves()` and
        :func:`~chess.Board.is_legal()`.
        """
        return LegalMoveGenerator(self)

    @property
    def pseudo_legal_moves(self) -> PseudoLegalMoveGenerator:
        """
        A dynamic list of pseudo-legal moves, much like the legal move list.

        Pseudo-legal moves might leave or put the king in check, but are
        otherwise valid. Null moves are not pseudo-legal. Castling moves are
        only included if they are completely legal.

        Wraps :func:`~chess.Board.generate_pseudo_legal_moves()` and
        :func:`~chess.Board.is_pseudo_legal()`.
        """
        return PseudoLegalMoveGenerator(self)

    def reset(self) -> None:
        """Restores the starting position."""
        self.turn = WHITE
        self.castling_rights = BB_CORNERS
        self.ep_square = None
        self.halfmove_clock = 0
        self.fullmove_number = 1

        self.reset_board()

    def reset_board(self) -> None:
        super().reset_board()
        self.clear_stack()

    def clear(self) -> None:
        """
        Clears the board.

        Resets move stack and move counters. The side to move is white. There
        are no rooks or kings, so castling rights are removed.

        In order to be in a valid :func:`~chess.Board.status()`, at least kings
        need to be put on the board.
        """
        self.turn = WHITE
        self.castling_rights = BB_EMPTY
        self.ep_square = None
        self.halfmove_clock = 0
        self.fullmove_number = 1

        self.clear_board()

    def clear_board(self) -> None:
        super().clear_board()
        self.clear_stack()

    def clear_stack(self) -> None:
        """Clears the move stack."""
        self.move_stack.clear()
        self._stack.clear()

    def root(self) -> Self:
        """Returns a copy of the root position."""
        if self._stack:
            board = type(self)(None, chess960=self.chess960)
            self._stack[0].restore(board)
            return board
        else:
            return self.copy(stack=False)

    def ply(self) -> int:
        """
        Returns the number of half-moves since the start of the game, as
        indicated by :data:`~chess.Board.fullmove_number` and
        :data:`~chess.Board.turn`.

        If moves have been pushed from the beginning, this is usually equal to
        ``len(board.move_stack)``. But note that a board can be set up with
        arbitrary starting positions, and the stack can be cleared.
        """
        return 2 * (self.fullmove_number - 1) + (self.turn == BLACK)

    def remove_piece_at(self, square: Square) -> Optional[Piece]:
        """Remove a piece, if any, from the given square and return the removed piece."""
        piece = super().remove_piece_at(square)
        self.clear_stack()
        return piece

    def set_piece_at(self, square: Square, piece: Optional[Piece], promoted: bool = False) -> None:
        """Place a piece on a square."""
        super().set_piece_at(square, piece, promoted=promoted)
        self.clear_stack()

    def generate_pseudo_legal_moves(self, from_mask: Bitboard = BB_ALL, to_mask: Bitboard = BB_ALL) -> Iterator[Move]:
        our_pieces = self.occupied_co[self.turn]

        # Generate piece moves.
        non_pawns = our_pieces & ~self.pawns & from_mask
        for from_square in scan_reversed(non_pawns):
            moves = self.attacks_mask(from_square) & ~our_pieces & to_mask
            for to_square in scan_reversed(moves):
                yield Move(from_square, to_square)

        # Generate castling moves.
        if from_mask & self.kings:
            yield from self.generate_castling_moves(from_mask, to_mask)

        # The remaining moves are all pawn moves.
        pawns = self.pawns & self.occupied_co[self.turn] & from_mask
        if not pawns:
            return

        # Generate pawn captures.
        capturers = pawns
        for from_square in scan_reversed(capturers):
            targets = (
                BB_PAWN_ATTACKS[self.turn][from_square] &
                self.occupied_co[not self.turn] & to_mask)

            for to_square in scan_reversed(targets):
                if square_rank(to_square) in [RANK_1, RANK_8]:
                    yield Move(from_square, to_square, QUEEN)
                    yield Move(from_square, to_square, ROOK)
                    yield Move(from_square, to_square, BISHOP)
                    yield Move(from_square, to_square, KNIGHT)
                else:
                    yield Move(from_square, to_square)

        # Prepare pawn advance generation.
        if self.turn == WHITE:
            single_moves = pawns << 8 & ~self.occupied
            double_moves = single_moves << 8 & ~self.occupied & (BB_RANK_3 | BB_RANK_4)
        else:
            single_moves = pawns >> 8 & ~self.occupied
            double_moves = single_moves >> 8 & ~self.occupied & (BB_RANK_6 | BB_RANK_5)

        single_moves &= to_mask
        double_moves &= to_mask

        # Generate single pawn moves.
        for to_square in scan_reversed(single_moves):
            from_square = to_square + (8 if self.turn == BLACK else -8)

            if square_rank(to_square) in [RANK_1, RANK_8]:
                yield Move(from_square, to_square, QUEEN)
                yield Move(from_square, to_square, ROOK)
                yield Move(from_square, to_square, BISHOP)
                yield Move(from_square, to_square, KNIGHT)
            else:
                yield Move(from_square, to_square)

        # Generate double pawn moves.
        for to_square in scan_reversed(double_moves):
            from_square = to_square + (16 if self.turn == BLACK else -16)
            yield Move(from_square, to_square)

        # Generate en passant captures.
        if self.ep_square:
            yield from self.generate_pseudo_legal_ep(from_mask, to_mask)

    def generate_pseudo_legal_ep(self, from_mask: Bitboard = BB_ALL, to_mask: Bitboard = BB_ALL) -> Iterator[Move]:
        if not self.ep_square or not BB_SQUARES[self.ep_square] & to_mask:
            return

        if BB_SQUARES[self.ep_square] & self.occupied:
            return

        capturers = (
            self.pawns & self.occupied_co[self.turn] & from_mask &
            BB_PAWN_ATTACKS[not self.turn][self.ep_square] &
            BB_RANKS[RANK_5 if self.turn else RANK_4])

        for capturer in scan_reversed(capturers):
            yield Move(capturer, self.ep_square)

    def generate_pseudo_legal_captures(self, from_mask: Bitboard = BB_ALL, to_mask: Bitboard = BB_ALL) -> Iterator[Move]:
        return itertools.chain(
            self.generate_pseudo_legal_moves(from_mask, to_mask & self.occupied_co[not self.turn]),
            self.generate_pseudo_legal_ep(from_mask, to_mask))

    def checkers_mask(self) -> Bitboard:
        king = self.king(self.turn)
        return BB_EMPTY if king is None else self.attackers_mask(not self.turn, king)

    def checkers(self) -> SquareSet:
        """
        Gets the pieces currently giving check.

        Returns a :class:`set of squares <chess.SquareSet>`.
        """
        return SquareSet(self.checkers_mask())

    def is_check(self) -> bool:
        """Tests if the current side to move is in check."""
        return bool(self.checkers_mask())

    def gives_check(self, move: Move) -> bool:
        """
        Probes if the given move would put the opponent in check. The move
        must be at least pseudo-legal.
        """
        self.push(move)
        try:
            return self.is_check()
        finally:
            self.pop()

    def gives_checkmate(self, move: Move) -> bool:
        """
        Probes if the given move would put the opponent in checkmate. The move
        must be at least pseudo-legal.
        """
        self.push(move)
        try:
            return self.is_checkmate()
        finally:
            self.pop()

    def is_into_check(self, move: Move) -> bool:
        king = self.king(self.turn)
        if king is None:
            return False

        # If already in check, look if it is an evasion.
        checkers = self.attackers_mask(not self.turn, king)
        if checkers and move not in self._generate_evasions(king, checkers, BB_SQUARES[move.from_square], BB_SQUARES[move.to_square]):
            return True

        return not self._is_safe(king, self._slider_blockers(king), move)

    def was_into_check(self) -> bool:
        king = self.king(not self.turn)
        return king is not None and self.is_attacked_by(self.turn, king)

    def is_pseudo_legal(self, move: Move) -> bool:
        # Null moves are not pseudo-legal.
        if not move:
            return False

        # Drops are not pseudo-legal.
        if move.drop:
            return False

        # Source square must not be vacant.
        piece = self.piece_type_at(move.from_square)
        if not piece:
            return False

        # Get square masks.
        from_mask = BB_SQUARES[move.from_square]
        to_mask = BB_SQUARES[move.to_square]

        # Check turn.
        if not self.occupied_co[self.turn] & from_mask:
            return False

        # Only pawns can promote and only on the backrank.
        if move.promotion:
            if piece != PAWN:
                return False

            if self.turn == WHITE and square_rank(move.to_square) != RANK_8:
                return False
            elif self.turn == BLACK and square_rank(move.to_square) != RANK_1:
                return False

        # Handle castling.
        if piece == KING:
            move = self._from_chess960(self.chess960, move.from_square, move.to_square)
            if move in self.generate_castling_moves():
                return True

        # Destination square can not be occupied.
        if self.occupied_co[self.turn] & to_mask:
            return False

        # Handle pawn moves.
        if piece == PAWN:
            return move in self.generate_pseudo_legal_moves(from_mask, to_mask)

        # Handle all other pieces.
        return bool(self.attacks_mask(move.from_square) & to_mask)

    def is_legal(self, move: Move) -> bool:
        """Check if a move is legal in the current position."""
        return not self.is_variant_end() and self.is_pseudo_legal(move) and not self.is_into_check(move)

    def is_variant_end(self) -> bool:
        """
        Checks if the game is over due to a special variant end condition.

        Note, for example, that stalemate is not considered a variant-specific
        end condition (this method will return ``False``), yet it can have a
        special **result** in suicide chess (any of
        :func:`~chess.Board.is_variant_loss()`,
        :func:`~chess.Board.is_variant_win()`,
        :func:`~chess.Board.is_variant_draw()` might return ``True``).
        """
        return False

    def is_variant_loss(self) -> bool:
        """
        Checks if the current side to move lost due to a variant-specific
        condition.
        """
        return False

    def is_variant_win(self) -> bool:
        """
        Checks if the current side to move won due to a variant-specific
        condition.
        """
        return False

    def is_variant_draw(self) -> bool:
        """
        Checks if a variant-specific drawing condition is fulfilled.
        """
        return False

    def is_game_over(self, *, claim_draw: bool = False) -> bool:
        """
        Check if the game is over by any rule.

        The game is not considered to be over by the
        :func:`fifty-move rule <chess.Board.can_claim_fifty_moves()>` or
        :func:`threefold repetition <chess.Board.can_claim_threefold_repetition()>`,
        unless *claim_draw* is given. Note that checking the latter can be
        slow.
        """
        return self.outcome(claim_draw=claim_draw) is not None

    def result(self, *, claim_draw: bool = False) -> str:
        """
        Return the result of a game: 1-0, 0-1, 1/2-1/2, or *.

        The game is not considered to be over by the
        :func:`fifty-move rule <chess.Board.can_claim_fifty_moves()>` or
        :func:`threefold repetition <chess.Board.can_claim_threefold_repetition()>`,
        unless *claim_draw* is given. Note that checking the latter can be
        slow.
        """
        outcome = self.outcome(claim_draw=claim_draw)
        return outcome.result() if outcome else "*"

    def outcome(self, *, claim_draw: bool = False) -> Optional[Outcome]:
        """
        Checks if the game is over due to
        :func:`checkmate <chess.Board.is_checkmate()>`,
        :func:`stalemate <chess.Board.is_stalemate()>`,
        :func:`insufficient material <chess.Board.is_insufficient_material()>`,
        the :func:`seventyfive-move rule <chess.Board.is_seventyfive_moves()>`,
        :func:`fivefold repetition <chess.Board.is_fivefold_repetition()>`,
        or a :func:`variant end condition <chess.Board.is_variant_end()>`.
        Returns the :class:`chess.Outcome` if the game has ended, otherwise
        ``None``.

        Alternatively, use :func:`~chess.Board.is_game_over()` if you are not
        interested in who won the game and why.

        The game is not considered to be over by the
        :func:`fifty-move rule <chess.Board.can_claim_fifty_moves()>` or
        :func:`threefold repetition <chess.Board.can_claim_threefold_repetition()>`,
        unless *claim_draw* is given. Note that checking the latter can be
        slow.
        """
        # Variant support.
        if self.is_variant_loss():
            return Outcome(Termination.VARIANT_LOSS, not self.turn)
        if self.is_variant_win():
            return Outcome(Termination.VARIANT_WIN, self.turn)
        if self.is_variant_draw():
            return Outcome(Termination.VARIANT_DRAW, None)

        # Normal game end.
        if self.is_checkmate():
            return Outcome(Termination.CHECKMATE, not self.turn)
        if self.is_insufficient_material():
            return Outcome(Termination.INSUFFICIENT_MATERIAL, None)
        if not any(self.generate_legal_moves()):
            return Outcome(Termination.STALEMATE, None)

        # Automatic draws.
        if self.is_seventyfive_moves():
            return Outcome(Termination.SEVENTYFIVE_MOVES, None)
        if self.is_fivefold_repetition():
            return Outcome(Termination.FIVEFOLD_REPETITION, None)

        # Claimable draws.
        if claim_draw:
            if self.can_claim_fifty_moves():
                return Outcome(Termination.FIFTY_MOVES, None)
            if self.can_claim_threefold_repetition():
                return Outcome(Termination.THREEFOLD_REPETITION, None)

        return None

    def is_checkmate(self) -> bool:
        """Checks if the current position is a checkmate."""
        if not self.is_check():
            return False

        return not any(self.generate_legal_moves())

    def is_stalemate(self) -> bool:
        """Checks if the current position is a stalemate."""
        if self.is_check():
            return False

        if self.is_variant_end():
            return False

        return not any(self.generate_legal_moves())

    def is_insufficient_material(self) -> bool:
        """
        Checks if neither side has sufficient winning material
        (:func:`~chess.Board.has_insufficient_material()`).
        """
        return all(self.has_insufficient_material(color) for color in COLORS)

    def has_insufficient_material(self, color: Color) -> bool:
        """
        Checks if *color* has insufficient winning material.

        This is guaranteed to return ``False`` if *color* can still win the
        game.

        The converse does not necessarily hold:
        The implementation only looks at the material, including the colors
        of bishops, but not considering piece positions. So fortress
        positions or positions with forced lines may return ``False``, even
        though there is no possible winning line.
        """
        if self.occupied_co[color] & (self.pawns | self.rooks | self.queens):
            return False

        # Knights are only insufficient material if:
        # (1) We do not have any other pieces, including more than one knight.
        # (2) The opponent does not have pawns, knights, bishops or rooks.
        #     These would allow selfmate.
        if self.occupied_co[color] & self.knights:
            return (popcount(self.occupied_co[color]) <= 2 and
                    not (self.occupied_co[not color] & ~self.kings & ~self.queens))

        # Bishops are only insufficient material if:
        # (1) We do not have any other pieces, including bishops of the
        #     opposite color.
        # (2) The opponent does not have bishops of the opposite color,
        #     pawns or knights. These would allow selfmate.
        if self.occupied_co[color] & self.bishops:
            same_color = (not self.bishops & BB_DARK_SQUARES) or (not self.bishops & BB_LIGHT_SQUARES)
            return same_color and not self.pawns and not self.knights

        return True

    def _is_halfmoves(self, n: int) -> bool:
        return self.halfmove_clock >= n and any(self.generate_legal_moves())

    def is_seventyfive_moves(self) -> bool:
        """
        Since the 1st of July 2014, a game is automatically drawn (without
        a claim by one of the players) if the half-move clock since a capture
        or pawn move is equal to or greater than 150. Other means to end a game
        take precedence.
        """
        return self._is_halfmoves(150)

    def is_fivefold_repetition(self) -> bool:
        """
        Since the 1st of July 2014 a game is automatically drawn (without
        a claim by one of the players) if a position occurs for the fifth time.
        Originally this had to occur on consecutive alternating moves, but
        this has since been revised.
        """
        return self.is_repetition(5)

    def can_claim_draw(self) -> bool:
        """
        Checks if the player to move can claim a draw by the fifty-move rule or
        by threefold repetition.

        Note that checking the latter can be slow.
        """
        return self.can_claim_fifty_moves() or self.can_claim_threefold_repetition()

    def is_fifty_moves(self) -> bool:
        """
        Checks that the clock of halfmoves since the last capture or pawn move
        is greater or equal to 100, and that no other means of ending the game
        (like checkmate) take precedence.
        """
        return self._is_halfmoves(100)

    def can_claim_fifty_moves(self) -> bool:
        """
        Checks if the player to move can claim a draw by the fifty-move rule.

        In addition to :func:`~chess.Board.is_fifty_moves()`, the fifty-move
        rule can also be claimed if there is a legal move that achieves this
        condition.
        """
        if self.is_fifty_moves():
            return True

        if self.halfmove_clock >= 99:
            for move in self.generate_legal_moves():
                if not self.is_zeroing(move):
                    self.push(move)
                    try:
                        if self.is_fifty_moves():
                            return True
                    finally:
                        self.pop()

        return False

    def can_claim_threefold_repetition(self) -> bool:
        """
        Checks if the player to move can claim a draw by threefold repetition.

        Draw by threefold repetition can be claimed if the position on the
        board occurred for the third time or if such a repetition is reached
        with one of the possible legal moves.

        Note that checking this can be slow: In the worst case
        scenario, every legal move has to be tested and the entire game has to
        be replayed because there is no incremental transposition table.
        """
        transposition_key = self._transposition_key()
        transpositions: Counter[Hashable] = collections.Counter()
        transpositions.update((transposition_key, ))

        # Count positions.
        switchyard: List[Move] = []
        while self.move_stack:
            move = self.pop()
            switchyard.append(move)

            if self.is_irreversible(move):
                break

            transpositions.update((self._transposition_key(), ))

        while switchyard:
            self.push(switchyard.pop())

        # Threefold repetition occurred.
        if transpositions[transposition_key] >= 3:
            return True

        # The next legal move is a threefold repetition.
        for move in self.generate_legal_moves():
            self.push(move)
            try:
                if transpositions[self._transposition_key()] >= 2:
                    return True
            finally:
                self.pop()

        return False

    def is_repetition(self, count: int = 3) -> bool:
        """
        Checks if the current position has repeated 3 (or a given number of)
        times.

        Unlike :func:`~chess.Board.can_claim_threefold_repetition()`,
        this does not consider a repetition that can be played on the next
        move.

        Note that checking this can be slow: In the worst case, the entire
        game has to be replayed because there is no incremental transposition
        table.
        """
        # Fast check, based on occupancy only.
        maybe_repetitions = 1
        for state in reversed(self._stack):
            if state.occupied == self.occupied:
                maybe_repetitions += 1
                if maybe_repetitions >= count:
                    break
        if maybe_repetitions < count:
            return False

        # Check full replay.
        transposition_key = self._transposition_key()
        switchyard: List[Move] = []

        try:
            while True:
                if count <= 1:
                    return True

                if len(self.move_stack) < count - 1:
                    break

                move = self.pop()
                switchyard.append(move)

                if self.is_irreversible(move):
                    break

                if self._transposition_key() == transposition_key:
                    count -= 1
        finally:
            while switchyard:
                self.push(switchyard.pop())

        return False

    def _push_capture(self, move: Move, capture_square: Square, piece_type: PieceType, was_promoted: bool) -> None:
        pass

    def push(self, move: Move) -> None:
        """
        Updates the position with the given *move* and puts it onto the
        move stack.

        >>> import chess
        >>>
        >>> board = chess.Board()
        >>>
        >>> Nf3 = chess.Move.from_uci("g1f3")
        >>> board.push(Nf3)  # Make the move

        >>> board.pop()  # Unmake the last move
        Move.from_uci('g1f3')

        Null moves just increment the move counters, switch turns and forfeit
        en passant capturing.

        .. warning::
            Moves are not checked for legality. It is the caller's
            responsibility to ensure that the move is at least pseudo-legal or
            a null move.
        """
        # Push move and remember board state.
        move = self._to_chess960(move)
        board_state = _BoardState(self)
        self.castling_rights = self.clean_castling_rights()  # Before pushing stack
        self.move_stack.append(self._from_chess960(self.chess960, move.from_square, move.to_square, move.promotion, move.drop))
        self._stack.append(board_state)

        # Reset en passant square.
        ep_square = self.ep_square
        self.ep_square = None

        # Increment move counters.
        self.halfmove_clock += 1
        if self.turn == BLACK:
            self.fullmove_number += 1

        # On a null move, simply swap turns and reset the en passant square.
        if not move:
            self.turn = not self.turn
            return

        # Drops.
        if move.drop:
            self._set_piece_at(move.to_square, move.drop, self.turn)
            self.turn = not self.turn
            return

        # Zero the half-move clock.
        if self.is_zeroing(move):
            self.halfmove_clock = 0

        from_bb = BB_SQUARES[move.from_square]
        to_bb = BB_SQUARES[move.to_square]

        promoted = bool(self.promoted & from_bb)
        piece_type = self._remove_piece_at(move.from_square)
        assert piece_type is not None, f"push() expects move to be pseudo-legal, but got {move} in {self.board_fen()}"
        capture_square = move.to_square
        captured_piece_type = self.piece_type_at(capture_square)

        # Update castling rights.
        self.castling_rights &= ~to_bb & ~from_bb
        if piece_type == KING and not self._effective_promoted() & from_bb:
            if self.turn == WHITE:
                self.castling_rights &= ~BB_RANK_1
            else:
                self.castling_rights &= ~BB_RANK_8
        elif captured_piece_type == KING and not self._effective_promoted() & to_bb:
            if self.turn == WHITE and square_rank(move.to_square) == RANK_8:
                self.castling_rights &= ~BB_RANK_8
            elif self.turn == BLACK and square_rank(move.to_square) == RANK_1:
                self.castling_rights &= ~BB_RANK_1

        # Handle special pawn moves.
        if piece_type == PAWN:
            diff = move.to_square - move.from_square

            if diff == 16 and square_rank(move.from_square) == RANK_2:
                self.ep_square = move.from_square + 8
            elif diff == -16 and square_rank(move.from_square) == RANK_7:
                self.ep_square = move.from_square - 8
            elif move.to_square == ep_square and abs(diff) in [7, 9] and not captured_piece_type:
                # Remove pawns captured en passant.
                down = -8 if self.turn == WHITE else 8
                capture_square = move.to_square + down
                captured_piece_type = self._remove_piece_at(capture_square)

        # Promotion.
        if move.promotion:
            promoted = True
            piece_type = move.promotion

        # Castling.
        castling = piece_type == KING and self.occupied_co[self.turn] & to_bb
        if castling:
            a_side = square_file(move.to_square) < square_file(move.from_square)

            self._remove_piece_at(move.from_square)
            self._remove_piece_at(move.to_square)

            if a_side:
                self._set_piece_at(C1 if self.turn == WHITE else C8, KING, self.turn)
                self._set_piece_at(D1 if self.turn == WHITE else D8, ROOK, self.turn)
            else:
                self._set_piece_at(G1 if self.turn == WHITE else G8, KING, self.turn)
                self._set_piece_at(F1 if self.turn == WHITE else F8, ROOK, self.turn)

        # Put the piece on the target square.
        if not castling:
            was_promoted = bool(self.promoted & to_bb)
            self._set_piece_at(move.to_square, piece_type, self.turn, promoted)

            if captured_piece_type:
                self._push_capture(move, capture_square, captured_piece_type, was_promoted)

        # Swap turn.
        self.turn = not self.turn

    def pop(self) -> Move:
        """
        Restores the previous position and returns the last move from the stack.

        :raises: :exc:`IndexError` if the move stack is empty.
        """
        move = self.move_stack.pop()
        self._stack.pop().restore(self)
        return move

    def peek(self) -> Move:
        """
        Gets the last move from the move stack.

        :raises: :exc:`IndexError` if the move stack is empty.
        """
        return self.move_stack[-1]

    def find_move(self, from_square: Square, to_square: Square, promotion: Optional[PieceType] = None) -> Move:
        """
        Finds a matching legal move for an origin square, a target square, and
        an optional promotion piece type.

        For pawn moves to the backrank, the promotion piece type defaults to
        :data:`chess.QUEEN`, unless otherwise specified.

        Castling moves are normalized to king moves by two steps, except in
        Chess960.

        :raises: :exc:`IllegalMoveError` if no matching legal move is found.
        """
        if promotion is None and self.pawns & BB_SQUARES[from_square] and BB_SQUARES[to_square] & BB_BACKRANKS:
            promotion = QUEEN

        move = self._from_chess960(self.chess960, from_square, to_square, promotion)
        if not self.is_legal(move):
            raise IllegalMoveError(f"no matching legal move for {move.uci()} ({SQUARE_NAMES[from_square]} -> {SQUARE_NAMES[to_square]}) in {self.fen()}")

        return move

    def castling_shredder_fen(self) -> str:
        castling_rights = self.clean_castling_rights()
        if not castling_rights:
            return "-"

        builder: List[str] = []

        for square in scan_reversed(castling_rights & BB_RANK_1):
            builder.append(FILE_NAMES[square_file(square)].upper())

        for square in scan_reversed(castling_rights & BB_RANK_8):
            builder.append(FILE_NAMES[square_file(square)])

        return "".join(builder)

    def castling_xfen(self) -> str:
        builder: List[str] = []

        for color in COLORS:
            king = self.king(color)
            if king is None:
                continue

            king_file = square_file(king)
            backrank = BB_RANK_1 if color == WHITE else BB_RANK_8

            for rook_square in scan_reversed(self.clean_castling_rights() & backrank):
                rook_file = square_file(rook_square)
                a_side = rook_file < king_file

                other_rooks = self.occupied_co[color] & self.rooks & backrank & ~BB_SQUARES[rook_square]

                if any((square_file(other) < rook_file) == a_side for other in scan_reversed(other_rooks)):
                    ch = FILE_NAMES[rook_file]
                else:
                    ch = "q" if a_side else "k"

                builder.append(ch.upper() if color == WHITE else ch)

        if builder:
            return "".join(builder)
        else:
            return "-"

    def has_pseudo_legal_en_passant(self) -> bool:
        """Checks if there is a pseudo-legal en passant capture."""
        return self.ep_square is not None and any(self.generate_pseudo_legal_ep())

    def has_legal_en_passant(self) -> bool:
        """Checks if there is a legal en passant capture."""
        return self.ep_square is not None and any(self.generate_legal_ep())

    def fen(self, *, shredder: bool = False, en_passant: EnPassantSpec = "legal", promoted: Optional[bool] = None) -> str:
        """
        Gets a FEN representation of the position.

        A FEN string (e.g.,
        ``rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1``) consists
        of the board part :func:`~chess.Board.board_fen()`, the
        :data:`~chess.Board.turn`, the castling part
        (:data:`~chess.Board.castling_rights`),
        the en passant square (:data:`~chess.Board.ep_square`),
        the :data:`~chess.Board.halfmove_clock`
        and the :data:`~chess.Board.fullmove_number`.

        :param shredder: Use :func:`~chess.Board.castling_shredder_fen()`
            and encode castling rights by the file of the rook
            (like ``HAha``) instead of the default
            :func:`~chess.Board.castling_xfen()` (like ``KQkq``).
        :param en_passant: By default, only fully legal en passant squares
            are included (:func:`~chess.Board.has_legal_en_passant()`).
            Pass ``fen`` to strictly follow the FEN specification
            (always include the en passant square after a two-step pawn move)
            or ``xfen`` to follow the X-FEN specification
            (:func:`~chess.Board.has_pseudo_legal_en_passant()`).
        :param promoted: Mark promoted pieces like ``Q~``. By default, this is
            only enabled in chess variants where this is relevant.
        """
        return " ".join([
            self.epd(shredder=shredder, en_passant=en_passant, promoted=promoted),
            str(self.halfmove_clock),
            str(self.fullmove_number)
        ])

    def shredder_fen(self, *, en_passant: EnPassantSpec = "legal", promoted: Optional[bool] = None) -> str:
        return " ".join([
            self.epd(shredder=True, en_passant=en_passant, promoted=promoted),
            str(self.halfmove_clock),
            str(self.fullmove_number)
        ])

    def set_fen(self, fen: str) -> None:
        """
        Parses a FEN and sets the position from it.

        :raises: :exc:`ValueError` if syntactically invalid. Use
            :func:`~chess.Board.is_valid()` to detect invalid positions.
        """
        parts = fen.split()

        # Board part.
        try:
            board_part = parts.pop(0)
        except IndexError:
            raise ValueError("empty fen")

        # Turn.
        try:
            turn_part = parts.pop(0)
        except IndexError:
            turn = WHITE
        else:
            if turn_part == "w":
                turn = WHITE
            elif turn_part == "b":
                turn = BLACK
            else:
                raise ValueError(f"expected 'w' or 'b' for turn part of fen: {fen!r}")

        # Validate castling part.
        try:
            castling_part = parts.pop(0)
        except IndexError:
            castling_part = "-"
        else:
            if not FEN_CASTLING_REGEX.match(castling_part):
                raise ValueError(f"invalid castling part in fen: {fen!r}")

        # En passant square.
        try:
            ep_part = parts.pop(0)
        except IndexError:
            ep_square = None
        else:
            try:
                ep_square = None if ep_part == "-" else SQUARE_NAMES.index(ep_part)
            except ValueError:
                raise ValueError(f"invalid en passant part in fen: {fen!r}")

        # Check that the half-move part is valid.
        try:
            halfmove_part = parts.pop(0)
        except IndexError:
            halfmove_clock = 0
        else:
            try:
                halfmove_clock = int(halfmove_part)
            except ValueError:
                raise ValueError(f"invalid half-move clock in fen: {fen!r}")

            if halfmove_clock < 0:
                raise ValueError(f"half-move clock cannot be negative: {fen!r}")

        # Check that the full-move number part is valid.
        # 0 is allowed for compatibility, but later replaced with 1.
        try:
            fullmove_part = parts.pop(0)
        except IndexError:
            fullmove_number = 1
        else:
            try:
                fullmove_number = int(fullmove_part)
            except ValueError:
                raise ValueError(f"invalid fullmove number in fen: {fen!r}")

            if fullmove_number < 0:
                raise ValueError(f"fullmove number cannot be negative: {fen!r}")

            fullmove_number = max(fullmove_number, 1)

        # All parts should be consumed now.
        if parts:
            raise ValueError(f"fen string has more parts than expected: {fen!r}")

        # Validate the board part and set it.
        self._set_board_fen(board_part)

        # Apply.
        self.turn = turn
        self._set_castling_fen(castling_part)
        self.ep_square = ep_square
        self.halfmove_clock = halfmove_clock
        self.fullmove_number = fullmove_number
        self.clear_stack()

    def _set_castling_fen(self, castling_fen: str) -> None:
        if not castling_fen or castling_fen == "-":
            self.castling_rights = BB_EMPTY
            return

        if not FEN_CASTLING_REGEX.match(castling_fen):
            raise ValueError(f"invalid castling fen: {castling_fen!r}")

        self.castling_rights = BB_EMPTY

        for flag in castling_fen:
            color = WHITE if flag.isupper() else BLACK
            flag = flag.lower()
            backrank = BB_RANK_1 if color == WHITE else BB_RANK_8
            rooks = self.occupied_co[color] & self.rooks & backrank
            king = self.king(color)

            if flag == "q":
                # Select the leftmost rook.
                if king is not None and lsb(rooks) < king:
                    self.castling_rights |= rooks & -rooks
                else:
                    self.castling_rights |= BB_FILE_A & backrank
            elif flag == "k":
                # Select the rightmost rook.
                rook = msb(rooks)
                if king is not None and king < rook:
                    self.castling_rights |= BB_SQUARES[rook]
                else:
                    self.castling_rights |= BB_FILE_H & backrank
            else:
                self.castling_rights |= BB_FILES[FILE_NAMES.index(flag)] & backrank

    def set_castling_fen(self, castling_fen: str) -> None:
        """
        Sets castling rights from a string in FEN notation like ``Qqk``.

        Also clears the move stack.

        :raises: :exc:`ValueError` if the castling FEN is syntactically
            invalid.
        """
        self._set_castling_fen(castling_fen)
        self.clear_stack()

    def set_board_fen(self, fen: str) -> None:
        super().set_board_fen(fen)
        self.clear_stack()

    def set_piece_map(self, pieces: Mapping[Square, Piece]) -> None:
        super().set_piece_map(pieces)
        self.clear_stack()

    def set_chess960_pos(self, scharnagl: int) -> None:
        super().set_chess960_pos(scharnagl)
        self.chess960 = True
        self.turn = WHITE
        self.castling_rights = self.rooks
        self.ep_square = None
        self.halfmove_clock = 0
        self.fullmove_number = 1

        self.clear_stack()

    def chess960_pos(self, *, ignore_turn: bool = False, ignore_castling: bool = False, ignore_counters: bool = True) -> Optional[int]:
        """
        Gets the Chess960 starting position index between 0 and 959,
        or ``None`` if the current position is not a Chess960 starting
        position.

        By default, white to move (**ignore_turn**) and full castling rights
        (**ignore_castling**) are required, but move counters
        (**ignore_counters**) are ignored.
        """
        if self.ep_square:
            return None

        if not ignore_turn:
            if self.turn != WHITE:
                return None

        if not ignore_castling:
            if self.clean_castling_rights() != self.rooks:
                return None

        if not ignore_counters:
            if self.fullmove_number != 1 or self.halfmove_clock != 0:
                return None

        return super().chess960_pos()

    def _epd_operations(self, operations: Mapping[str, Union[None, str, int, float, Move, Iterable[Move]]]) -> str:
        epd: List[str] = []
        first_op = True

        for opcode, operand in operations.items():
            self._validate_epd_opcode(opcode)

            if not first_op:
                epd.append(" ")
            first_op = False
            epd.append(opcode)

            if operand is None:
                epd.append(";")
            elif isinstance(operand, Move):
                epd.append(" ")
                epd.append(self.san(operand))
                epd.append(";")
            elif isinstance(operand, int):
                epd.append(f" {operand};")
            elif isinstance(operand, float):
                assert math.isfinite(operand), f"expected numeric epd operand to be finite, got: {operand}"
                epd.append(f" {operand};")
            elif opcode == "pv" and not isinstance(operand, str) and hasattr(operand, "__iter__"):
                position = self.copy(stack=False)
                for move in operand:
                    epd.append(" ")
                    epd.append(position.san_and_push(move))
                epd.append(";")
            elif opcode in ["am", "bm"] and not isinstance(operand, str) and hasattr(operand, "__iter__"):
                for san in sorted(self.san(move) for move in operand):
                    epd.append(" ")
                    epd.append(san)
                epd.append(";")
            else:
                # Append as escaped string.
                epd.append(" \"")
                epd.append(str(operand).replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n").replace("\"", "\\\""))
                epd.append("\";")

        return "".join(epd)

    def epd(self, *, shredder: bool = False, en_passant: EnPassantSpec = "legal", promoted: Optional[bool] = None, **operations: Union[None, str, int, float, Move, Iterable[Move]]) -> str:
        """
        Gets an EPD representation of the current position.

        See :func:`~chess.Board.fen()` for FEN formatting options (*shredder*,
        *ep_square* and *promoted*).

        EPD operations can be given as keyword arguments. Supported operands
        are strings, integers, finite floats, legal moves and ``None``.
        Additionally, the operation ``pv`` accepts a legal variation as
        a list of moves. The operations ``am`` and ``bm`` accept a list of
        legal moves in the current position.

        The name of the field cannot be a lone dash and cannot contain spaces,
        newlines, carriage returns or tabs.

        *hmvc* and *fmvn* are not included by default. You can use:

        >>> import chess
        >>>
        >>> board = chess.Board()
        >>> board.epd(hmvc=board.halfmove_clock, fmvn=board.fullmove_number)
        'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - hmvc 0; fmvn 1;'
        """
        if en_passant == "fen":
            ep_square = self.ep_square
        elif en_passant == "xfen":
            ep_square = self.ep_square if self.has_pseudo_legal_en_passant() else None
        else:
            ep_square = self.ep_square if self.has_legal_en_passant() else None

        epd = [self.board_fen(promoted=promoted),
               "w" if self.turn == WHITE else "b",
               self.castling_shredder_fen() if shredder else self.castling_xfen(),
               SQUARE_NAMES[ep_square] if ep_square is not None else "-"]

        if operations:
            epd.append(self._epd_operations(operations))

        return " ".join(epd)

    def _validate_epd_opcode(self, opcode: str) -> None:
        if not opcode:
            raise ValueError("empty string is not a valid epd opcode")
        if opcode == "-":
            raise ValueError("dash (-) is not a valid epd opcode")
        if not opcode[0].isalpha():
            raise ValueError(f"expected epd opcode to start with a letter, got: {opcode!r}")
        for blacklisted in [" ", "\n", "\t", "\r"]:
            if blacklisted in opcode:
                raise ValueError(f"invalid character {blacklisted!r} in epd opcode: {opcode!r}")

    def _parse_epd_ops(self, operation_part: str, make_board: Callable[[], Self]) -> Dict[str, Union[None, str, int, float, Move, List[Move]]]:
        operations: Dict[str, Union[None, str, int, float, Move, List[Move]]] = {}
        state = "opcode"
        opcode = ""
        operand = ""
        position = None

        for ch in itertools.chain(operation_part, [None]):
            if state == "opcode":
                if ch in [" ", "\t", "\r", "\n"]:
                    if opcode == "-":
                        opcode = ""
                    elif opcode:
                        self._validate_epd_opcode(opcode)
                        state = "after_opcode"
                elif ch is None or ch == ";":
                    if opcode == "-":
                        opcode = ""
                    elif opcode:
                        operations[opcode] = [] if opcode in ["pv", "am", "bm"] else None
                        opcode = ""
                else:
                    opcode += ch
            elif state == "after_opcode":
                if ch in [" ", "\t", "\r", "\n"]:
                    pass
                elif ch == "\"":
                    state = "string"
                elif ch is None or ch == ";":
                    if opcode:
                        operations[opcode] = [] if opcode in ["pv", "am", "bm"] else None
                        opcode = ""
                    state = "opcode"
                elif ch in "+-.0123456789":
                    operand = ch
                    state = "numeric"
                else:
                    operand = ch
                    state = "san"
            elif state == "numeric":
                if ch is None or ch == ";":
                    if "." in operand or "e" in operand or "E" in operand:
                        parsed = float(operand)
                        if not math.isfinite(parsed):
                            raise ValueError(f"invalid numeric operand for epd operation {opcode!r}: {operand!r}")
                        operations[opcode] = parsed
                    else:
                        operations[opcode] = int(operand)
                    opcode = ""
                    operand = ""
                    state = "opcode"
                else:
                    operand += ch
            elif state == "string":
                if ch is None or ch == "\"":
                    operations[opcode] = operand
                    opcode = ""
                    operand = ""
                    state = "opcode"
                elif ch == "\\":
                    state = "string_escape"
                else:
                    operand += ch
            elif state == "string_escape":
                if ch is None:
                    operations[opcode] = operand
                    opcode = ""
                    operand = ""
                    state = "opcode"
                elif ch == "r":
                    operand += "\r"
                    state = "string"
                elif ch == "n":
                    operand += "\n"
                    state = "string"
                elif ch == "t":
                    operand += "\t"
                    state = "string"
                else:
                    operand += ch
                    state = "string"
            elif state == "san":
                if ch is None or ch == ";":
                    if position is None:
                        position = make_board()

                    if opcode == "pv":
                        # A variation.
                        variation: List[Move] = []
                        for token in operand.split():
                            move = position.parse_xboard(token)
                            variation.append(move)
                            position.push(move)

                        # Reset the position.
                        while position.move_stack:
                            position.pop()

                        operations[opcode] = variation
                    elif opcode in ["bm", "am"]:
                        # A set of moves.
                        operations[opcode] = [position.parse_xboard(token) for token in operand.split()]
                    else:
                        # A single move.
                        operations[opcode] = position.parse_xboard(operand)

                    opcode = ""
                    operand = ""
                    state = "opcode"
                else:
                    operand += ch

        assert state == "opcode"
        return operations

    def set_epd(self, epd: str) -> Dict[str, Union[None, str, int, float, Move, List[Move]]]:
        """
        Parses the given EPD string and uses it to set the position.

        If present, ``hmvc`` and ``fmvn`` are used to set the half-move
        clock and the full-move number. Otherwise, ``0`` and ``1`` are used.

        Returns a dictionary of parsed operations. Values can be strings,
        integers, floats, move objects, or lists of moves.

        :raises: :exc:`ValueError` if the EPD string is invalid.
        """
        parts = epd.strip().rstrip(";").split(None, 4)

        # Parse ops.
        if len(parts) > 4:
            operations = self._parse_epd_ops(parts.pop(), lambda: type(self)(" ".join(parts) + " 0 1"))
            parts.append(str(operations["hmvc"]) if "hmvc" in operations else "0")
            parts.append(str(operations["fmvn"]) if "fmvn" in operations else "1")
            self.set_fen(" ".join(parts))
            return operations
        else:
            self.set_fen(epd)
            return {}

    def san(self, move: Move) -> str:
        """
        Gets the standard algebraic notation of the given move in the context
        of the current position.
        """
        return self._algebraic(move)

    def lan(self, move: Move) -> str:
        """
        Gets the long algebraic notation of the given move in the context of
        the current position.
        """
        return self._algebraic(move, long=True)

    def san_and_push(self, move: Move) -> str:
        return self._algebraic_and_push(move)

    def _algebraic(self, move: Move, *, long: bool = False) -> str:
        san = self._algebraic_and_push(move, long=long)
        self.pop()
        return san

    def _algebraic_and_push(self, move: Move, *, long: bool = False) -> str:
        san = self._algebraic_without_suffix(move, long=long)

        # Look ahead for check or checkmate.
        self.push(move)
        is_check = self.is_check()
        is_checkmate = (is_check and self.is_checkmate()) or self.is_variant_loss() or self.is_variant_win()

        # Add check or checkmate suffix.
        if is_checkmate and move:
            return san + "#"
        elif is_check and move:
            return san + "+"
        else:
            return san

    def _algebraic_without_suffix(self, move: Move, *, long: bool = False) -> str:
        # Null move.
        if not move:
            return "--"

        # Drops.
        if move.drop:
            san = ""
            if move.drop != PAWN:
                san = piece_symbol(move.drop).upper()
            san += "@" + SQUARE_NAMES[move.to_square]
            return san

        # Castling.
        if self.is_castling(move):
            if square_file(move.to_square) < square_file(move.from_square):
                return "O-O-O"
            else:
                return "O-O"

        piece_type = self.piece_type_at(move.from_square)
        assert piece_type, f"san() and lan() expect move to be legal or null, but got {move} in {self.fen()}"
        capture = self.is_capture(move)

        if piece_type == PAWN:
            san = ""
        else:
            san = piece_symbol(piece_type).upper()

        if long:
            san += SQUARE_NAMES[move.from_square]
        elif piece_type != PAWN:
            # Get ambiguous move candidates.
            # Relevant candidates: not exactly the current move,
            # but to the same square.
            others = 0
            from_mask = self.pieces_mask(piece_type, self.turn)
            from_mask &= ~BB_SQUARES[move.from_square]
            to_mask = BB_SQUARES[move.to_square]
            for candidate in self.generate_legal_moves(from_mask, to_mask):
                others |= BB_SQUARES[candidate.from_square]

            # Disambiguate.
            if others:
                row, column = False, False

                if others & BB_RANKS[square_rank(move.from_square)]:
                    column = True

                if others & BB_FILES[square_file(move.from_square)]:
                    row = True
                else:
                    column = True

                if column:
                    san += FILE_NAMES[square_file(move.from_square)]
                if row:
                    san += RANK_NAMES[square_rank(move.from_square)]
        elif capture:
            san += FILE_NAMES[square_file(move.from_square)]

        # Captures.
        if capture:
            san += "x"
        elif long:
            san += "-"

        # Destination square.
        san += SQUARE_NAMES[move.to_square]

        # Promotion.
        if move.promotion:
            san += "=" + piece_symbol(move.promotion).upper()

        return san

    def variation_san(self, variation: Iterable[Move]) -> str:
        """
        Given a sequence of moves, returns a string representing the sequence
        in standard algebraic notation (e.g., ``1. e4 e5 2. Nf3 Nc6`` or
        ``37... Bg6 38. fxg6``).

        The board will not be modified as a result of calling this.

        :raises: :exc:`IllegalMoveError` if any moves in the sequence are illegal.
        """
        board = self.copy(stack=False)
        san: List[str] = []

        for move in variation:
            if not board.is_legal(move):
                raise IllegalMoveError(f"illegal move {move} in position {board.fen()}")

            if board.turn == WHITE:
                san.append(f"{board.fullmove_number}. {board.san_and_push(move)}")
            elif not san:
                san.append(f"{board.fullmove_number}... {board.san_and_push(move)}")
            else:
                san.append(board.san_and_push(move))

        return " ".join(san)

    def parse_san(self, san: str) -> Move:
        """
        Uses the current position as the context to parse a move in standard
        algebraic notation and returns the corresponding move object.

        Ambiguous moves are rejected. Overspecified moves (including long
        algebraic notation) are accepted. Some common syntactical deviations
        are also accepted.

        The returned move is guaranteed to be either legal or a null move.

        :raises:
            :exc:`ValueError` (specifically an exception specified below) if the SAN is invalid, illegal or ambiguous.

            - :exc:`InvalidMoveError` if the SAN is syntactically invalid.
            - :exc:`IllegalMoveError` if the SAN is illegal.
            - :exc:`AmbiguousMoveError` if the SAN is ambiguous.
        """
        # Castling.
        try:
            if san in ["O-O", "O-O+", "O-O#", "0-0", "0-0+", "0-0#"]:
                return next(move for move in self.generate_castling_moves() if self.is_kingside_castling(move))
            elif san in ["O-O-O", "O-O-O+", "O-O-O#", "0-0-0", "0-0-0+", "0-0-0#"]:
                return next(move for move in self.generate_castling_moves() if self.is_queenside_castling(move))
        except StopIteration:
            raise IllegalMoveError(f"illegal san: {san!r} in {self.fen()}")

        # Match normal moves.
        match = SAN_REGEX.match(san)
        if not match:
            # Null moves.
            if san in ["--", "Z0", "0000", "@@@@"]:
                return Move.null()
            elif "," in san:
                raise InvalidMoveError(f"unsupported multi-leg move: {san!r}")
            else:
                raise InvalidMoveError(f"invalid san: {san!r}")

        # Get target square. Mask our own pieces to exclude castling moves.
        to_square = SQUARE_NAMES.index(match.group(4))
        to_mask = BB_SQUARES[to_square] & ~self.occupied_co[self.turn]

        # Get the promotion piece type.
        p = match.group(5)
        promotion = PIECE_SYMBOLS.index(p[-1].lower()) if p else None

        # Filter by original square.
        from_mask = BB_ALL
        from_file = None
        from_rank = None
        if match.group(2):
            from_file = FILE_NAMES.index(match.group(2))
            from_mask &= BB_FILES[from_file]
        if match.group(3):
            from_rank = int(match.group(3)) - 1
            from_mask &= BB_RANKS[from_rank]

        # Filter by piece type.
        if match.group(1):
            piece_type = PIECE_SYMBOLS.index(match.group(1).lower())
            from_mask &= self.pieces_mask(piece_type, self.turn)
        elif from_file is not None and from_rank is not None:
            # Allow fully specified moves, even if they are not pawn moves,
            # including castling moves.
            move = self.find_move(square(from_file, from_rank), to_square, promotion)
            if move.promotion == promotion:
                return move
            else:
                raise IllegalMoveError(f"missing promotion piece type: {san!r} in {self.fen()}")
        else:
            from_mask &= self.pawns

            # Do not allow pawn captures if file is not specified.
            if from_file is None:
                from_mask &= BB_FILES[square_file(to_square)]

        # Match legal moves.
        matched_move = None
        for move in self.generate_legal_moves(from_mask, to_mask):
            if move.promotion != promotion:
                continue

            if matched_move:
                raise AmbiguousMoveError(f"ambiguous san: {san!r} in {self.fen()}")

            matched_move = move

        if not matched_move:
            raise IllegalMoveError(f"illegal san: {san!r} in {self.fen()}")

        return matched_move

    def push_san(self, san: str) -> Move:
        """
        Parses a move in standard algebraic notation, makes the move and puts
        it onto the move stack.

        Returns the move.

        :raises:
            :exc:`ValueError` (specifically an exception specified below) if neither legal nor a null move.

            - :exc:`InvalidMoveError` if the SAN is syntactically invalid.
            - :exc:`IllegalMoveError` if the SAN is illegal.
            - :exc:`AmbiguousMoveError` if the SAN is ambiguous.
        """
        move = self.parse_san(san)
        self.push(move)
        return move

    def uci(self, move: Move, *, chess960: Optional[bool] = None) -> str:
        """
        Gets the UCI notation of the move.

        *chess960* defaults to the mode of the board. Pass ``True`` to force
        Chess960 mode.
        """
        if chess960 is None:
            chess960 = self.chess960

        move = self._to_chess960(move)
        move = self._from_chess960(chess960, move.from_square, move.to_square, move.promotion, move.drop)
        return move.uci()

    def parse_uci(self, uci: str) -> Move:
        """
        Parses the given move in UCI notation.

        Supports both Chess960 and standard UCI notation.

        The returned move is guaranteed to be either legal or a null move.

        :raises:
            :exc:`ValueError` (specifically an exception specified below) if the move is invalid or illegal in the
            current position (but not a null move).

            - :exc:`InvalidMoveError` if the UCI is syntactically invalid.
            - :exc:`IllegalMoveError` if the UCI is illegal.
        """
        move = Move.from_uci(uci)

        if not move:
            return move

        move = self._to_chess960(move)
        move = self._from_chess960(self.chess960, move.from_square, move.to_square, move.promotion, move.drop)

        if not self.is_legal(move):
            raise IllegalMoveError(f"illegal uci: {uci!r} in {self.fen()}")

        return move

    def push_uci(self, uci: str) -> Move:
        """
        Parses a move in UCI notation and puts it on the move stack.

        Returns the move.

        :raises:
            :exc:`ValueError` (specifically an exception specified below) if the move is invalid or illegal in the
            current position (but not a null move).

            - :exc:`InvalidMoveError` if the UCI is syntactically invalid.
            - :exc:`IllegalMoveError` if the UCI is illegal.
        """
        move = self.parse_uci(uci)
        self.push(move)
        return move

    def xboard(self, move: Move, chess960: Optional[bool] = None) -> str:
        if chess960 is None:
            chess960 = self.chess960

        if not chess960 or not self.is_castling(move):
            return move.xboard()
        elif self.is_kingside_castling(move):
            return "O-O"
        else:
            return "O-O-O"

    def parse_xboard(self, xboard: str) -> Move:
        return self.parse_san(xboard)

    push_xboard = push_san

    def is_en_passant(self, move: Move) -> bool:
        """Checks if the given pseudo-legal move is an en passant capture."""
        return (self.ep_square == move.to_square and
                bool(self.pawns & BB_SQUARES[move.from_square]) and
                abs(move.to_square - move.from_square) in [7, 9] and
                not self.occupied & BB_SQUARES[move.to_square])

    def is_capture(self, move: Move) -> bool:
        """Checks if the given pseudo-legal move is a capture."""
        touched = BB_SQUARES[move.from_square] ^ BB_SQUARES[move.to_square]
        return bool(touched & self.occupied_co[not self.turn]) or self.is_en_passant(move)

    def is_zeroing(self, move: Move) -> bool:
        """Checks if the given pseudo-legal move is a capture or pawn move."""
        touched = BB_SQUARES[move.from_square] ^ BB_SQUARES[move.to_square]
        return bool(touched & self.pawns or touched & self.occupied_co[not self.turn] or move.drop == PAWN)

    def _reduces_castling_rights(self, move: Move) -> bool:
        cr = self.clean_castling_rights()
        touched = BB_SQUARES[move.from_square] ^ BB_SQUARES[move.to_square]
        return bool(touched & cr or
                    cr & BB_RANK_1 and touched & self.kings & self.occupied_co[WHITE] & ~self._effective_promoted() or
                    cr & BB_RANK_8 and touched & self.kings & self.occupied_co[BLACK] & ~self._effective_promoted())

    def is_irreversible(self, move: Move) -> bool:
        """
        Checks if the given pseudo-legal move is irreversible.

        In standard chess, pawn moves, captures, moves that destroy castling
        rights and moves that cede en passant are irreversible.

        This method has false-negatives with forced lines. For example, a check
        that will force the king to lose castling rights is not considered
        irreversible. Only the actual king move is.
        """
        return self.is_zeroing(move) or self._reduces_castling_rights(move) or self.has_legal_en_passant()

    def is_castling(self, move: Move) -> bool:
        """Checks if the given pseudo-legal move is a castling move."""
        if self.kings & BB_SQUARES[move.from_square]:
            diff = square_file(move.from_square) - square_file(move.to_square)
            return abs(diff) > 1 or bool(self.rooks & self.occupied_co[self.turn] & BB_SQUARES[move.to_square])
        return False

    def is_kingside_castling(self, move: Move) -> bool:
        """
        Checks if the given pseudo-legal move is a kingside castling move.
        """
        return self.is_castling(move) and square_file(move.to_square) > square_file(move.from_square)

    def is_queenside_castling(self, move: Move) -> bool:
        """
        Checks if the given pseudo-legal move is a queenside castling move.
        """
        return self.is_castling(move) and square_file(move.to_square) < square_file(move.from_square)

    def clean_castling_rights(self) -> Bitboard:
        """
        Returns valid castling rights filtered from
        :data:`~chess.Board.castling_rights`.
        """
        if self._stack:
            # No new castling rights are assigned in a game, so we can assume
            # they were filtered already.
            return self.castling_rights

        castling = self.castling_rights & self.rooks
        white_castling = castling & BB_RANK_1 & self.occupied_co[WHITE]
        black_castling = castling & BB_RANK_8 & self.occupied_co[BLACK]

        if not self.chess960:
            # The rooks must be on a1, h1, a8 or h8.
            white_castling &= (BB_A1 | BB_H1)
            black_castling &= (BB_A8 | BB_H8)

            # The kings must be on e1 or e8.
            if not self.occupied_co[WHITE] & self.kings & ~self._effective_promoted() & BB_E1:
                white_castling = 0
            if not self.occupied_co[BLACK] & self.kings & ~self._effective_promoted() & BB_E8:
                black_castling = 0

            return white_castling | black_castling
        else:
            # The kings must be on the back rank.
            white_king_mask = self.occupied_co[WHITE] & self.kings & BB_RANK_1 & ~self._effective_promoted()
            black_king_mask = self.occupied_co[BLACK] & self.kings & BB_RANK_8 & ~self._effective_promoted()
            if not white_king_mask:
                white_castling = 0
            if not black_king_mask:
                black_castling = 0

            # There are only two ways of castling, a-side and h-side, and the
            # king must be between the rooks.
            white_a_side = white_castling & -white_castling
            white_h_side = BB_SQUARES[msb(white_castling)] if white_castling else 0

            if white_a_side and msb(white_a_side) > msb(white_king_mask):
                white_a_side = 0
            if white_h_side and msb(white_h_side) < msb(white_king_mask):
                white_h_side = 0

            black_a_side = black_castling & -black_castling
            black_h_side = BB_SQUARES[msb(black_castling)] if black_castling else BB_EMPTY

            if black_a_side and msb(black_a_side) > msb(black_king_mask):
                black_a_side = 0
            if black_h_side and msb(black_h_side) < msb(black_king_mask):
                black_h_side = 0

            # Done.
            return black_a_side | black_h_side | white_a_side | white_h_side

    def has_castling_rights(self, color: Color) -> bool:
        """Checks if the given side has castling rights."""
        backrank = BB_RANK_1 if color == WHITE else BB_RANK_8
        return bool(self.clean_castling_rights() & backrank)

    def has_kingside_castling_rights(self, color: Color) -> bool:
        """
        Checks if the given side has kingside (that is h-side in Chess960)
        castling rights.
        """
        backrank = BB_RANK_1 if color == WHITE else BB_RANK_8
        king_mask = self.kings & self.occupied_co[color] & backrank & ~self._effective_promoted()
        if not king_mask:
            return False

        castling_rights = self.clean_castling_rights() & backrank
        while castling_rights:
            rook = castling_rights & -castling_rights

            if rook > king_mask:
                return True

            castling_rights &= castling_rights - 1

        return False

    def has_queenside_castling_rights(self, color: Color) -> bool:
        """
        Checks if the given side has queenside (that is a-side in Chess960)
        castling rights.
        """
        backrank = BB_RANK_1 if color == WHITE else BB_RANK_8
        king_mask = self.kings & self.occupied_co[color] & backrank & ~self._effective_promoted()
        if not king_mask:
            return False

        castling_rights = self.clean_castling_rights() & backrank
        while castling_rights:
            rook = castling_rights & -castling_rights

            if rook < king_mask:
                return True

            castling_rights &= castling_rights - 1

        return False

    def has_chess960_castling_rights(self) -> bool:
        """
        Checks if there are castling rights that are only possible in Chess960.
        """
        # Get valid Chess960 castling rights.
        chess960 = self.chess960
        self.chess960 = True
        castling_rights = self.clean_castling_rights()
        self.chess960 = chess960

        # Standard chess castling rights can only be on the standard
        # starting rook squares.
        if castling_rights & ~BB_CORNERS:
            return True

        # If there are any castling rights in standard chess, the king must be
        # on e1 or e8.
        if castling_rights & BB_RANK_1 and not self.occupied_co[WHITE] & self.kings & BB_E1:
            return True
        if castling_rights & BB_RANK_8 and not self.occupied_co[BLACK] & self.kings & BB_E8:
            return True

        return False

    def status(self) -> Status:
        """
        Gets a bitmask of possible problems with the position.

        :data:`~chess.STATUS_VALID` if all basic validity requirements are met.
        This does not imply that the position is actually reachable with a
        series of legal moves from the starting position.

        Otherwise, bitwise combinations of:
        :data:`~chess.STATUS_NO_WHITE_KING`,
        :data:`~chess.STATUS_NO_BLACK_KING`,
        :data:`~chess.STATUS_TOO_MANY_KINGS`,
        :data:`~chess.STATUS_TOO_MANY_WHITE_PAWNS`,
        :data:`~chess.STATUS_TOO_MANY_BLACK_PAWNS`,
        :data:`~chess.STATUS_PAWNS_ON_BACKRANK`,
        :data:`~chess.STATUS_TOO_MANY_WHITE_PIECES`,
        :data:`~chess.STATUS_TOO_MANY_BLACK_PIECES`,
        :data:`~chess.STATUS_BAD_CASTLING_RIGHTS`,
        :data:`~chess.STATUS_INVALID_EP_SQUARE`,
        :data:`~chess.STATUS_OPPOSITE_CHECK`,
        :data:`~chess.STATUS_EMPTY`,
        :data:`~chess.STATUS_RACE_CHECK`,
        :data:`~chess.STATUS_RACE_OVER`,
        :data:`~chess.STATUS_RACE_MATERIAL`,
        :data:`~chess.STATUS_TOO_MANY_CHECKERS`,
        :data:`~chess.STATUS_IMPOSSIBLE_CHECK`.
        """
        errors = STATUS_VALID

        # There must be at least one piece.
        if not self.occupied:
            errors |= STATUS_EMPTY

        # There must be exactly one king of each color.
        if not self.occupied_co[WHITE] & self.kings & ~self._effective_promoted():
            errors |= STATUS_NO_WHITE_KING
        if not self.occupied_co[BLACK] & self.kings & ~self._effective_promoted():
            errors |= STATUS_NO_BLACK_KING
        if popcount(self.occupied & self.kings & ~self._effective_promoted()) > 2:
            errors |= STATUS_TOO_MANY_KINGS

        # There can not be more than 16 pieces of any color.
        if popcount(self.occupied_co[WHITE]) > 16:
            errors |= STATUS_TOO_MANY_WHITE_PIECES
        if popcount(self.occupied_co[BLACK]) > 16:
            errors |= STATUS_TOO_MANY_BLACK_PIECES

        # There can not be more than 8 pawns of any color.
        if popcount(self.occupied_co[WHITE] & self.pawns) > 8:
            errors |= STATUS_TOO_MANY_WHITE_PAWNS
        if popcount(self.occupied_co[BLACK] & self.pawns) > 8:
            errors |= STATUS_TOO_MANY_BLACK_PAWNS

        # Pawns can not be on the back rank.
        if self.pawns & BB_BACKRANKS:
            errors |= STATUS_PAWNS_ON_BACKRANK

        # Castling rights.
        if self.castling_rights != self.clean_castling_rights():
            errors |= STATUS_BAD_CASTLING_RIGHTS

        # En passant.
        valid_ep_square = self._valid_ep_square()
        if self.ep_square != valid_ep_square:
            errors |= STATUS_INVALID_EP_SQUARE

        # Side to move giving check.
        if self.was_into_check():
            errors |= STATUS_OPPOSITE_CHECK

        # More than the maximum number of possible checkers in the variant,
        # or impossibly aligned checkers.
        checkers = self.checkers_mask()
        our_kings = self.kings & self.occupied_co[self.turn] & ~self._effective_promoted()
        if checkers:
            if popcount(checkers) > 2:
                errors |= STATUS_TOO_MANY_CHECKERS

            if valid_ep_square is not None:
                pushed_to = valid_ep_square ^ A2
                pushed_from = valid_ep_square ^ A4
                occupied_before = (self.occupied & ~BB_SQUARES[pushed_to]) | BB_SQUARES[pushed_from]
                if popcount(checkers) > 1 or (
                        msb(checkers) != pushed_to and
                        self._attacked_for_king(our_kings, occupied_before)):
                    errors |= STATUS_IMPOSSIBLE_CHECK
            else:
                if popcount(checkers) > 2 or (popcount(checkers) == 2 and ray(lsb(checkers), msb(checkers)) & our_kings):
                    errors |= STATUS_IMPOSSIBLE_CHECK

            # Multiple steppers.
            steppers = self.pawns | self.knights | self.kings
            if popcount(checkers & steppers) > 1:
                errors |= STATUS_IMPOSSIBLE_CHECK

        return errors

    def _valid_ep_square(self) -> Optional[Square]:
        if not self.ep_square:
            return None

        if self.turn == WHITE:
            ep_rank = RANK_6
            pawn_mask = shift_down(BB_SQUARES[self.ep_square])
            seventh_rank_mask = shift_up(BB_SQUARES[self.ep_square])
        else:
            ep_rank = RANK_3
            pawn_mask = shift_up(BB_SQUARES[self.ep_square])
            seventh_rank_mask = shift_down(BB_SQUARES[self.ep_square])

        # The en passant square must be on the third or sixth rank.
        if square_rank(self.ep_square) != ep_rank:
            return None

        # The last move must have been a double pawn push, so there must
        # be a pawn of the correct color on the fourth or fifth rank.
        if not self.pawns & self.occupied_co[not self.turn] & pawn_mask:
            return None

        # And the en passant square must be empty.
        if self.occupied & BB_SQUARES[self.ep_square]:
            return None

        # And the second rank must be empty.
        if self.occupied & seventh_rank_mask:
            return None

        return self.ep_square

    def is_valid(self) -> bool:
        """
        Checks some basic validity requirements.

        See :func:`~chess.Board.status()` for details.
        """
        return self.status() == STATUS_VALID

    def _ep_skewered(self, king: Square, capturer: Square) -> bool:
        # Handle the special case where the king would be in check if the
        # pawn and its capturer disappear from the rank.

        # Vertical skewers of the captured pawn are not possible. (Pins on
        # the capturer are not handled here.)
        assert self.ep_square is not None

        last_double = self.ep_square + (-8 if self.turn == WHITE else 8)

        occupancy = (self.occupied & ~BB_SQUARES[last_double] &
                     ~BB_SQUARES[capturer] | BB_SQUARES[self.ep_square])

        # Horizontal attack on the fifth or fourth rank.
        horizontal_attackers = self.occupied_co[not self.turn] & (self.rooks | self.queens)
        if BB_RANK_ATTACKS[king][BB_RANK_MASKS[king] & occupancy] & horizontal_attackers:
            return True

        # Diagonal skewers. These are not actually possible in a real game,
        # because if the latest double pawn move covers a diagonal attack,
        # then the other side would have been in check already.
        diagonal_attackers = self.occupied_co[not self.turn] & (self.bishops | self.queens)
        if BB_DIAG_ATTACKS[king][BB_DIAG_MASKS[king] & occupancy] & diagonal_attackers:
            return True

        return False

    def _slider_blockers(self, king: Square) -> Bitboard:
        rooks_and_queens = self.rooks | self.queens
        bishops_and_queens = self.bishops | self.queens

        snipers = ((BB_RANK_ATTACKS[king][0] & rooks_and_queens) |
                   (BB_FILE_ATTACKS[king][0] & rooks_and_queens) |
                   (BB_DIAG_ATTACKS[king][0] & bishops_and_queens))

        blockers = 0

        for sniper in scan_reversed(snipers & self.occupied_co[not self.turn]):
            b = between(king, sniper) & self.occupied

            # Add to blockers if exactly one piece in-between.
            if b and BB_SQUARES[msb(b)] == b:
                blockers |= b

        return blockers & self.occupied_co[self.turn]

    def _is_safe(self, king: Square, blockers: Bitboard, move: Move) -> bool:
        if move.from_square == king:
            if self.is_castling(move):
                return True
            else:
                return not self.is_attacked_by(not self.turn, move.to_square)
        elif self.is_en_passant(move):
            return bool(self.pin_mask(self.turn, move.from_square) & BB_SQUARES[move.to_square] and
                        not self._ep_skewered(king, move.from_square))
        else:
            return bool(not blockers & BB_SQUARES[move.from_square] or
                        ray(move.from_square, move.to_square) & BB_SQUARES[king])

    def _generate_evasions(self, king: Square, checkers: Bitboard, from_mask: Bitboard = BB_ALL, to_mask: Bitboard = BB_ALL) -> Iterator[Move]:
        sliders = checkers & (self.bishops | self.rooks | self.queens)

        attacked = 0
        for checker in scan_reversed(sliders):
            attacked |= ray(king, checker) & ~BB_SQUARES[checker]

        if BB_SQUARES[king] & from_mask:
            for to_square in scan_reversed(BB_KING_ATTACKS[king] & ~self.occupied_co[self.turn] & ~attacked & to_mask):
                yield Move(king, to_square)

        checker = msb(checkers)
        if BB_SQUARES[checker] == checkers:
            # Capture or block a single checker.
            target = between(king, checker) | checkers

            yield from self.generate_pseudo_legal_moves(~self.kings & from_mask, target & to_mask)

            # Capture the checking pawn en passant (but avoid yielding
            # duplicate moves).
            if self.ep_square and not BB_SQUARES[self.ep_square] & target:
                last_double = self.ep_square + (-8 if self.turn == WHITE else 8)
                if last_double == checker:
                    yield from self.generate_pseudo_legal_ep(from_mask, to_mask)

    def generate_legal_moves(self, from_mask: Bitboard = BB_ALL, to_mask: Bitboard = BB_ALL) -> Iterator[Move]:
        if self.is_variant_end():
            return

        king_mask = self.kings & self.occupied_co[self.turn]
        if king_mask:
            king = msb(king_mask)
            blockers = self._slider_blockers(king)
            checkers = self.attackers_mask(not self.turn, king)
            if checkers:
                for move in self._generate_evasions(king, checkers, from_mask, to_mask):
                    if self._is_safe(king, blockers, move):
                        yield move
            else:
                for move in self.generate_pseudo_legal_moves(from_mask, to_mask):
                    if self._is_safe(king, blockers, move):
                        yield move
        else:
            yield from self.generate_pseudo_legal_moves(from_mask, to_mask)

    def generate_legal_ep(self, from_mask: Bitboard = BB_ALL, to_mask: Bitboard = BB_ALL) -> Iterator[Move]:
        if self.is_variant_end():
            return

        for move in self.generate_pseudo_legal_ep(from_mask, to_mask):
            if not self.is_into_check(move):
                yield move

    def generate_legal_captures(self, from_mask: Bitboard = BB_ALL, to_mask: Bitboard = BB_ALL) -> Iterator[Move]:
        return itertools.chain(
            self.generate_legal_moves(from_mask, to_mask & self.occupied_co[not self.turn]),
            self.generate_legal_ep(from_mask, to_mask))

    def _attacked_for_king(self, path: Bitboard, occupied: Bitboard) -> bool:
        return any(self.attackers_mask(not self.turn, sq, occupied) for sq in scan_reversed(path))

    def generate_castling_moves(self, from_mask: Bitboard = BB_ALL, to_mask: Bitboard = BB_ALL) -> Iterator[Move]:
        if self.is_variant_end():
            return

        backrank = BB_RANK_1 if self.turn == WHITE else BB_RANK_8
        king = self.occupied_co[self.turn] & self.kings & ~self._effective_promoted() & backrank & from_mask
        king &= -king
        if not king:
            return

        bb_c = BB_FILE_C & backrank
        bb_d = BB_FILE_D & backrank
        bb_f = BB_FILE_F & backrank
        bb_g = BB_FILE_G & backrank

        for candidate in scan_reversed(self.clean_castling_rights() & backrank & to_mask):
            rook = BB_SQUARES[candidate]

            a_side = rook < king
            king_to = bb_c if a_side else bb_g
            rook_to = bb_d if a_side else bb_f

            king_path = between(msb(king), msb(king_to))
            rook_path = between(candidate, msb(rook_to))

            if not ((self.occupied ^ king ^ rook) & (king_path | rook_path | king_to | rook_to) or
                    self._attacked_for_king(king_path | king, self.occupied ^ king) or
                    self._attacked_for_king(king_to, self.occupied ^ king ^ rook ^ rook_to)):
                yield self._from_chess960(self.chess960, msb(king), candidate)

    def _from_chess960(self, chess960: bool, from_square: Square, to_square: Square, promotion: Optional[PieceType] = None, drop: Optional[PieceType] = None) -> Move:
        if not chess960 and promotion is None and drop is None:
            if from_square == E1 and self.kings & BB_E1:
                if to_square == H1:
                    return Move(E1, G1)
                elif to_square == A1:
                    return Move(E1, C1)
            elif from_square == E8 and self.kings & BB_E8:
                if to_square == H8:
                    return Move(E8, G8)
                elif to_square == A8:
                    return Move(E8, C8)

        return Move(from_square, to_square, promotion, drop)

    def _to_chess960(self, move: Move) -> Move:
        if move.from_square == E1 and self.kings & BB_E1:
            if move.to_square == G1 and not self.rooks & BB_G1:
                return Move(E1, H1)
            elif move.to_square == C1 and not self.rooks & BB_C1:
                return Move(E1, A1)
        elif move.from_square == E8 and self.kings & BB_E8:
            if move.to_square == G8 and not self.rooks & BB_G8:
                return Move(E8, H8)
            elif move.to_square == C8 and not self.rooks & BB_C8:
                return Move(E8, A8)

        return move

    def _transposition_key(self) -> Hashable:
        return (self.pawns, self.knights, self.bishops, self.rooks,
                self.queens, self.kings,
                self._effective_promoted(),
                self.occupied_co[WHITE], self.occupied_co[BLACK],
                self.turn, self.clean_castling_rights(),
                self.ep_square if self.has_legal_en_passant() else None)

    def __repr__(self) -> str:
        if not self.chess960:
            return f"{type(self).__name__}({self.fen()!r})"
        else:
            return f"{type(self).__name__}({self.fen()!r}, chess960=True)"

    def _repr_svg_(self) -> str:
        import chess.svg
        return chess.svg.board(
            board=self,
            size=390,
            lastmove=self.peek() if self.move_stack else None,
            check=self.king(self.turn) if self.is_check() else None)

    def __eq__(self, board: object) -> bool:
        if isinstance(board, Board):
            return (
                self.halfmove_clock == board.halfmove_clock and
                self.fullmove_number == board.fullmove_number and
                type(self).uci_variant == type(board).uci_variant and
                self._transposition_key() == board._transposition_key())
        else:
            return NotImplemented

    def apply_transform(self, f: Callable[[Bitboard], Bitboard]) -> None:
        super().apply_transform(f)
        self.clear_stack()
        self.ep_square = None if self.ep_square is None else msb(f(BB_SQUARES[self.ep_square]))
        self.castling_rights = f(self.castling_rights)

    def transform(self, f: Callable[[Bitboard], Bitboard]) -> Self:
        board = self.copy(stack=False)
        board.apply_transform(f)
        return board

    def apply_mirror(self) -> None:
        super().apply_mirror()
        self.turn = not self.turn

    def mirror(self) -> Self:
        """
        Returns a mirrored copy of the board.

        The board is mirrored vertically and piece colors are swapped, so that
        the position is equivalent modulo color. Also swap the "en passant"
        square, castling rights and turn.

        Alternatively, :func:`~chess.Board.apply_mirror()` can be used
        to mirror the board.
        """
        board = self.copy()
        board.apply_mirror()
        return board

    def copy(self, *, stack: Union[bool, int] = True) -> Self:
        """
        Creates a copy of the board.

        Defaults to copying the entire move stack. Alternatively, *stack* can
        be ``False``, or an integer to copy a limited number of moves.
        """
        board = super().copy()

        board.chess960 = self.chess960

        board.ep_square = self.ep_square
        board.castling_rights = self.castling_rights
        board.turn = self.turn
        board.fullmove_number = self.fullmove_number
        board.halfmove_clock = self.halfmove_clock

        if stack:
            stack = len(self.move_stack) if stack is True else stack
            board.move_stack = [copy.copy(move) for move in self.move_stack[-stack:]]
            board._stack = self._stack[-stack:]

        return board

    @classmethod
    def empty(cls: Type[BoardT], *, chess960: bool = False) -> BoardT:
        """Creates a new empty board. Also see :func:`~chess.Board.clear()`."""
        return cls(None, chess960=chess960)

    @classmethod
    def from_epd(cls: Type[BoardT], epd: str, *, chess960: bool = False) -> Tuple[BoardT, Dict[str, Union[None, str, int, float, Move, List[Move]]]]:
        """
        Creates a new board from an EPD string. See
        :func:`~chess.Board.set_epd()`.

        Returns the board and the dictionary of parsed operations as a tuple.
        """
        board = cls.empty(chess960=chess960)
        return board, board.set_epd(epd)

    @classmethod
    def from_chess960_pos(cls: Type[BoardT], scharnagl: int) -> BoardT:
        board = cls.empty(chess960=True)
        board.set_chess960_pos(scharnagl)
        return board