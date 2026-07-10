import chess.pgn

from typing import List

def load_games(pgn_path: str) -> List[chess.pgn.Game]:
    """
    Reads every game from the PGN file at *pgn_path* and returns them as a
    list, in the order they appear in the file.
    """
    games: List[chess.pgn.Game] = []

    with open(pgn_path, encoding="utf-8") as pgn_file:
        # read game until games exhaust in the pgn_file
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is None:
                break
            games.append(game)
    
    return games