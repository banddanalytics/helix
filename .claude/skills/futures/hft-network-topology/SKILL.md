---
name: hft-network-topology
description: >
  Design and implement the physical and logical network topology for a geographically distributed
  HFT trading system with a Nairobi command center and co-located execution at NY4/LD4 data centers.
  Covers subsea fiber routing (PEACE/2Africa cables), FIX 4.4 persistent TCP connections to CME,
  WireGuard mesh VPN overlays, BGP peering, kernel bypass networking (DPDK/Solarflare OpenOnload),
  and latency budget allocation. Use this skill whenever working on: network architecture for
  trading systems, co-location topology design, FIX protocol integration with CME, cross-continent
  latency optimization, bare-metal server provisioning at NY4/LD4, or any task involving the
  physical infrastructure layer of the algorithmic trading suite. Also trigger when the user
  mentions "network topology", "co-location", "FIX API", "CME connectivity", "subsea fiber",
  "latency budget", or "execution infrastructure".
---

# HFT Network Topology Skill

## Purpose

This skill enables the design and implementation of a production-grade network topology for an
algorithmic trading system where the monitoring/analytics dashboard operates from Nairobi, Kenya
while all order execution occurs on co-located bare-metal servers at Equinix NY4 (New York) and
Equinix LD4 (London).

## Architectural Context

The system must solve a fundamental physics constraint: Nairobi is ~12,000 km from NY4 and ~6,500 km
from LD4. Speed-of-light latency alone is ~55ms to LD4 and ~80ms to NY4 one-way. With real-world
routing overhead, expect 150-220ms RTT. This means Nairobi CANNOT be in the execution hot path.
The architecture mandates a strict separation:

- **Nairobi**: Command, surveillance, analytics, risk dashboard (human-speed interactions)
- **NY4/LD4**: Autonomous execution, order routing, FIX sessions, market data ingestion (microsecond-speed)

## Network Topology Specification

### Layer 1: Physical Fiber Routes

```
Nairobi ──[PEACE Cable: Mombasa→Marseille→London]──► LD4 (Equinix London)
                                                        │
Nairobi ──[2Africa: Mombasa→Egypt→Marseille]──► LD4 ──[TAT-14/AEConnect]──► NY4 (Equinix New York)
```

**Primary Path (Nairobi → LD4):**
- PEACE Cable: Mombasa landing → Red Sea → Mediterranean → Marseille → London
- Expected one-way latency: 60-75ms (fiber), 80-110ms (with routing hops)

**Primary Path (Nairobi → NY4):**
- Route via LD4 as a transit hop, then LD4→NY4 via dedicated low-latency transatlantic
- LD4→NY4 baseline: ~32ms one-way (Hibernia Express subsea)
- Total Nairobi→NY4: ~110-145ms one-way

**Redundant Path:**
- 2Africa cable via Egypt as failover
- Dedicated MPLS circuit from Safaricom Business / Liquid Intelligent Technologies

### Layer 2: VPN Mesh Overlay

All inter-site communication traverses a WireGuard mesh VPN. WireGuard is selected for its
minimal cryptographic overhead (~2μs per packet on modern hardware) and kernel-space performance.

```
Topology:
  NBO-GW (Nairobi Gateway)  ◄──WireGuard──►  LD4-GW
  NBO-GW                    ◄──WireGuard──►  NY4-GW
  LD4-GW                    ◄──WireGuard──►  NY4-GW  (cross-colo sync)
```

Configuration constraints:
- MTU: 1420 (WireGuard overhead on standard 1500 Ethernet)
- Keepalive: 25s (NAT traversal for African ISP middleboxes)
- AllowedIPs: Strict /32 per host, no wildcard routing
- Pre-shared keys: Rotated via HashiCorp Vault on 24h schedule

### Layer 3: Execution Infrastructure at NY4/LD4

Each co-location site runs identical bare-metal configurations:

**Server Specification (per site):**
- CPU: AMD EPYC 9554 (64C/128T, 3.1GHz base) — selected for consistent clock speeds
- RAM: 512GB DDR5-4800 ECC Registered
- NIC: Solarflare X2522-25G with OpenOnload kernel bypass
- Storage: 4x Samsung PM9A3 3.84TB NVMe in RAID-10 (ZFS mirror-stripe)
- OS: Ubuntu 22.04 LTS with PREEMPT_RT kernel patch

**Kernel Bypass Networking:**
- Solarflare OpenOnload for FIX session sockets — bypasses kernel TCP/IP stack entirely
- ef_vi API for raw packet injection on market data multicast
- CPU core affinity: Cores 0-3 reserved for OS; Cores 4-15 for execution threads; Cores 16+ for analytics

### Layer 4: FIX Protocol — CME Connectivity

The system connects to CME Group via FIX 4.4 over persistent TCP connections.

**FIX Session Architecture:**
```
[NY4 Execution Server]
  ├── FIX Session 1: CME Globex (Order Entry) — iLink 3.0
  │     SenderCompID: FIRM_NY4_OE
  │     TargetCompID: CME
  │     HeartBtInt: 30
  │     ResetOnLogon: Y
  │     SocketConnectPort: 9300-9310 (CME assigned)
  │
  ├── FIX Session 2: CME Market Data (MDP 3.0 → MBO Channel)
  │     Multicast groups: 224.0.28.x (incremental), 224.0.31.x (snapshot)
  │     Interface: Solarflare ef_vi zero-copy receive
  │
  └── FIX Session 3: CME Drop Copy (Fills/Executions confirmation)
        SenderCompID: FIRM_NY4_DC
        Redundant acknowledgment of all fills
```

**Critical FIX Fields for MBO Data:**
- Tag 37 (OrderID): Exchange-assigned order identifier
- Tag 346 (NumberOfOrders): Orders at price level (MBP) or individual order (MBO)
- Tag 1023 (MDPriceLevel): Explicit price level for book reconstruction
- Tag 83 (RptSeq): Sequence number for gap detection

**Sequence Number Recovery Protocol:**
1. On gap detection (RptSeq discontinuity), immediately request snapshot via TCP recovery port
2. Buffer all incremental messages during recovery
3. Apply snapshot, then replay buffered incrementals
4. If recovery exceeds 500ms, switch to backup multicast group

### Layer 5: Nairobi Dashboard Connectivity

The Nairobi command center connects to execution sites for monitoring only. It NEVER sends
order instructions directly — all execution logic is autonomous at NY4/LD4.

**Data flows to Nairobi:**
- NATS JetStream: Telemetry, PnL updates, position snapshots (pub/sub, 100ms intervals)
- gRPC streaming: Real-time order book visualization (compressed protobuf)
- PostgreSQL logical replication: Historical trade log sync (async, 5s batches)

**Nairobi → Execution site commands (rate-limited):**
- Strategy parameter updates (kill switches, position limits)
- Transmitted via authenticated gRPC with 2FA confirmation
- Maximum command rate: 1 per second (human-speed, anti-fat-finger)

### Latency Budget Allocation

```
Component                        Budget (μs)    Notes
─────────────────────────────────────────────────────────────────
Market data NIC → userspace      0.5-1.2        OpenOnload kernel bypass
Packet parse (FIX/MDP decode)    0.8-1.5        Pre-allocated buffers
Signal computation                2-10           Strategy dependent
Order construction (FIX msg)     0.3-0.5        Template-based, pre-serialized
Order NIC → CME matching          1.5-3.0        Co-located cross-connect
─────────────────────────────────────────────────────────────────
TOTAL tick-to-trade (co-lo)      5-16 μs        Target: <20μs p99
Nairobi RTT (monitoring only)    200-300 ms     Not in execution path
```

## Implementation Sequence

1. Provision bare-metal at NY4 and LD4 via Equinix Metal or direct cage lease
2. Install Ubuntu 22.04 + PREEMPT_RT kernel, configure isolcpus boot parameter
3. Deploy Solarflare NICs, compile and load OpenOnload module
4. Establish WireGuard mesh between all three sites
5. Configure CME FIX sessions (requires CME onboarding — 4-6 week lead time)
6. Deploy NATS JetStream cluster for telemetry relay to Nairobi
7. Validate end-to-end with CME New Release certification environment
8. Production cutover with parallel shadow trading period

## Key Dependencies

- CME iLink 3.0 certification (mandatory before live trading)
- Equinix cross-connect provisioning (2-3 week lead time)
- Safaricom/Liquid dedicated circuit for Nairobi uplink (SLA negotiation required)
- Solarflare OpenOnload license (free for basic, paid for ef_vi advanced features)

Read `references/` for tool-specific implementation prompts.
