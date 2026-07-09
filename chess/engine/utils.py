import logging
import threading
import concurrent
import asyncio
import inspect
import typing

from typing import TypeVar, Union, Mapping, TypeAlias, Iterable, Tuple, Callable, Optional, Coroutine, Any

if typing.TYPE_CHECKING:
    from .protocol import Protocol

T = TypeVar("T")
ProtocolT = TypeVar("ProtocolT", bound="Protocol")

ConfigValue: TypeAlias = Union[str, int, bool, None]
ConfigMapping: TypeAlias = Mapping[str, ConfigValue]

LOGGER = logging.getLogger(__name__)


MANAGED_OPTIONS = ["uci_chess960", "uci_variant", "multipv", "ponder"]

def _chain_config(a: ConfigMapping, b: ConfigMapping) -> Iterable[Tuple[str, ConfigValue]]:
    merged = dict(a)
    for k, v in b.items():
        merged.setdefault(k, v)
    if "Hash" in merged and "Threads" in merged:
        # Move Hash after Threads, as recommended by Stockfish.
        hash_val = merged["Hash"]
        del merged["Hash"]
        merged["Hash"] = hash_val
    return merged.items()

def _next_token(line: str) -> tuple[str, str]:
    """
    Get the next token in a whitespace-delimited line of text.

    The result is returned as a 2-part tuple of strings.

    If the input line is empty or all whitespace, then the result is two
    empty strings.

    If the input line is not empty and not completely whitespace, then
    the first element of the returned tuple is a single word with
    leading and trailing whitespace removed. The second element is the
    unchanged rest of the line.
    """
    parts = line.split(maxsplit=1)
    return parts[0] if parts else "", parts[1] if len(parts) == 2 else ""

def run_in_background(coroutine: Callable[[concurrent.futures.Future[T]], Coroutine[Any, Any, None]], *, name: Optional[str] = None, debug: Optional[bool] = None) -> T:
    """
    Runs ``coroutine(future)`` in a new event loop on a background thread.

    Blocks on *future* and returns the result as soon as it is resolved.
    The coroutine and all remaining tasks continue running in the background
    until complete.
    """
    assert inspect.iscoroutinefunction(coroutine)

    future: concurrent.futures.Future[T] = concurrent.futures.Future()

    def background() -> None:
        try:
            asyncio.run(coroutine(future), debug=debug)
            future.cancel()
        except Exception as exc:
            future.set_exception(exc)

    threading.Thread(target=background, name=name).start()
    return future.result()


