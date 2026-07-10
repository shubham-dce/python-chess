import dataclasses
import chess
from .position_iter import iter_position_hashes

@dataclasses.dataclass
class PositionStats:
    """Win/loss/draw tally accumulated for a single chess position."""
    total_games: int = 0
    white_wins: int = 0
    black_wins: int = 0
    draws: int = 0
    unknown: int = 0

    @property
    def decisive_games(self) -> int:
        """Games reaching this position with a definitive outcome (win, loss or draw), excluding ``unknown``."""
        return self.white_wins + self.black_wins + self.draws

def parse_result(result: str) -> str:
    """
    Maps a PGN ``Result`` header value to one of ``"white"``, ``"black"``,
    ``"draw"`` or ``"unknown"`` (for unfinished/unrecognised results, e.g. ``"*"``).
    """
    if result == "1-0":
        return "white"
    elif result == "0-1":
        return "black"
    elif result == "1/2-1/2":
        return "draw"
    else:
        return "unknown"

from typing import Dict

def build_position_index(games: list[chess.pgn.game]) -> Dict[int, PositionStats]:
    """
    Builds a mapping from position (Zobrist hash) to :class:`PositionStats`
    by replaying the mainline of every game in *games* and tallying each
    game's result against every position it passed through. It stores the game stats (win, draw, loss, unknown) against each hash i.e. position
    """
    index: Dict[int, PositionStats] = {}

    for game in games:
        outcome = parse_result(game.headers.get("Result", "*"))

        for position_hash in iter_position_hashes(game):
            stats = index.setdefault(position_hash, PositionStats())

            if outcome == "white":
                stats.white_wins += 1
            elif outcome == "black":
                stats.black_wins += 1
            elif outcome == "draw":
                stats.draws += 1
            else:
                stats.unknown += 1

            stats.total_games += 1
            
    return index