---
name: zeromq-nats-react-ui
description: >
  Implement backend IPC using ZeroMQ and NATS plus the React dashboard. Supports BOTH
  stages: Stage A uses ZeroMQ as a bridge between Windows MT5 and Linux alpha engines
  with a single NATS node for telemetry. Stage B uses ZeroMQ for intra-host nanosecond
  IPC at NY4/LD4 with a NATS JetStream cluster for cross-continent telemetry. The React
  Webpack 5 Module Federation dashboard works identically in both stages — it consumes
  telemetry from NATS regardless of the backend topology. Use this skill for: ZeroMQ
  patterns, NATS messaging, order routing, telemetry, React dashboard, Module Federation,
  micro-frontends, CPU affinity, or IPC design.
---

# ZeroMQ/NATS IPC & React Dashboard Skill

## Part 1: ZeroMQ Architecture

### Stage A: Cross-Host Bridge (Forex Phase)

ZeroMQ bridges Windows MT5 to Linux alpha engines over WireGuard:

```
[Windows VPS]                          [Linux / Nairobi]
MT5 Terminal                            Alpha Engines
  │                                       │
  ├── ZMQ PUB tcp://*:5556 ─ticks──►     ZMQ SUB
  ├── ZMQ PUB tcp://*:5557 ─bars───►     ZMQ SUB
  ├── ZMQ PULL tcp://*:5558 ◄─orders──   ZMQ PUSH
  └── ZMQ PUSH tcp://*:5559 ─fills──►    ZMQ PULL
  
  Over WireGuard VPN (10.200.0.x)
  MessagePack serialization
```

```python
# Windows side: publish ticks from MT5
import zmq, msgpack, MetaTrader5 as mt5

ctx = zmq.Context()
tick_pub = ctx.socket(zmq.PUB)
tick_pub.bind("tcp://*:5556")
tick_pub.setsockopt(zmq.SNDHWM, 100000)

while True:
    for symbol in ["EURUSD", "GBPUSD", "AUDUSD"]:
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            data = msgpack.packb({
                'ts': tick.time_msc, 'sym': symbol,
                'bid': tick.bid, 'ask': tick.ask, 'vol': tick.volume_real
            })
            tick_pub.send_multipart([symbol.encode(), data])
    time.sleep(0.01)  # 10ms poll
```

```python
# Linux side: consume ticks
sub = ctx.socket(zmq.SUB)
sub.connect("tcp://10.200.0.1:5556")  # Windows VPS via WireGuard
sub.setsockopt_string(zmq.SUBSCRIBE, "EURUSD")

while True:
    topic, data = sub.recv_multipart()
    tick = msgpack.unpackb(data)
    # Feed to ArcticDB writer and signal engines
```

### Stage B: Intra-Host IPC (Futures Phase)

ZeroMQ for co-located nanosecond IPC at NY4/LD4:

```
[NY4 Process Map]
┌──────────────┐  PUSH/PULL (orders)  ┌──────────────┐
│ Signal Engine │ ───────────────────► │ Order Router  │
│ (cores 4-7)  │  ipc:///tmp/orders   │ (core 8)     │
└──────────────┘                      └──────────────┘

┌──────────────┐  PUB/SUB (mkt data)  ┌──────────────┐
│ FIX Parser   │ ───────────────────► │ Strategies   │
│ (core 9)     │  ipc:///tmp/mdata    │ (cores 10-15) │
└──────────────┘                      └──────────────┘
```

Key differences from Stage A:
- IPC transport (`ipc://`) not TCP — zero-copy, nanosecond latency
- struct packing (not MessagePack) — no serialization overhead
- CPU core affinity — each process pinned to dedicated core

```python
# Stage B: struct-packed order message (37 bytes fixed-size)
import struct
ORDER_FMT = '!BQdiBQ'
def pack_order(side, symbol_id, price, qty, order_type, timestamp):
    return struct.pack(ORDER_FMT, side, symbol_id, price, qty, side, order_type, timestamp)
```

## Part 2: NATS Telemetry

### Stage A: Single Node

```
[NATS single node on Linux server]
  Subjects: telemetry.pnl, telemetry.positions, telemetry.risk, telemetry.regime
  Storage: File-backed JetStream, 7-day retention
  Consumer: nairobi-dashboard (pull-based)
```

### Stage B: Hub + Leaf Cluster

```
[NY4: 3-node NATS cluster (hub)]
  │
  ├── [LD4: leaf node] ── connects on port 7422
  │
  └── [Nairobi: leaf node] ── separate JetStream domain
      └── Leaf compression enabled for subsea bandwidth
```

### NATS Subject Hierarchy (Both Stages)

```
telemetry.{site}.pnl           → PnL snapshots (100ms)
telemetry.{site}.positions     → Position inventory (1s)
telemetry.{site}.risk          → CVaR, drawdown, circuit breakers (1s)
telemetry.{site}.regime        → HMM regime state (5s)
telemetry.{site}.orders        → Order events (on-event)
telemetry.{site}.latency       → Execution latency (10s)
telemetry.{site}.system        → CPU, memory, NIC (30s)
```

### WebSocket Bridge (NATS → Browser)

```python
import asyncio, websockets, nats

async def bridge(websocket, path):
    nc = await nats.connect("nats://localhost:4222")
    js = nc.jetstream()
    sub = await js.pull_subscribe("telemetry.>", "nairobi-dashboard")
    
    while True:
        try:
            msgs = await sub.fetch(batch=10, timeout=1)
            for msg in msgs:
                await websocket.send(msg.data.decode())
                await msg.ack()
        except nats.errors.TimeoutError:
            pass
```

## Part 3: React Module Federation Dashboard

Works identically in both stages — consumes telemetry from NATS via WebSocket.

### Host Shell + Remote Modules

```
Host Shell (Nairobi Dashboard)
├── /shell                    → Layout, nav, auth, WebSocket manager
├── /remote/regime-monitor    → HMM regime visualization
├── /remote/coint-dashboard   → Cointegration pairs monitor
├── /remote/momentum-monitor  → ML prediction viewer
├── /remote/carry-monitor     → Carry positions (swaps in A, term structure in B)
├── /remote/risk-dashboard    → CVaR, drawdown, circuit breakers
└── /remote/order-blotter     → Order history, fills
```

### Webpack 5 Module Federation Config

```javascript
// Host shell
new ModuleFederationPlugin({
  name: 'shell',
  remotes: {
    regimeMonitor: 'regimeMonitor@http://localhost:3001/remoteEntry.js',
    riskDashboard: 'riskDashboard@http://localhost:3005/remoteEntry.js',
    // ... other remotes
  },
  shared: {
    react: { singleton: true, requiredVersion: '^18.0.0' },
    'react-dom': { singleton: true },
    recharts: { singleton: true },
  },
});
```

### Dashboard Component Interface

```typescript
interface StrategyDashboardProps {
  wsUrl: string;               // WebSocket URL for NATS bridge
  natsSubject: string;         // Subject filter
  timeRange: [Date, Date];
  tradingStage: 'forex' | 'futures';  // UI adapts labels/units
  onAlert: (alert: Alert) => void;
}
```

The `tradingStage` prop lets components display appropriate units:
- Stage A: "lots", "pips", "swap rate"
- Stage B: "contracts", "ticks", "term structure carry"

## CPU Core Affinity (Stage B Only)

```python
import os

CORE_MAP_STAGE_B = {
    'os_kernel':      [0, 1, 2, 3],
    'signal_engine':  [4, 5, 6, 7],
    'order_router':   [8],
    'fix_parser':     [9],
    'strategy_1':     [10, 11],
    'strategy_2':     [12, 13],
    'strategy_3':     [14, 15],
    'arcticdb_writer': [16, 17],
    'nats_bridge':    [18, 19],
    'monitoring':     [20, 21, 22, 23],
}

def pin_to_core(core_id: int):
    os.sched_setaffinity(0, {core_id})
```

Not used in Stage A — single VPS doesn't require core isolation.

## Implementation Structure

```
./src/ipc/
  zmq/
    bridge_publisher.py   (Stage A: Windows→Linux bridge)
    bridge_consumer.py    (Stage A: Linux subscriber)
    ipc_pipeline.py       (Stage B: intra-host PUSH/PULL)
    ipc_pubsub.py         (Stage B: intra-host PUB/SUB)
    message_formats.py    (MessagePack for A, struct for B)
    core_affinity.py      (Stage B only)
  nats/
    single_node.py        (Stage A: single NATS config)
    cluster.py            (Stage B: hub + leaf config)
    telemetry_pub.py      (Publish telemetry — both stages)
    ws_bridge.py          (NATS → WebSocket — both stages)
./ui/
  shell/                  (Host app — both stages)
  remotes/                (6 remote modules — both stages)
  nginx/                  (Reverse proxy config)
```
