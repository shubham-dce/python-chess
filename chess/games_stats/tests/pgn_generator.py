import chess
import chess.pgn
from typing import List, Tuple


OPENING_TEMPLATES: List[Tuple[List[str], str, int]] = [
    (["e4", "e5", "Nf3", "Nc6"], "1-0", 50),   
    (["e4", "e5", "Nf3", "Nc6"], "0-1", 30),   
    (["e4", "e5", "Nf3", "Nc6"], "1/2-1/2", 20),  
    (["d4", "d5", "c4"], "1-0", 40),           
    (["d4", "d5", "c4"], "0-1", 10),           
    (["e4", "c5"], "*", 15),                   
]


def generate_deterministic_game(moves_san: List[str], result: str) -> chess.pgn.Game:
    """Build one game from a fixed list of SAN moves and a fixed result — fully reproducible."""
    board = chess.Board()
    game = chess.pgn.Game()
    node = game

    for san in moves_san:
        move = board.parse_san(san) 
        board.push(move)
        node = node.add_variation(move)

    game.headers["Result"] = result
    return game


def generate_mock_pgn(path: str) -> None:
    """
    Generate a deterministic mock PGN file from OPENING_TEMPLATES.
    Same output every run — no randomness, exact counts are predictable in tests.
    """
    with open(path, "w", encoding="utf-8") as f:
        game_num = 1
        for moves_san, result, repeat_count in OPENING_TEMPLATES:
            for _ in range(repeat_count):
                game = generate_deterministic_game(moves_san, result)
                game.headers["Event"] = f"Mock Game {game_num}"
                print(game, file=f, end="\n\n")
                game_num += 1