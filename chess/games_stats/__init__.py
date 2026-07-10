"""
Aggregates game outcomes (win/loss/draw) by chess position, so callers can
look up how a given position has historically scored across a set of PGN
games.
"""

from .loader import load_games
from .position_iter import iter_position_hashes
from .indexer import PositionStats, build_position_index, parse_result
from .lookup import lookup_position, InvalidPositionError
from .position_store import PositionStatsStore, unsigned_to_signed_64, signed_to_unsigned_64
from .sqlite_store import SQLitePositionStatsStore

__all__ = [
    "load_games",
    "iter_position_hashes",
    "PositionStats", "build_position_index", "parse_result",
    "lookup_position", "InvalidPositionError",
    "PositionStatsStore", "unsigned_to_signed_64", "signed_to_unsigned_64",
    "SQLitePositionStatsStore",
    "MongoPositionStatsStore",
]


def __getattr__(name: str):
    """Lazily imports :class:`MongoPositionStatsStore` so ``pymongo`` is only required when it's actually used."""
    if name == "MongoPositionStatsStore":
        from .mongodb_store import MongoPositionStatsStore
        return MongoPositionStatsStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")