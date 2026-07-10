from typing import Iterator, Tuple
from chess.polyglot import zobrist_hash
import chess
import chess.pgn

def iter_position_hashes(game: chess.pgn.Game) -> Iterator[Tuple[int, chess.Board]]:
    """
    Yields the Zobrist hash of every position along the mainline of *game*,
    starting with the game's initial position and then one hash per mainline
    move. Moves in side variations are not visited.
    """

    board = game.board() # starting position

    yield zobrist_hash(board)

    for move in game.mainline_moves(): # only mainline movement, ignoring variations
        board.push(move)
        yield zobrist_hash(board)