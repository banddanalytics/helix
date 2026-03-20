---
name: hft-network-topology
description: >
  Stage B ONLY (CME Futures): Design the physical and logical network topology for
  co-located execution at Equinix NY4/LD4 with Nairobi monitoring. During Stage A (Forex),
  a simpler VPS-based topology is used (documented in this skill's Stage A section).
  Covers subsea fiber routing, FIX iLink 3.0, WireGuard mesh, PREEMPT_RT kernel,
  Solarflare OpenOnload kernel bypass, CPU core affinity, and NATS JetStream cross-continent
  telemetry. Use this skill when: deploying to co-location, configuring CME FIX sessions,
  setting up bare-metal servers, kernel bypass networking, or network topology design.
---

# HFT Network Topology Skill

## Stage A Topology (Forex Phase — Simple)

During Stage A, execution runs on a Windows VPS near the broker's servers:

```
[Windows VPS near broker]        [Linux server / Nairobi]
  MT5 Terminal                     Alpha engines + ArcticDB
  ZMQ Publisher     ◄──WireGuard──►  ZMQ Subscriber
                                     React Dashboard
```

- Single Windows VPS (Vultr/Hetzner, London or New York depending on broker)
- WireGuard tunnel to Nairobi for monitoring
- NATS single-node for telemetry
- No co-location, no kernel bypass, no PREEMPT_RT
- Total cost: ~$50-100/month

## Stage B Topology (CME Futures — Full)

### Physical Layer

```
Nairobi ──[PEACE Cable: Mombasa→Marseille→London]──► LD4
Nairobi ──[2Africa: Mombasa→Egypt→Marseille]──► LD4 ──[Hibernia Express]──► NY4
```

### Execution Infrastructure at NY4/LD4

- CPU: AMD EPYC 9554, 512GB DDR5 ECC
- NIC: Solarflare X3522/X4542 with OpenOnload 8.1.x kernel bypass
- OS: Ubuntu 22.04 + PREEMPT_RT 6.1-rt LTS
- isolcpus=4-15, nohz_full=4-15, rcu_nocbs=4-15

### WireGuard Mesh (3-site)

```
NBO (10.200.0.1) ◄──► LD4 (10.200.0.2) ◄──► NY4 (10.200.0.3)
NBO ◄──────────────────────────────────────► NY4
MTU: 1420, PersistentKeepalive: 25 for NBO
```

### CME iLink 3.0 Sessions

- FIXP session layer with SBE encoding
- Negotiate → Establish logon sequence
- HMAC digital signatures
- 250 TPS throttle for order entry
- MDP 3.0 multicast for market data (10 Gbps required post-March 2026)

### NATS JetStream (Cross-Continent)

- Hub: 3-node cluster at NY4 with R=3 replication
- LD4: leaf node connecting to NY4 hub
- Nairobi: leaf node with separate JetStream domain
- Leaf node compression for subsea bandwidth efficiency

### Latency Budget (Stage B)

```
Component                     Budget (μs)
Market data NIC → userspace   0.5-1.2 (OpenOnload)
FIX/MDP decode                0.8-1.5
Signal computation            2-10
Order construction            0.3-0.5
NIC → CME matching            1.5-3.0
TOTAL tick-to-trade           5-16 μs (target: <20μs p99)
Nairobi RTT (monitoring)      200-300 ms (NOT in execution path)
```

## Migration Trigger: Stage A → Stage B

Activate this skill's Stage B infrastructure when:
- Account equity exceeds CME margin requirements
- Forex strategies show 6+ months consistent positive expectancy
- CME iLink 3.0 sandbox certification completed
- Equinix colocation lease and cross-connect provisioned

## Implementation Structure

```
./infra/
  stage_a/
    vps-setup.sh          (Windows VPS provisioning)
    wireguard-simple.conf (2-site: VPS + Nairobi)
    nats-single.conf      (Single NATS node)
  stage_b/
    ansible/              (Bare-metal provisioning at NY4/LD4)
    wireguard/            (3-site mesh configs)
    nats/                 (Hub + leaf cluster configs)
    terraform/            (Equinix Fabric interconnection)
    kernel/               (PREEMPT_RT build script)
    onload/               (Solarflare OpenOnload installation)
    fix/                  (CME iLink 3.0 session configs)
```
