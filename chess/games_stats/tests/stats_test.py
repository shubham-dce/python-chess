import os

import mongomock
import pytest

import chess
import chess.polyglot
from chess.games_stats import (
    MongoPositionStatsStore,
    PositionStats,
    SQLitePositionStatsStore,
    build_position_index,
    iter_position_hashes,
    load_games,
    lookup_position,
    parse_result,
)
from chess.games_stats.tests.pgn_generator import generate_mock_pgn

SAMPLE_PGN = os.path.join(os.path.dirname(__file__), "data", "sample.pgn")

def test_load_games_returns_correct_count():
    games = load_games(SAMPLE_PGN)
    assert len(games) == 2

def test_load_games_reads_headers_correctly():
    games = load_games(SAMPLE_PGN)
    assert games[0].headers["White"] == "A"
    assert games[1].headers["Result"] == "0-1"

def test_load_games_empty_file(tmp_path):
    empty_pgn = tmp_path / "empty.pgn"
    empty_pgn.write_text("")
    assert load_games(str(empty_pgn)) == []  

def test_iter_position_hashes_matches_move_count():
    games = load_games(SAMPLE_PGN)
    game = games[0]
    hashes = list(iter_position_hashes(game))
    assert len(hashes) == 4 # one for the root Game and three moves

def test_build_position_index_shared_starting_position() -> None:
    games = load_games(SAMPLE_PGN)
    index = build_position_index(games)

    start_hash = chess.polyglot.zobrist_hash(chess.Board())  #starting position hash - standard position

    assert start_hash in index
    stats = index[start_hash]
    assert stats.total_games == 2
    assert stats.white_wins == 1
    assert stats.black_wins == 1
    assert stats.draws == 0
    assert stats.unknown == 0

def test_build_position_index_unique_position_after_divergent_moves() -> None:
    games = load_games(SAMPLE_PGN)
    index = build_position_index(games)

    board = chess.Board()
    board.push_san("e4")
    after_e4_hash = chess.polyglot.zobrist_hash(board)

    assert after_e4_hash in index
    stats = index[after_e4_hash]
    assert stats.total_games == 1       
    assert stats.white_wins == 1   

def test_build_position_index_win_rate_in_decisive_games() -> None:
    stats = PositionStats(total_games=5, white_wins=2, black_wins=1, draws=1, unknown=1)

    assert stats.decisive_games == 4
    assert (stats.white_wins / stats.decisive_games) == 0.5

def test_parse_result_mapping() -> None:
    """Sanity-check PGN result header normalization."""
    assert parse_result("1-0") == "white"
    assert parse_result("0-1") == "black"
    assert parse_result("1/2-1/2") == "draw"
    assert parse_result("*") == "unknown"
    assert parse_result("garbage") == "unknown"     

def test_lookup_position_found() -> None:
    games = load_games(SAMPLE_PGN)
    index = build_position_index(games)

    start_fen = chess.Board().fen()
    stats = lookup_position(start_fen, index)

    assert stats.total_games == 2
    assert stats.white_wins == 1


def test_save_and_load_handles_large_unsigned_hash_sqlite_store(tmp_path) -> None:
    db_path = str(tmp_path/ "test.db")
    store = SQLitePositionStatsStore(db_path)

    large_unsigned_hash = 2**63 + 12345

    index = {large_unsigned_hash: PositionStats(total_games=5, white_wins=2, black_wins=1, draws=2)}

    store.save(index)
    loaded = store.load()  
    store.close()

    assert large_unsigned_hash in loaded
    assert loaded[large_unsigned_hash].total_games == 5

@pytest.fixture
def mongo_store():
    mock_client = mongomock.MongoClient()
    store = MongoPositionStatsStore(connection_uri="mongodb://fake", client=mock_client)
    yield store
    store.close()

def test_save_and_load_handles_large_unsigned_hash_mongo_store(mongo_store) -> None:
    large_unsigned_hash = 2**63 + 12345
    index = {large_unsigned_hash: PositionStats(total_games=5, white_wins=2, black_wins=1, draws=2)}

    mongo_store.save(index)

    loaded = mongo_store.load()
    assert large_unsigned_hash in loaded
    assert loaded[large_unsigned_hash].total_games == 5

    result = mongo_store.query(large_unsigned_hash)
    assert result is not None
    assert result.total_games == 5


def test_mock_pgn_generates_expected_total_games(tmp_path) -> None:
    pgn_path = str(tmp_path / "mock.pgn")
    generate_mock_pgn(pgn_path)

    games = load_games(pgn_path)
    assert len(games) == 165  


def test_mock_pgn_position_stats_are_exact(tmp_path) -> None:
    pgn_path = str(tmp_path / "mock.pgn")
    generate_mock_pgn(pgn_path)

    games = load_games(pgn_path)
    index = build_position_index(games)

    board = chess.Board()
    for san in ["e4", "e5", "Nf3", "Nc6"]:
        board.push_san(san)
    position_hash = chess.polyglot.zobrist_hash(board)

    stats = index[position_hash]
    assert stats.total_games == 100
    assert stats.white_wins == 50
    assert stats.black_wins == 30
    assert stats.draws == 20
    assert stats.decisive_games == 100  


def test_mock_pgn_sicilian_unknown_result(tmp_path) -> None:
    pgn_path = str(tmp_path / "mock.pgn")
    generate_mock_pgn(pgn_path)

    games = load_games(pgn_path)
    index = build_position_index(games)

    board = chess.Board()
    for san in ["e4", "c5"]:
        board.push_san(san)
    position_hash = chess.polyglot.zobrist_hash(board)

    stats = index[position_hash]
    assert stats.total_games == 15
    assert stats.unknown == 15
    assert stats.decisive_games == 0  