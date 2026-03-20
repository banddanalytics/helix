<!-- GSD:project-start source:PROJECT.md -->
## Project

**Helix — Algorithmic Trading Suite**

Helix is a two-stage algorithmic trading system for currency markets. Stage A trades retail Forex via MT5/cTrader with 4 alpha engines, a CVaR risk engine, and a real-time React dashboard. Stage B migrates to CME currency futures via co-located iLink 3.0 execution once sufficient capital and strategy validation are achieved.

**Core Value:** A fully automated, broker-agnostic trading system where every signal passes through rigorous quality gates (AST validation, PiT compliance, 80%+ test coverage) before reaching live markets — eliminating hallucinated API calls and look-ahead bias from the execution path.

### Constraints

- **Platform:** MT5 Python API is Windows-only — all alpha engine code runs on Linux via ZMQ bridge
- **Data:** No genuine order book data in Stage A — tick volume is a proxy only
- **Quality:** All code must pass AST/KCH validation (no phantom APIs), PiT compliance, mypy strict, 80%+ coverage
- **Capital:** Stage B requires $50K+ equity and 6+ months consistent positive expectancy
- **Stage B trigger:** Equity > $50K AND strategy profitable 6+ months AND spreads > 30% gross alpha AND iLink 3.0 certification complete
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
