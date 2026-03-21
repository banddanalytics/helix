"""Ground-truth pyzmq API stub."""

from __future__ import annotations

STUB: dict[str, dict[str, set[str]]] = {
    "zmq": {
        "Context": {"io_threads", "shadow"},
        "socket": {"socket_type"},
        "term": set(),
        "bind": {"addr"},
        "connect": {"addr"},
        "send": {"data", "flags", "copy", "track"},
        "recv": {"flags", "copy", "track"},
        "send_multipart": {"msg_parts", "flags", "copy", "track"},
        "recv_multipart": {"flags", "copy", "track"},
        "send_string": {"u", "encoding", "flags"},
        "recv_string": {"encoding", "flags"},
        "send_json": {"obj", "flags"},
        "recv_json": {"flags"},
        "setsockopt": {"option", "optval"},
        "getsockopt": {"option"},
        "close": {"linger"},
        "subscribe": {"topic"},
        "unsubscribe": {"topic"},
        "poll": {"timeout", "flags"},
        "Poller": set(),
        "register": {"socket", "flags"},
        "unregister": {"socket"},
        "device": {"device_type", "frontend", "backend"},
        "proxy": {"frontend", "backend", "capture"},
        "curve_keypair": set(),
    }
}
