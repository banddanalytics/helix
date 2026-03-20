---
name: zeromq-nats-react-ui
description: >
  Implement the backend IPC layer using ZeroMQ for order routing and NATS for telemetry,
  plus the React Webpack 5 Module Federation dashboard for the Nairobi command center.
  Covers ZeroMQ socket patterns (PUSH/PULL for orders, PUB/SUB for market data fan-out),
  NATS JetStream for durable telemetry pub/sub, CPU core affinity for execution threads,
  React Module Federation configuration for isolated strategy dashboards as remote apps,
  Webpack 5 federation boundaries, and WebSocket bridges for real-time dashboard updates.
  Use this skill whenever working on: inter-process communication, ZeroMQ patterns, NATS
  messaging, order routing, telemetry pipelines, React dashboard architecture, Module
  Federation setup, micro-frontend design, CPU pinning, or any task involving the IPC or
  frontend layers. Also trigger when the user mentions "ZeroMQ", "NATS", "IPC", "order
  routing", "Module Federation", "micro-frontend", "CPU affinity", "core pinning",
  "telemetry", "pub/sub", or "dashboard".
---

# ZeroMQ/NATS IPC & React Module Federation Skill

## Purpose

This skill defines two interconnected subsystems:
1. **Backend IPC**: ZeroMQ for ultra-low-latency order routing between co-located processes,
   NATS JetStream for reliable telemetry delivery to Nairobi
2. **Frontend UI**: React-based dashboard using Webpack 5 Module Federation for
   modular strategy monitoring from the Nairobi command center

## Part 1: Backend IPC Architecture

### ZeroMQ Socket Topology

ZeroMQ is used ONLY for co-located IPC at NY4/LD4 where nanosecond latency matters.
It is brokerless — no intermediary server, no serialization overhead for local communication.

```
[NY4 Process Map]

┌─────────────────┐     PUSH/PULL (orders)     ┌──────────────────┐
│ Signal Engine    │ ─────────────────────────► │ Order Router     │
│ (cores 4-7)     │     ipc:///tmp/orders.sock  │ (core 8)         │
└─────────────────┘                             └──────┬───────────┘
                                                       │
┌─────────────────┐     PUB/SUB (mkt data)      ┌──────▼───────────┐
│ FIX Parser      │ ─────────────────────────► │ Strategy Engines  │
│ (core 9)        │     ipc:///tmp/mdata.sock   │ (cores 10-15)    │
└─────────────────┘                             └──────────────────┘
        │
        └──► PUB/SUB (raw ticks)  ────────────► [ArcticDB Writer (core 16)]
             ipc:///tmp/ticks.sock
```

### ZeroMQ Socket Configuration

```python
import zmq

class OrderRouter:
    """
    PULL socket: receives order requests from signal engines.
    Uses IPC transport (Unix domain sockets) for zero-copy local delivery.
    """
    def __init__(self):
        self.ctx = zmq.Context()
        
        # Order intake: PULL from signal engines
        self.order_pull = self.ctx.socket(zmq.PULL)
        self.order_pull.bind("ipc:///tmp/orders.sock")
        self.order_pull.setsockopt(zmq.RCVHWM, 10000)  # High water mark
        self.order_pull.setsockopt(zmq.RCVTIMEO, 0)     # Non-blocking
        
        # Market data fan-out: SUB from FIX parser
        self.mdata_sub = self.ctx.socket(zmq.SUB)
        self.mdata_sub.connect("ipc:///tmp/mdata.sock")
        self.mdata_sub.setsockopt_string(zmq.SUBSCRIBE, "")  # All messages
        
        # Order confirmation: PUB back to signal engines
        self.confirm_pub = self.ctx.socket(zmq.PUB)
        self.confirm_pub.bind("ipc:///tmp/confirms.sock")

class MarketDataPublisher:
    """
    PUB socket: FIX parser publishes decoded market data to all subscribers.
    Uses zero-copy for large tick batches.
    """
    def __init__(self):
        self.ctx = zmq.Context()
        self.pub = self.ctx.socket(zmq.PUB)
        self.pub.bind("ipc:///tmp/mdata.sock")
        self.pub.setsockopt(zmq.SNDHWM, 100000)  # Large buffer for bursts
        self.pub.setsockopt(zmq.LINGER, 0)        # Don't block on close
    
    def publish_tick(self, symbol: bytes, data: bytes):
        """Publish with topic prefix for selective subscription."""
        self.pub.send_multipart([symbol, data])
```

### Message Serialization

For ZeroMQ IPC (local only), use raw struct packing — no protobuf/JSON overhead:

```python
import struct

# Order message: 37 bytes fixed-size
ORDER_FMT = '!BQdiBQ'  # side(1), symbol_id(8), price(8), qty(4), side(1), order_type(1), timestamp(8)

def pack_order(side: int, symbol_id: int, price: float, qty: int, 
               order_type: int, timestamp: int) -> bytes:
    return struct.pack(ORDER_FMT, side, symbol_id, price, qty, side, order_type, timestamp)

def unpack_order(data: bytes) -> tuple:
    return struct.unpack(ORDER_FMT, data)
```

### CPU Core Affinity

Each critical process is pinned to a specific CPU core to eliminate context-switch jitter:

```python
import os

def pin_to_core(core_id: int):
    """Pin current process to a specific CPU core."""
    os.sched_setaffinity(0, {core_id})

# In Rust (for the FIX parser):
# use core_affinity;
# let core_ids = core_affinity::get_core_ids().unwrap();
# core_affinity::set_for_current(core_ids[9]);  // FIX parser on core 9

CORE_MAP = {
    'os_kernel':      [0, 1, 2, 3],   # System processes
    'signal_engine':  [4, 5, 6, 7],   # Alpha signal computation
    'order_router':   [8],             # Order routing (single-threaded)
    'fix_parser':     [9],             # FIX/MDP message parsing
    'strategy_1':     [10, 11],        # Cointegration engine
    'strategy_2':     [12, 13],        # ML Momentum engine
    'strategy_3':     [14, 15],        # Carry engine
    'arcticdb_writer': [16, 17],       # Tick storage
    'nats_bridge':    [18, 19],        # NATS telemetry relay
    'monitoring':     [20, 21, 22, 23] # Prometheus, logging, diagnostics
}
```

### NATS JetStream (Telemetry)

NATS is used exclusively for telemetry — delivering monitoring data from NY4/LD4 to Nairobi.
JetStream provides durability (survives Nairobi disconnections).

```
NATS Subject Hierarchy:
  telemetry.{site}.pnl           → Real-time PnL snapshots (100ms)
  telemetry.{site}.positions     → Current position inventory (1s)
  telemetry.{site}.risk          → CVaR, drawdown, circuit breaker status (1s)
  telemetry.{site}.regime        → HMM regime state probabilities (5s)
  telemetry.{site}.orders        → Order events (fills, rejects, cancels)
  telemetry.{site}.latency       → Tick-to-trade latency histogram (10s)
  telemetry.{site}.system        → CPU, memory, NIC stats (30s)

JetStream Configuration:
  - Stream: TELEMETRY
  - Retention: WorkQueue (once consumed by Nairobi, delete)
  - Max age: 24h (if Nairobi disconnected, buffer up to 24h)
  - Max bytes: 10GB per stream
  - Replicas: 1 (single node per site, not clustered)
  - Consumer: NAIROBI_DASHBOARD (durable, pull-based)
```

```python
import nats
from nats.js.api import StreamConfig, ConsumerConfig

async def setup_nats_telemetry(nc):
    js = nc.jetstream()
    
    # Create stream
    await js.add_stream(StreamConfig(
        name="TELEMETRY",
        subjects=["telemetry.>"],
        retention="workqueue",
        max_age=86400_000_000_000,  # 24h in nanoseconds
        max_bytes=10 * 1024**3,     # 10GB
    ))
    
    # Create durable consumer for Nairobi
    await js.add_consumer("TELEMETRY", ConsumerConfig(
        durable_name="NAIROBI_DASHBOARD",
        deliver_policy="all",
        ack_policy="explicit",
        max_deliver=3,  # Retry 3 times on ack timeout
    ))
```

---

## Part 2: React Module Federation Dashboard

### Architecture Overview

The Nairobi dashboard uses Webpack 5 Module Federation to load strategy-specific
dashboards as independent remote applications. This allows each strategy team to
deploy their monitoring UI independently without affecting the host shell.

```
Host Shell (Nairobi Dashboard)
├── /shell                    → Layout, navigation, auth, WebSocket manager
├── /remote/regime-monitor    → HMM regime visualization (Module Federation remote)
├── /remote/coint-dashboard   → Cointegration pairs monitor (remote)
├── /remote/ml-momentum       → ML momentum feature/prediction viewer (remote)
├── /remote/carry-monitor     → Carry trade positions (remote)
├── /remote/risk-dashboard    → CVaR, drawdown, circuit breakers (remote)
└── /remote/order-blotter     → Order history, fills, rejects (remote)
```

### Webpack 5 Module Federation Configuration

**Host Shell (webpack.config.js):**
```javascript
const { ModuleFederationPlugin } = require('webpack').container;

module.exports = {
  plugins: [
    new ModuleFederationPlugin({
      name: 'shell',
      remotes: {
        regimeMonitor: 'regimeMonitor@http://localhost:3001/remoteEntry.js',
        cointDashboard: 'cointDashboard@http://localhost:3002/remoteEntry.js',
        mlMomentum: 'mlMomentum@http://localhost:3003/remoteEntry.js',
        carryMonitor: 'carryMonitor@http://localhost:3004/remoteEntry.js',
        riskDashboard: 'riskDashboard@http://localhost:3005/remoteEntry.js',
        orderBlotter: 'orderBlotter@http://localhost:3006/remoteEntry.js',
      },
      shared: {
        react: { singleton: true, requiredVersion: '^18.0.0' },
        'react-dom': { singleton: true, requiredVersion: '^18.0.0' },
        recharts: { singleton: true },
        '@tanstack/react-query': { singleton: true },
      },
    }),
  ],
};
```

**Remote Example (regime-monitor/webpack.config.js):**
```javascript
module.exports = {
  plugins: [
    new ModuleFederationPlugin({
      name: 'regimeMonitor',
      filename: 'remoteEntry.js',
      exposes: {
        './RegimePanel': './src/RegimePanel',
      },
      shared: {
        react: { singleton: true, requiredVersion: '^18.0.0' },
        'react-dom': { singleton: true, requiredVersion: '^18.0.0' },
      },
    }),
  ],
};
```

### WebSocket Bridge (NATS → Browser)

A WebSocket gateway bridges NATS telemetry to the browser:

```python
# ws_bridge.py — runs on Nairobi server
import asyncio
import websockets
import nats

async def bridge(websocket, path):
    nc = await nats.connect("nats://ld4-gateway:4222")
    js = nc.jetstream()
    
    # Subscribe to all telemetry
    sub = await js.pull_subscribe("telemetry.>", "NAIROBI_DASHBOARD")
    
    while True:
        try:
            msgs = await sub.fetch(batch=10, timeout=1)
            for msg in msgs:
                await websocket.send(msg.data.decode())
                await msg.ack()
        except nats.errors.TimeoutError:
            pass  # No messages available, continue
```

### Dashboard Component Contract

Each remote module must export a React component conforming to this interface:

```typescript
interface StrategyDashboardProps {
  wsUrl: string;              // WebSocket URL for real-time data
  natsSubject: string;        // NATS subject filter for this strategy
  timeRange: [Date, Date];    // User-selected time window
  onAlert: (alert: Alert) => void;  // Callback to host shell's alert system
}

// Each remote exports a default component matching this interface:
// export default function RegimePanel(props: StrategyDashboardProps): JSX.Element
```

### Production Deployment

```
Nairobi Server:
  - Nginx reverse proxy: routes /remote/* to individual remote bundles
  - NATS→WebSocket bridge: single process, port 8080
  - Host shell: served from /shell/ path
  - SSL termination: Let's Encrypt certificate

Remote bundles:
  - Built and pushed to CDN (or local Nginx) independently
  - Each remote has its own CI pipeline
  - Version pinning via remoteEntry.js hash
  - Fallback: if remote fails to load, host shell shows "Module unavailable" placeholder
```

## Implementation Structure

```
./backend-ipc/
  zeromq/
    order_router.py       (PULL socket, order dispatch)
    market_data_pub.py    (PUB socket, tick fan-out)
    message_formats.py    (struct pack/unpack definitions)
    core_affinity.py      (CPU pinning utilities)
  nats/
    telemetry_publisher.py (JetStream publish from NY4/LD4)
    stream_config.py       (Stream and consumer setup)
    ws_bridge.py           (NATS → WebSocket for Nairobi)
  tests/
    test_zmq_routing.py
    test_nats_delivery.py

./dashboard/
  shell/                  (Host application)
    webpack.config.js
    src/
      App.tsx
      WebSocketManager.ts
      AlertSystem.tsx
  remotes/
    regime-monitor/
    coint-dashboard/
    ml-momentum/
    carry-monitor/
    risk-dashboard/
    order-blotter/
  nginx/
    dashboard.conf        (Reverse proxy config)
```

Read `prompts/` for tool-specific implementation prompts.
