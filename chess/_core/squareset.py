from __future__ import annotations

from .bitboard import *
from .squares import *
from .constants import *
from .attacks import ray, between, _carry_rippler

from typing import TypeAlias, SupportsInt, Iterable, Union

IntoSquareSet: TypeAlias = Union[SupportsInt, Iterable[Square]]

class SquareSet:
    """
    A set of squares.

    >>> import chess
    >>>
    >>> squares = chess.SquareSet([chess.A8, chess.A1])
    >>> squares
    SquareSet(0x0100_0000_0000_0001)

    >>> squares = chess.SquareSet(chess.BB_A8 | chess.BB_RANK_1)
    >>> squares
    SquareSet(0x0100_0000_0000_00ff)

    >>> print(squares)
    1 . . . . . . .
    . . . . . . . .
    . . . . . . . .
    . . . . . . . .
    . . . . . . . .
    . . . . . . . .
    . . . . . . . .
    1 1 1 1 1 1 1 1

    >>> len(squares)
    9

    >>> bool(squares)
    True

    >>> chess.B1 in squares
    True

    >>> for square in squares:
    ...     # 0 -- chess.A1
    ...     # 1 -- chess.B1
    ...     # 2 -- chess.C1
    ...     # 3 -- chess.D1
    ...     # 4 -- chess.E1
    ...     # 5 -- chess.F1
    ...     # 6 -- chess.G1
    ...     # 7 -- chess.H1
    ...     # 56 -- chess.A8
    ...     print(square)
    ...
    0
    1
    2
    3
    4
    5
    6
    7
    56

    >>> list(squares)
    [0, 1, 2, 3, 4, 5, 6, 7, 56]

    Square sets are internally represented by 64-bit integer masks of the
    included squares. Bitwise operations can be used to compute unions,
    intersections and shifts.

    >>> int(squares)
    72057594037928191

    Also supports common set operations like
    :func:`~chess.SquareSet.issubset()`, :func:`~chess.SquareSet.issuperset()`,
    :func:`~chess.SquareSet.union()`, :func:`~chess.SquareSet.intersection()`,
    :func:`~chess.SquareSet.difference()`,
    :func:`~chess.SquareSet.symmetric_difference()` and
    :func:`~chess.SquareSet.copy()` as well as
    :func:`~chess.SquareSet.update()`,
    :func:`~chess.SquareSet.intersection_update()`,
    :func:`~chess.SquareSet.difference_update()`,
    :func:`~chess.SquareSet.symmetric_difference_update()` and
    :func:`~chess.SquareSet.clear()`.
    """

    def __init__(self, squares: IntoSquareSet = BB_EMPTY) -> None:
        try:
            self.mask: Bitboard = squares.__int__() & BB_ALL  # type: ignore
            return
        except AttributeError:
            self.mask = 0

        # Try squares as an iterable. Not under except clause for nicer
        # backtraces.
        for square in squares:  # type: ignore
            self.add(square)

    # Set

    def __contains__(self, square: Square) -> bool:
        return bool(BB_SQUARES[square] & self.mask)

    def __iter__(self) -> Iterator[Square]:
        return scan_forward(self.mask)

    def __reversed__(self) -> Iterator[Square]:
        return scan_reversed(self.mask)

    def __len__(self) -> int:
        return popcount(self.mask)

    # MutableSet

    def add(self, square: Square) -> None:
        """Adds a square to the set."""
        self.mask |= BB_SQUARES[square]

    def discard(self, square: Square) -> None:
        """Discards a square from the set."""
        self.mask &= ~BB_SQUARES[square]

    # frozenset

    def isdisjoint(self, other: IntoSquareSet) -> bool:
        """Tests if the square sets are disjoint."""
        return not bool(self & other)

    def issubset(self, other: IntoSquareSet) -> bool:
        """Tests if this square set is a subset of another."""
        return not bool(self & ~SquareSet(other))

    def issuperset(self, other: IntoSquareSet) -> bool:
        """Tests if this square set is a superset of another."""
        return not bool(~self & other)

    def union(self, other: IntoSquareSet) -> SquareSet:
        return self | other

    def __or__(self, other: IntoSquareSet) -> SquareSet:
        r = SquareSet(other)
        r.mask |= self.mask
        return r

    def intersection(self, other: IntoSquareSet) -> SquareSet:
        return self & other

    def __and__(self, other: IntoSquareSet) -> SquareSet:
        r = SquareSet(other)
        r.mask &= self.mask
        return r

    def difference(self, other: IntoSquareSet) -> SquareSet:
        return self - other

    def __sub__(self, other: IntoSquareSet) -> SquareSet:
        r = SquareSet(other)
        r.mask = self.mask & ~r.mask
        return r

    def symmetric_difference(self, other: IntoSquareSet) -> SquareSet:
        return self ^ other

    def __xor__(self, other: IntoSquareSet) -> SquareSet:
        r = SquareSet(other)
        r.mask ^= self.mask
        return r

    def copy(self) -> SquareSet:
        return SquareSet(self.mask)

    # set

    def update(self, *others: IntoSquareSet) -> None:
        for other in others:
            self |= other

    def __ior__(self, other: IntoSquareSet) -> SquareSet:
        self.mask |= SquareSet(other).mask
        return self

    def intersection_update(self, *others: IntoSquareSet) -> None:
        for other in others:
            self &= other

    def __iand__(self, other: IntoSquareSet) -> SquareSet:
        self.mask &= SquareSet(other).mask
        return self

    def difference_update(self, other: IntoSquareSet) -> None:
        self -= other

    def __isub__(self, other: IntoSquareSet) -> SquareSet:
        self.mask &= ~SquareSet(other).mask
        return self

    def symmetric_difference_update(self, other: IntoSquareSet) -> None:
        self ^= other

    def __ixor__(self, other: IntoSquareSet) -> SquareSet:
        self.mask ^= SquareSet(other).mask
        return self

    def remove(self, square: Square) -> None:
        """
        Removes a square from the set.

        :raises: :exc:`KeyError` if the given *square* was not in the set.
        """
        mask = BB_SQUARES[square]
        if self.mask & mask:
            self.mask ^= mask
        else:
            raise KeyError(square)

    def pop(self) -> Square:
        """
        Removes and returns a square from the set.

        :raises: :exc:`KeyError` if the set is empty.
        """
        if not self.mask:
            raise KeyError("pop from empty SquareSet")

        square = lsb(self.mask)
        self.mask &= (self.mask - 1)
        return square

    def clear(self) -> None:
        """Removes all elements from this set."""
        self.mask = BB_EMPTY

    # SquareSet

    def carry_rippler(self) -> Iterator[Bitboard]:
        """Iterator over the subsets of this set."""
        return _carry_rippler(self.mask)

    def mirror(self) -> SquareSet:
        """Returns a vertically mirrored copy of this square set."""
        return SquareSet(flip_vertical(self.mask))

    def tolist(self) -> List[bool]:
        """Converts the set to a list of 64 bools."""
        result = [False] * 64
        for square in self:
            result[square] = True
        return result

    def __bool__(self) -> bool:
        return bool(self.mask)

    def __eq__(self, other: object) -> bool:
        try:
            return self.mask == SquareSet(other).mask  # type: ignore
        except (TypeError, ValueError):
            return NotImplemented

    def __lshift__(self, shift: int) -> SquareSet:
        return SquareSet((self.mask << shift) & BB_ALL)

    def __rshift__(self, shift: int) -> SquareSet:
        return SquareSet(self.mask >> shift)

    def __ilshift__(self, shift: int) -> SquareSet:
        self.mask = (self.mask << shift) & BB_ALL
        return self

    def __irshift__(self, shift: int) -> SquareSet:
        self.mask >>= shift
        return self

    def __invert__(self) -> SquareSet:
        return SquareSet(~self.mask & BB_ALL)

    def __int__(self) -> int:
        return self.mask

    def __index__(self) -> int:
        return self.mask

    def __repr__(self) -> str:
        return f"SquareSet({self.mask:#021_x})"

    def __str__(self) -> str:
        builder: List[str] = []

        for square in SQUARES_180:
            mask = BB_SQUARES[square]
            builder.append("1" if self.mask & mask else ".")

            if not mask & BB_FILE_H:
                builder.append(" ")
            elif square != H1:
                builder.append("\n")

        return "".join(builder)

    def _repr_svg_(self) -> str:
        import chess.svg
        return chess.svg.board(squares=self, size=390)

    @classmethod
    def ray(cls, a: Square, b: Square) -> SquareSet:
        """
        All squares on the rank, file or diagonal with the two squares, if they
        are aligned.

        >>> import chess
        >>>
        >>> print(chess.SquareSet.ray(chess.E2, chess.B5))
        . . . . . . . .
        . . . . . . . .
        1 . . . . . . .
        . 1 . . . . . .
        . . 1 . . . . .
        . . . 1 . . . .
        . . . . 1 . . .
        . . . . . 1 . .
        """
        return cls(ray(a, b))

    @classmethod
    def between(cls, a: Square, b: Square) -> SquareSet:
        """
        All squares on the rank, file or diagonal between the two squares
        (bounds not included), if they are aligned.

        >>> import chess
        >>>
        >>> print(chess.SquareSet.between(chess.E2, chess.B5))
        . . . . . . . .
        . . . . . . . .
        . . . . . . . .
        . . . . . . . .
        . . 1 . . . . .
        . . . 1 . . . .
        . . . . . . . .
        . . . . . . . .
        """
        return cls(between(a, b))

    @classmethod
    def from_square(cls, square: Square) -> SquareSet:
        """
        Creates a :class:`~chess.SquareSet` from a single square.

        >>> import chess
        >>>
        >>> chess.SquareSet.from_square(chess.A1) == chess.BB_A1
        True
        """
        return cls(BB_SQUARES[square])