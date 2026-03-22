---
phase: 01-foundation
plan: "07"
subsystem: zmq-bridge
tags: [zeromq, msgpack, windows-publisher, linux-consumer, auto-reconnect, tdd]
dependency_graph:
  requires: ["01-04"]
  provides: ["WindowsPublisher", "LinuxConsumer", "message_schemas"]
  affects: ["alpha-engines", "live-trading-pipeline"]
tech_stack:
  added: ["zmq", "msgpack"]
  patterns:
    - "ZMQ PUB/SUB with symbol topic prefix for filtering"
    - "ZMQ PUSH/PULL for order request/result cycle"
    - "MessagePack for compact binary serialization"
    - "Exponential backoff reconnect (1s→2s→4s→…→30s max)"
    - "Stale detection via monotonic time since last heartbeat"
    - "All socket tests use MagicMock/AsyncMock — no real connections"
key_files:
  created:
    - src/execution/bridge/message_schemas.py
    - src/execution/bridge/windows_publisher.py
    - src/execution/bridge/linux_consumer.py
    - tests/execution/bridge/test_bridge.py
  modified:
    - src/execution/bridge/__init__.py
    - tests/execution/bridge/__init__.py
decisions:
  - "np.datetime64 serialized as int64 nanoseconds since epoch for full precision preservation"
  - "Tick topic prefix: symbol bytes prepended to packed payload for ZMQ SUB filtering"
  - "Live E2E testing deferred to go-live hardware — Phase 1 unit tests only (D-32)"
  - "Default LinuxConsumer host: 10.200.0.1 (WireGuard interface)"
  - "Heartbeat interval 5s, stale threshold 10s (D-35)"
  - "Max reconnect backoff 30s via RECONNECT_DELAYS list"
metrics:
  duration_minutes: 25
  completed_date: "2026-03-22"
  tasks_completed: 2
  files_created: 4
  files_modified: 2
---

# Phase 01 Plan 07: ZeroMQ Bridge Summary

**One-liner:** MessagePack round-trip serialization for all execution dataclasses; WindowsPublisher binds 4 ZMQ sockets (PUB×2, PULL, PUSH); LinuxConsumer connects with symbol subscription and exponential backoff auto-reconnect.

## What Was Built

Three bridge components implementing EXEC-07:

1. **`src/execution/bridge/message_schemas.py`** — Pack/unpack functions for Tick, Bar, OrderRequest, OrderResult, and heartbeat. `np.datetime64` converted to/from int64 nanoseconds. Enum values serialized as primitives. All optional fields handled. Round-trip fidelity verified in tests.

2. **`src/execution/bridge/windows_publisher.py`** — `WindowsPublisher` binds ZMQ PUB on port 5556 (ticks) and 5557 (bars), PULL on 5558 (order requests), PUSH on 5559 (order results). `publish_tick` sends multipart `[symbol_bytes, packed_data]` for topic filtering. Heartbeat loop fires every 5 seconds. Async order handler loop processes incoming requests.

3. **`src/execution/bridge/linux_consumer.py`** — `LinuxConsumer` connects to `tcp://host:555x`. `subscribe(symbol)` sets ZMQ SUB topic filter. `_receive_loop` dispatches to `on_tick`/`on_bar` callbacks. `is_stale` property checks `monotonic() - last_heartbeat > 10.0`. `_reconnect` walks `RECONNECT_DELAYS = [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]` with exponential backoff capped at 30s.

## Commits

| Hash | Message |
|------|---------|
| 5131dcb | test(01-07): add failing tests for ZMQ bridge schemas and socket classes |
| ecd8aed | feat(01-07): implement MessagePack schemas for bridge serialization |
| 4e6a87f | feat(01-07): implement WindowsPublisher, LinuxConsumer with auto-reconnect; fix zmq import in tests |

## Test Results

- 38 bridge tests — all pass
- message_schemas.py: 100% coverage
- windows_publisher.py: 81% branch coverage
- linux_consumer.py: 79% branch coverage (async reconnect paths require live ZMQ — deferred to go-live)
- `mypy src/execution/bridge/ --strict` — clean

## Verification

```
38 bridge tests pass with fully mocked ZMQ sockets
pack_tick/unpack_tick round-trip: confirmed all fields preserved
WindowsPublisher ports 5556/5557/5558/5559: confirmed
LinuxConsumer STALE_THRESHOLD=10.0, RECONNECT_DELAYS max=30.0: confirmed
Default host 10.200.0.1: confirmed
```

## Deviations from Plan

- Added `import zmq` to test file (missing from initial skeleton, caused NameError in receive_loop test)

## Self-Check: PASSED

- src/execution/bridge/message_schemas.py: FOUND
- src/execution/bridge/windows_publisher.py: FOUND
- src/execution/bridge/linux_consumer.py: FOUND
- tests/execution/bridge/test_bridge.py: FOUND
- Commit 5131dcb: FOUND
- Commit ecd8aed: FOUND
- Commit 4e6a87f: FOUND
