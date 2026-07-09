"""
Communicate with UCI and XBoard chess engines.

The engine code used to live in the single ``chess/engine.py`` module. It has
been split into cohesive submodules:

* :mod:`chess.engine.utils` -- background task runner, config types, helpers
* :mod:`chess.engine.error` -- engine exceptions
* :mod:`chess.engine.info` -- :class:`Limit`, :class:`InfoDict`, :class:`PlayResult`, :class:`Info`, :class:`Opponent`, :class:`Option`
* :mod:`chess.engine.wdl` -- :class:`WdlModel`, :class:`Wdl`, :class:`PovWdl`
* :mod:`chess.engine.score` -- :class:`Score`, :class:`Cp`, :class:`Mate`, :class:`PovScore`
* :mod:`chess.engine.analysis` -- :class:`BestMove`, :class:`AnalysisResult`
* :mod:`chess.engine.base_command` -- :class:`CommandState`, :class:`BaseCommand`
* :mod:`chess.engine.protocol` -- the abstract :class:`Protocol` base
* :mod:`chess.engine.uci` -- :class:`UciProtocol`
* :mod:`chess.engine.xboard` -- :class:`XBoardProtocol`
* :mod:`chess.engine.simple_engine` -- :class:`SimpleEngine`
* :mod:`chess.engine.mock` -- a test-only transport

Every public name is re-exported here, so ``chess.engine.<name>`` keeps working
exactly as before.
"""

from __future__ import annotations

import asyncio
from typing import List, Tuple, Any, Union

from .error import EngineError, EngineTerminatedError, AnalysisComplete
from .info import (
    Limit, InfoDict, PlayResult, Info, Opponent, Option,
    INFO_NONE, INFO_BASIC, INFO_SCORE, INFO_PV, INFO_REFUTATION, INFO_CURRLINE, INFO_ALL)
from .wdl import WdlModel, Wdl, PovWdl
from .score import Score, Cp, Mate, MateGivenType, MateGiven, PovScore
from .analysis import BestMove, AnalysisResult
from .protocol import Protocol
from .base_command import CommandState, BaseCommand
from .uci import UciProtocol, UciOptionMap, UCI_REGEX, _parse_uci_info, _parse_uci_bestmove
from .xboard import XBoardProtocol, XBOARD_ERROR_REGEX, _parse_xboard_option, _parse_xboard_post
from .simple_engine import SimpleEngine, SimpleAnalysisResult
from .utils import run_in_background, LOGGER, MANAGED_OPTIONS, ConfigValue, ConfigMapping, _next_token, _chain_config
from .mock import MockTransport as MockTransport


# Public API
__all__ = [
    "EngineError", "EngineTerminatedError", "AnalysisComplete",
    "Option",
    "Limit", "InfoDict", "PlayResult", "Info", "Opponent",
    "INFO_NONE", "INFO_BASIC", "INFO_SCORE", "INFO_PV", "INFO_REFUTATION", "INFO_CURRLINE", "INFO_ALL",
    "WdlModel", "Wdl", "PovWdl",
    "Score", "Cp", "Mate", "MateGivenType", "MateGiven", "PovScore",
    "BestMove", "AnalysisResult",
    "Protocol", "CommandState", "BaseCommand",
    "UciProtocol", "UciOptionMap", "UCI_REGEX",
    "XBoardProtocol", "XBOARD_ERROR_REGEX",
    "SimpleEngine", "SimpleAnalysisResult",
    "run_in_background", "LOGGER", "MANAGED_OPTIONS", "ConfigValue", "ConfigMapping", "popen_uci", "popen_xboard"
]

async def popen_uci(command: Union[str, List[str]], *, setpgrp: bool = False, **popen_args: Any) -> Tuple[asyncio.SubprocessTransport, UciProtocol]:
    """
    Spawns and initializes a UCI engine.

    :param command: Path of the engine executable, or a list including the
        path and arguments.
    :param setpgrp: Open the engine process in a new process group. This will
        stop signals (such as keyboard interrupts) from propagating from the
        parent process. Defaults to ``False``.
    :param popen_args: Additional arguments for
        `popen <https://docs.python.org/3/library/subprocess.html#popen-constructor>`_.
        Do not set ``stdin``, ``stdout``, ``bufsize`` or
        ``universal_newlines``.

    Returns a subprocess transport and engine protocol pair.
    """
    transport, protocol = await UciProtocol.popen(command, setpgrp=setpgrp, **popen_args)
    try:
        await protocol.initialize()
    except:
        transport.close()
        raise
    return transport, protocol


async def popen_xboard(command: Union[str, List[str]], *, setpgrp: bool = False, **popen_args: Any) -> Tuple[asyncio.SubprocessTransport, XBoardProtocol]:
    """
    Spawns and initializes an XBoard engine.

    :param command: Path of the engine executable, or a list including the
        path and arguments.
    :param setpgrp: Open the engine process in a new process group. This will
        stop signals (such as keyboard interrupts) from propagating from the
        parent process. Defaults to ``False``.
    :param popen_args: Additional arguments for
        `popen <https://docs.python.org/3/library/subprocess.html#popen-constructor>`_.
        Do not set ``stdin``, ``stdout``, ``bufsize`` or
        ``universal_newlines``.

    Returns a subprocess transport and engine protocol pair.
    """
    transport, protocol = await XBoardProtocol.popen(command, setpgrp=setpgrp, **popen_args)
    try:
        await protocol.initialize()
    except:
        transport.close()
        raise
    return transport, protocol