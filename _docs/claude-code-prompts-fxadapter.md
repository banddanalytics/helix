# Implementation Prompts — Forex Broker Adapter

## Claude Code Prompts

### Prompt 1: Execution Abstraction Layer
```
Implement the complete execution abstraction layer with abstract interfaces and
the MT5 concrete adapter.

Requirements:
- Abstract base classes: MarketDataProvider, OrderExecutor, PositionManager
- Dataclasses: Tick, Bar, OrderRequest, OrderResult, Position (market-agnostic)
- MT5Adapter implementing all three interfaces
- Connection management with auto-reconnect
- SpreadModel class for variable spread tracking and cost adjustment
- Lot sizing function converting Kelly fraction to MT5 lots with pip value calculation
- Swap rate extraction for carry signal computation
- Error handling: MT5 error codes mapped to meaningful exceptions
- Async wrappers around MT5's synchronous API using asyncio.to_thread()

Output: ./src/execution/
  abstract.py        (ABC interfaces and dataclasses)
  mt5_adapter.py     (MetaTrader 5 implementation)
  spread_model.py    (Variable spread tracking)
  lot_sizing.py      (Kelly → lot conversion)
  swap_rates.py      (Carry signal from broker swaps)

Tests: mock MT5 API calls using unittest.mock for cross-platform testing
```

### Prompt 2: MT5 Data Bridge for Linux
```
Build a ZeroMQ bridge that runs MT5 data collection on Windows and forwards
ticks/bars to the Linux-based alpha engines.

Requirements:
- Windows side: Python script running alongside MT5 terminal
  - Subscribes to tick events via mt5.symbol_info_tick() polling loop (10ms interval)
  - Publishes ticks on ZeroMQ PUB socket (tcp://*:5556)
  - Publishes bars on completion (tcp://*:5557)
  - Accepts order requests on ZeroMQ PULL socket (tcp://*:5558)
  - Returns order results on ZeroMQ PUSH socket (tcp://*:5559)
- Linux side: connects to Windows VPS over WireGuard
  - Receives ticks/bars via ZeroMQ SUB
  - Sends order requests via ZeroMQ PUSH
  - Feeds data into ArcticDB and alpha engines

Message format: MessagePack serialization (faster than JSON, schema-flexible)
Output: ./src/bridge/
  windows_mt5_publisher.py
  linux_data_consumer.py
  message_schemas.py
```

### Prompt 3: Forex-Specific ArcticDB Ingestion
```
Adapt the ArcticDB ingestion pipeline for Forex broker data.

Requirements:
- Schema adapted for Forex ticks (no MBO fields):
  timestamp(ns), symbol, bid, ask, tick_volume, spread
- Bar schema: timestamp, symbol, open, high, low, close, tick_volume, spread
- Swap rate daily snapshots: timestamp, symbol, swap_long, swap_short
- Data normalization: handle 5-digit vs 3-digit pricing, variable pip sizes
- Session tagging: each bar tagged with session (Asian/London/NY/Overlap)
- Gap detection: flag weekend gaps, data feed interruptions
- PiT compliance: identical .shift(1) framework from arcticdb-vectorbt-engine

Output: ./src/data/forex_ingestion.py, ./src/data/forex_schemas.py
```

## Cursor Prompts

### .cursorrules for Forex phase
```
You are implementing a Forex trading system using a retail broker (MT5/cTrader).
Key constraints:
- NO genuine order book data exists — never implement OFI, VPIN, or depth features
- Tick volume is a PROXY for activity only — never use it as real volume
- Variable spreads must be modeled as a stochastic cost in all signal evaluations
- Swap rates change daily — extract and store them, don't hardcode
- MT5 Python API is Windows-only — bridge via ZeroMQ for Linux alpha engines
- All code must use the execution abstraction layer (never call mt5.* directly from alpha)
- Lot sizing must account for pip value conversion across account currencies
- Kelly fraction → lot size conversion must respect broker's volume_min/volume_max/volume_step
- Always check mt5.last_error() after every MT5 API call
```

## Claude CLI Prompts

```bash
# Generate swap rate carry ranking
claude -p "Generate a script that:
1. Connects to MT5 and extracts swap rates for all major FX pairs
2. Computes annualized carry (long and short) for each pair
3. Ranks pairs by net carry signal
4. Flags pairs where spread cost exceeds carry benefit
5. Outputs a markdown table: symbol | carry_long | carry_short | spread_cost | viable
Use the forex-broker-adapter skill's swap rate formula." > compute_carry_ranking.py
```

```bash
# Validate execution abstraction layer
claude -p "Given the MT5Adapter implementation:
$(cat src/execution/mt5_adapter.py)

Verify:
1. All abstract methods from MarketDataProvider/OrderExecutor/PositionManager implemented
2. No mt5.* calls leak outside the adapter
3. Error handling covers all MT5 retcodes
4. Lot sizing respects volume_min/max/step
5. Spread model tracks p95 spread correctly
Output: PASS/FAIL per check."
```
