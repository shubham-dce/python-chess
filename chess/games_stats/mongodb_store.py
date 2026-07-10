from typing import Dict, Optional
from pymongo import MongoClient
from pymongo.collection import Collection
from .indexer import PositionStats
from .position_store import PositionStatsStore, unsigned_to_signed_64, signed_to_unsigned_64

class MongoPositionStatsStore(PositionStatsStore):
    """:class:`PositionStatsStore` backed by a MongoDB collection."""

    def __init__(self, connection_uri: str, db_name: str = "games_stats", collection_name: str = "position_stats", client: Optional[MongoClient] = None) -> None:
        """
        Connects to *db_name*.*collection_name* at *connection_uri* (or reuses
        *client* if injected) and ensures a unique index on ``position_hash``.
        """
        self.client = client if client is not None else MongoClient(connection_uri)
        self.collection: Collection = self.client[db_name][collection_name]
        self.collection.create_index("position_hash", unique=True)

    def save(self, index: Dict[int, PositionStats]) -> None:
        """Upserts every entry of *index* into the collection, keyed by position hash."""
        for h, s in index.items():
            document = {
                "position_hash": unsigned_to_signed_64(h), 
                "total_games": s.total_games,
                "white_wins": s.white_wins,
                "black_wins": s.black_wins,
                "draws": s.draws,
                "unknown": s.unknown,
            }

            self.collection.replace_one({"position_hash" : document["position_hash"]}, document, upsert=True)

    def load(self) -> Dict[int, PositionStats]:
        """Loads and returns every document in the collection as a position index."""
        index: Dict[int, PositionStats] = {}
        for doc in self.collection.find():
            unsigned_hash = signed_to_unsigned_64(doc["position_hash"])
            index[unsigned_hash] = PositionStats(
                total_games=doc["total_games"],
                white_wins=doc["white_wins"],
                black_wins=doc["black_wins"],
                draws=doc["draws"],
                unknown=doc["unknown"],
            )
        return index

    def query(self, position_hash: int) -> Optional[PositionStats]:
        """Returns the stats document for *position_hash*, or ``None`` if it isn't stored."""
        signed_hash = unsigned_to_signed_64(position_hash)
        doc = self.collection.find_one({"position_hash" : signed_hash})
        if doc is None:
            return None
        return PositionStats(
            total_games=doc["total_games"],
            white_wins=doc["white_wins"],
            black_wins=doc["black_wins"],
            draws=doc["draws"],
            unknown=doc["unknown"],
        )

    def close(self) -> None:
        """Closes the underlying MongoDB client connection."""
        self.client.close()
        