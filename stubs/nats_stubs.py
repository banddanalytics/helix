"""Ground-truth nats-py API stub."""

from __future__ import annotations

STUB: dict[str, dict[str, set[str]]] = {
    "nats": {
        "connect": {"servers", "name", "pedantic", "verbose", "allow_reconnect",
                    "connect_timeout", "reconnect_time_wait", "max_reconnect_attempts",
                    "ping_interval", "max_outstanding_pings", "dont_randomize",
                    "flusher_queue_size", "no_echo", "tls", "tls_hostname",
                    "user", "password", "token", "drain_timeout", "signature_cb",
                    "user_jwt_cb", "user_credentials", "nkeys_seed", "inbox_prefix",
                    "pending_size", "flush_timeout", "error_cb", "disconnected_cb",
                    "closed_cb", "discovered_server_cb", "reconnected_cb"},
        "publish": {"subject", "payload", "reply", "headers"},
        "subscribe": {"subject", "queue", "cb", "future", "max_msgs", "pending_msgs_limit",
                      "pending_bytes_limit"},
        "unsubscribe": {"ssid", "limit"},
        "request": {"subject", "payload", "timeout", "old_style", "headers"},
        "drain": set(),
        "close": set(),
        "flush": {"timeout"},
        "jetstream": {"timeout", "domain", "prefix"},
        "find_server_by_url": {"url"},
        "add_stream": {"config"},
        "publish": {"subject", "payload", "timeout", "headers", "stream"},
        "subscribe": {"subject", "queue", "durable", "stream", "config",
                      "manual_ack", "ordered_consumer", "idle_heartbeat",
                      "flow_control", "pending_msgs_limit", "pending_bytes_limit",
                      "deliver_policy", "headers_only", "cb", "inactive_threshold"},
        "pull_subscribe": {"subject", "durable", "stream", "config",
                           "pending_msgs_limit", "pending_bytes_limit"},
        "fetch": {"batch", "timeout"},
        "ack": set(),
        "nak": {"delay"},
        "in_progress": set(),
        "term": set(),
    }
}
