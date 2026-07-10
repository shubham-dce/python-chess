from typing import Optional, Dict
import chess
import chess.polyglot
from .indexer import PositionStats

def lookup_position(fen: str, index: Dict[int, PositionStats]) -> Optional[PositionStats]:
    """
    Looks up the :class:`PositionStats` for the position given as *fen*
    within *index* (as produced by :func:`chess.games_stats.build_position_index`).

    :raises: :exc:`InvalidPositionError` if *fen* is malformed.
    :returns: ``None`` if the position is not present in *index*.
    """
    try:
        board = chess.Board(fen)
    except ValueError:
        raise InvalidPositionError(f"Malformed FEN: {fen!r}") from ValueError
    position_hash = chess.polyglot.zobrist_hash(board)
    return index.get(position_hash)

class InvalidPositionError(ValueError):
    """Raised by :func:`lookup_position` when given a malformed FEN."""
    pass
