import sqlite3
from typing import Dict, Optional
from .indexer import PositionStats
from .position_store import PositionStatsStore, unsigned_to_signed_64, signed_to_unsigned_64


class SQLitePositionStatsStore(PositionStatsStore):
    """:class:`PositionStatsStore` backed by a SQLite database file."""

    def __init__(self, db_path: str) -> None:
        """Opens (creating if necessary) the SQLite database at *db_path* and ensures its schema exists."""
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self) -> None:
        """Creates the ``position_stats`` table if it does not already exist."""
        self.conn.execute(
            """
                CREATE TABLE IF NOT EXISTS position_stats (
                position_hash INTEGER PRIMARY KEY, 
                total_games INTEGER NOT NULL,
                white_wins INTEGER NOT NULL,
                black_wins INTEGER NOT NULL,
                draws INTEGER NOT NULL,
                unknown INTEGER NOT NULL
            )
            """
        )

        self.conn.commit()

    def save(self, index: Dict[int, PositionStats]) -> None:
        """Upserts every entry of *index* into the ``position_stats`` table, keyed by position hash."""
        rows = [
            (unsigned_to_signed_64(h), s.total_games, s.white_wins, s.black_wins, s.draws, s.unknown) for h, s in index.items()
        ]

        self.conn.executemany("""
            INSERT OR REPLACE INTO position_stats
            (position_hash, total_games, white_wins, black_wins, draws, unknown)
            VALUES (?, ?, ?, ?, ?, ?)
        """, rows)

        self.conn.commit()

    def load(self) -> Dict[int, PositionStats]:
        """Loads and returns every row of ``position_stats`` as a position index."""
        cursor = self.conn.execute("SELECT * FROM position_stats")
        index: Dict[int, PositionStats] = {}
        for h, total, w, b, d, u in cursor.fetchall():
            unsigned_hash = signed_to_unsigned_64(h)
            index[unsigned_hash] = PositionStats(total_games=total, white_wins=w, black_wins=b, draws=d, unknown=u)

        return index

    def query(self, position_hash: int) -> Optional[PositionStats]:
        """Returns the stats row for *position_hash*, or ``None`` if it isn't stored."""
        signed_hash = unsigned_to_signed_64(position_hash)
        cursor = self.conn.execute(
            "SELECT total_games, white_wins, black_wins, draws, unknown FROM position_stats WHERE position_hash = ?", (signed_hash,)
        )

        row = cursor.fetchone()

        if row is None:
            return None
        total, w, b, d, u = row
        return PositionStats(total_games=total, white_wins=w, black_wins=b, draws=d, unknown=u)

    def close(self) -> None:
        """Closes the underlying SQLite connection."""
        self.conn.close()