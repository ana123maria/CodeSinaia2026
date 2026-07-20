# -*- coding: utf-8 -*-
"""
Networking + crypto layer
"""

import base64
import hashlib
import json
import os
import socket
import sys
import threading

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 3000
RECV_CHUNK_SIZE = 4096
MAX_IMAGE_BYTES = 2 * 1024 * 1024
CHAT_SECRET = os.environ.get("CHAT_SECRET", "my-own-whatsapp-dev-secret").encode("utf-8")


def _build_keystream(nonce: bytes, length: int) -> bytes:
    stream = bytearray()
    counter = 0
    while len(stream) < length:
        block = hashlib.sha256(CHAT_SECRET + nonce + counter.to_bytes(4, "big")).digest()
        stream.extend(block)
        counter += 1
    return bytes(stream[:length])


def encrypt_text(plain_text: str) -> str:
    plain_bytes = plain_text.encode("utf-8")
    nonce = os.urandom(16)
    stream = _build_keystream(nonce, len(plain_bytes))
    cipher_bytes = bytes(a ^ b for a, b in zip(plain_bytes, stream))
    return base64.b64encode(nonce + cipher_bytes).decode("utf-8")


def decrypt_text(cipher_text: str) -> str:
    payload = base64.b64decode(cipher_text.encode("utf-8"))
    nonce = payload[:16]
    cipher_bytes = payload[16:]
    stream = _build_keystream(nonce, len(cipher_bytes))
    plain_bytes = bytes(a ^ b for a, b in zip(cipher_bytes, stream))
    return plain_bytes.decode("utf-8", errors="replace")


class ChatClient:
    """Thin wrapper around the raw socket so main.py never touches it directly."""

    def __init__(self, host: str = SERVER_HOST, port: int = SERVER_PORT):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.send_lock = threading.Lock()
        self.stop_event = threading.Event()
        self._buffer = b""
        self._connected = False

    def connect(self) -> None:
        if self._connected:
            return
        try:
            self.socket.connect((self.host, self.port))
        except OSError as exc:
            print(f"Could not connect to server: {exc}")
            sys.exit(1)
        self._connected = True
        print("Connected to socket!")

    def send_packet(self, packet: dict) -> None:
        wire = (json.dumps(packet, separators=(",", ":")) + "\n").encode("utf-8")
        with self.send_lock:
            self.socket.sendall(wire)

    def recv_packet_blocking(self, timeout_seconds: float = None):
        previous_timeout = self.socket.gettimeout()
        self.socket.settimeout(timeout_seconds)
        try:
            while b"\n" not in self._buffer:
                chunk = self.socket.recv(RECV_CHUNK_SIZE)
                if not chunk:
                    return None
                self._buffer += chunk

            raw_line, self._buffer = self._buffer.split(b"\n", 1)
            if not raw_line:
                return {}
            return json.loads(raw_line.decode("utf-8"))
        finally:
            self.socket.settimeout(previous_timeout)

    def start_recv_loop(self, on_packet, on_disconnect=None) -> threading.Thread:
        def _loop():
            while not self.stop_event.is_set():
                try:
                    chunk = self.socket.recv(RECV_CHUNK_SIZE)
                    if not chunk:
                        break
                    self._buffer += chunk

                    while b"\n" in self._buffer:
                        raw_line, self._buffer = self._buffer.split(b"\n", 1)
                        if not raw_line:
                            continue
                        try:
                            packet = json.loads(raw_line.decode("utf-8"))
                        except json.JSONDecodeError:
                            continue
                        on_packet(packet)
                except OSError:
                    break
                except Exception as exc:
                    print(f"Receive loop error: {exc}")
                    break

            if not self.stop_event.is_set() and on_disconnect is not None:
                on_disconnect()

        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()
        return thread

    def close(self) -> None:
        self.stop_event.set()
        try:
            self.send_packet({"type": "CLOSE"})
        except Exception:
            pass
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        self.socket.close()