import abc
from typing import Dict, Optional
from .indexer import PositionStats

class PositionStatsStore(abc.ABC):
    """
    Persistence interface for a position index (as produced by
    :func:`chess.games_stats.build_position_index`). Implementations back
    the store with a particular storage engine, e.g. SQLite or MongoDB.
    """

    @abc.abstractmethod
    def save(self, index: Dict[int, PositionStats]) -> None:
        """Persists *index*, replacing any existing entry for each position hash it contains."""
        raise NotImplementedError

    @abc.abstractmethod
    def load(self) -> Dict[int, PositionStats]:
        """Loads and returns the full position index from storage."""
        raise NotImplementedError

    @abc.abstractmethod
    def query(self, position_hash: int) -> Optional[PositionStats]:
        """Returns the stats for *position_hash*, or ``None`` if not stored."""
        raise NotImplementedError

    @abc.abstractmethod
    def close(self) -> None:
        """Releases any underlying storage connection/resources."""
        raise NotImplementedError

UINT64_MAX = 2**64
INT64_MAX = 2**63 - 1

def unsigned_to_signed_64(value: int) -> int:
    """
    Reinterprets unsigned 64-bit *value* (e.g. a Zobrist hash) as a signed
    64-bit integer, since some storage engines (e.g. SQLite) only support
    signed integer columns.
    """
    if value > INT64_MAX:
        return value - UINT64_MAX
    return value

def signed_to_unsigned_64(value: int) -> int:
    """Inverse of :func:`unsigned_to_signed_64`: recovers the original unsigned 64-bit value."""
    if value < 0:
        return value + UINT64_MAX
    return value