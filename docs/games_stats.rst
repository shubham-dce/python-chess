Game statistics
===============

``chess.games_stats`` aggregates game outcomes (win/loss/draw) by chess
position, so that callers can look up how a given position has historically
scored across a set of PGN games.

Loading games
-------------

.. autofunction:: chess.games_stats.load_games

.. autofunction:: chess.games_stats.iter_position_hashes

Building and querying a position index
---------------------------------------

.. autoclass:: chess.games_stats.PositionStats
    :members:

.. autofunction:: chess.games_stats.build_position_index

.. autofunction:: chess.games_stats.parse_result

.. autofunction:: chess.games_stats.lookup_position

.. autoclass:: chess.games_stats.InvalidPositionError

Persisting a position index
----------------------------

Position indexes can be persisted through a :class:`~chess.games_stats.PositionStatsStore`
implementation, so that they do not need to be rebuilt from PGN files on
every run.

.. autoclass:: chess.games_stats.PositionStatsStore
    :members:

.. autofunction:: chess.games_stats.unsigned_to_signed_64

.. autofunction:: chess.games_stats.signed_to_unsigned_64

.. autoclass:: chess.games_stats.SQLitePositionStatsStore
    :members:

.. autoclass:: chess.games_stats.MongoPositionStatsStore
    :members:

    .. note::
        Requires the optional ``pymongo`` dependency. It is only imported
        when :class:`~chess.games_stats.MongoPositionStatsStore` is first
        accessed, so ``chess.games_stats`` can be used without it installed.
