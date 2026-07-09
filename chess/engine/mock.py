import asyncio
import collections

from typing import Deque, Tuple, List, Optional
from .protocol import Protocol

class MockTransport(asyncio.SubprocessTransport, asyncio.WriteTransport):
    def __init__(self, protocol: Protocol) -> None:
        super().__init__()
        self.protocol = protocol
        self.expectations: Deque[Tuple[str, List[str]]] = collections.deque()
        self.expected_pings = 0
        self.stdin_buffer = bytearray()
        self.protocol.connection_made(self)

    def expect(self, expectation: str, responses: List[str] = []) -> None:
        self.expectations.append((expectation, responses))

    def expect_ping(self) -> None:
        self.expected_pings += 1

    def assert_done(self) -> None:
        assert not self.expectations, f"pending expectations: {self.expectations}"

    def get_pipe_transport(self, fd: int) -> Optional[asyncio.BaseTransport]:
        assert fd == 0, f"expected 0 for stdin, got {fd}"
        return self

    def write(self, data: bytes | bytearray | memoryview) -> None:
        self.stdin_buffer.extend(data)
        while b"\n" in self.stdin_buffer:
            line_bytes, self.stdin_buffer = self.stdin_buffer.split(b"\n", 1)
            line = line_bytes.decode("utf-8")

            if line.startswith("ping ") and self.expected_pings:
                self.expected_pings -= 1
                self.protocol.pipe_data_received(1, (line.replace("ping ", "pong ") + "\n").encode("utf-8"))
            else:
                assert self.expectations, f"unexpected: {line!r}"
                expectation, responses = self.expectations.popleft()
                assert expectation == line, f"expected {expectation}, got: {line}"
                if responses:
                    self.protocol.loop.call_soon(self.protocol.pipe_data_received, 1, "\n".join(responses + [""]).encode("utf-8"))

    def get_pid(self) -> int:
        return id(self)

    def get_returncode(self) -> Optional[int]:
        return None if self.expectations else 0