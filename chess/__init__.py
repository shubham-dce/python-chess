"""
A chess library with move generation and validation,
Polyglot opening book probing, PGN reading and writing,
Gaviota tablebase probing,
Syzygy tablebase probing, and XBoard/UCI engine communication.
"""

__author__ = "Niklas Fiekas"

__email__ = "niklas.fiekas@backscattering.de"

__version__ = "1.11.2"

from ._core import *
from ._core import _BoardState, _sliding_attacks, _step_attacks, _edges, _carry_rippler, _attack_table, _rays




