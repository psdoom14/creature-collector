"""Message connections between two copies of the game.

    Connection (abstract)       send(dict), poll() -> [dict], close()
    ├── SocketConnection        a TCP socket on the local network; a background thread
    │                           reads one JSON message per line into a queue
    └── MemoryConnection        two linked in-process queues, for tests

``LinkListener`` (host) and ``LinkJoiner`` (guest) open a SocketConnection in the
background so the game window never freezes while waiting.
"""
import json
import logging
import queue
import socket
import threading
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_PORT = 50505
CONNECT_TIMEOUT = 5.0


class ConnectionLost(Exception):
    """The other player disconnected."""


class Connection(ABC):
    """A two-way pipe for JSON-able dict messages."""

    @abstractmethod
    def send(self, message: dict) -> None:
        """Send one message. Raises ConnectionLost if the other side is gone."""

    @abstractmethod
    def poll(self) -> List[dict]:
        """All messages received since the last poll (never blocks)."""

    @property
    @abstractmethod
    def closed(self) -> bool:
        """True once either side has closed the connection."""

    @abstractmethod
    def close(self) -> None:
        """Close the connection (safe to call more than once)."""


class MemoryConnection(Connection):
    """In-process connection for tests: ``a, b = MemoryConnection.pair()``."""

    def __init__(self, inbox: "queue.Queue", outbox: "queue.Queue", state: dict):
        self._inbox = inbox
        self._outbox = outbox
        self._state = state

    @classmethod
    def pair(cls) -> Tuple["MemoryConnection", "MemoryConnection"]:
        q1, q2, state = queue.Queue(), queue.Queue(), {"closed": False}
        return cls(q1, q2, state), cls(q2, q1, state)

    def send(self, message: dict) -> None:
        if self._state["closed"]:
            raise ConnectionLost("The other player disconnected")
        self._outbox.put(json.loads(json.dumps(message)))   # same JSON round trip as the wire

    def poll(self) -> List[dict]:
        out = []
        while not self._inbox.empty():
            out.append(self._inbox.get_nowait())
        return out

    @property
    def closed(self) -> bool:
        return self._state["closed"]

    def close(self) -> None:
        self._state["closed"] = True


class SocketConnection(Connection):
    """A TCP connection carrying one JSON object per line."""

    def __init__(self, sock: socket.socket):
        self._sock = sock
        self._sock.settimeout(None)
        self._inbox: "queue.Queue[dict]" = queue.Queue()
        self._closed = threading.Event()
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        buffer = b""
        try:
            while not self._closed.is_set():
                chunk = self._sock.recv(65536)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.strip():
                        try:
                            self._inbox.put(json.loads(line.decode("utf-8")))
                        except (ValueError, UnicodeDecodeError) as e:
                            logger.warning("Ignoring a malformed link message: %s", e)
        except OSError:
            pass
        finally:
            self._closed.set()

    def send(self, message: dict) -> None:
        if self._closed.is_set():
            raise ConnectionLost("The other player disconnected")
        data = (json.dumps(message) + "\n").encode("utf-8")
        try:
            with self._lock:
                self._sock.sendall(data)
        except OSError as e:
            self._closed.set()
            raise ConnectionLost("The other player disconnected") from e

    def poll(self) -> List[dict]:
        out = []
        while not self._inbox.empty():
            out.append(self._inbox.get_nowait())
        return out

    @property
    def closed(self) -> bool:
        return self._closed.is_set() and self._inbox.empty()

    def close(self) -> None:
        self._closed.set()
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._sock.close()


class LinkListener:
    """Host side: listens on ``port`` and hands over the first player who connects."""

    def __init__(self, port: int = DEFAULT_PORT, host: str = "0.0.0.0"):
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((host, port))
        self._server.listen(1)
        self.port = self._server.getsockname()[1]
        self._result: "queue.Queue" = queue.Queue()
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        try:
            sock, _addr = self._server.accept()
            self._result.put(SocketConnection(sock))
        except OSError:
            pass

    def poll(self) -> Optional[SocketConnection]:
        """The connection once someone has joined, else None."""
        try:
            return self._result.get_nowait()
        except queue.Empty:
            return None

    def close(self) -> None:
        try:
            self._server.close()
        except OSError:
            pass


class LinkJoiner:
    """Guest side: connects to ``address:port`` in the background."""

    def __init__(self, address: str, port: int = DEFAULT_PORT, timeout: float = CONNECT_TIMEOUT):
        self._result: "queue.Queue" = queue.Queue()
        threading.Thread(target=self._connect, args=(address, port, timeout), daemon=True).start()

    def _connect(self, address: str, port: int, timeout: float) -> None:
        try:
            sock = socket.create_connection((address, port), timeout=timeout)
            self._result.put(SocketConnection(sock))
        except OSError as e:
            self._result.put(e)

    def poll(self) -> Optional[SocketConnection]:
        """The connection once made; raises ConnectionLost if it failed; None while trying."""
        try:
            result = self._result.get_nowait()
        except queue.Empty:
            return None
        if isinstance(result, Exception):
            raise ConnectionLost(f"Could not connect: {result}") from result
        return result


def local_ip_address() -> str:
    """This computer's address on the local network (what the friend types in).

    Uses the routing table only: connecting a UDP socket sends no packets.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
