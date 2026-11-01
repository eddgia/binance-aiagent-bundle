---
name: binance-aiagent-suite
description: |
  Master skill for Binance AI Agent & Binance Agentic Wallet (BAW) ecosystem.
  Covers real-time smart wallet tracking & auto-minting (>10 consensus rule), scam/drainer filtering,
  fast PancakeSwap LP reserve detection, automatic dumping to BNB, gas floor protection,
  safe contract call simulation & execution, PancakeSwap DEX token swapping,
  portfolio monitoring, yield/mining protocol automation (Hash21, FAGENT PoA Vault, Ptah IAO, Moribundus),
  and complete on-chain asset management on BNB Smart Chain (BSC).
metadata:
  author: kpl-agyent-team
  version: '3.2.0'
  requiredCliVersion: '1.11.0'
  openclaw:
    requires:
      bins:
        - baw
        - python
    install:
      - kind: node
        package: '@binance/agentic-wallet'
        bins: [baw]
        label: Install Binance Agentic Wallet CLI (npm)
---

# Binance AI Agent & Smart Sniper Suite v3.2

This skill provides full-spectrum automated operations for the **Binance Agentic Wallet (`baw`)** on **BNB Smart Chain (BSC)**.

---

## 📁 Bundle Architecture

```
binance-aiagent-bundle/
├── config.json                     # Global parameters (RPC, Wallet, Thresholds, Safety)
├── SKILL.md                        # Skill definition & execution playbook
├── README.md                       # Quick-start guide for Muse & AI Agents
├── data/
│   └── smart_wallets_list.json     # Curated database of 4,942 top smart wallets on BSC
├── logs/                           # Runtime logs (auto-created)
│   ├── sniper_activity.log         # Sniper log & consensus tracking
│   ├── portfolio_sentinel.log      # Hash21, IAO & FAGENT vault logs
│   └── twitter_alpha.log           # KOL tweets & alpha alerts
├── scripts/
│   ├── run_all.py                  # Master launcher for all 3 daemons
│   ├── smart_sniper_daemon.py      # v3.2: >10 consensus, fast 4s LP poller, auto-dump to BNB
│   ├── portfolio_price_sentinel.py # v2.0: Hash21, FAGENT R4 Vault, IAO pool monitor
│   ├── twitter_alpha_sentinel.py   # Real-time alpha monitoring on X
│   ├── ptah_iao_manager.py         # IAO offering check, claim forensics, LP reserves
│   ├── market_order_swapper.py     # Rapid DEX market order token swapper
│   ├── contract_interactor.py      # 2-layer verified safe contract caller
│   └── wallet_portfolio_scanner.py # Real-time balance and inventory auditor
└── references/                     # Comprehensive BAW CLI command references (17 files)
```

---

## ⚡ Core Operational Commands

### 1. Master Daemons
| Task | Command | Description |
| :--- | :--- | :--- |
| **Run All Daemons** | `python scripts/run_all.py` | Runs Sniper, Price Sentinel, and Twitter Alpha concurrently. |
| **Run Sniper Only** | `python scripts/smart_sniper_daemon.py` | Snipes free mints with >10 wallets consensus & auto-dumps to BNB. |
| **Run Sentinel Only** | `python scripts/portfolio_price_sentinel.py` | Monitors Hash21 hashrate, FAGENT Vault #38,000, and IAO presale. |
| **Run Alpha Tracker** | `python scripts/twitter_alpha_sentinel.py` | Tracks crypto KOLs on X for early contract announcements. |

### 2. Manual Tools & Management
| Task | Command | Description |
| :--- | :--- | :--- |
| **Check IAO Status** | `python scripts/ptah_iao_manager.py` | Inspects Ptah Trade IAO offering, airdrop claim status, and liquidity. |
| **Audit Portfolio** | `python scripts/wallet_portfolio_scanner.py` | Audits on-chain token balances, USD values, and NFT holdings. |
| **DEX Swap to BNB** | `python scripts/market_order_swapper.py <TOKEN> <AMOUNT>` | Swaps tokens on PancakeSwap via BAW with MEV protection. |
| **Simulate Contract** | `python scripts/contract_interactor.py <CONTRACT> <CALLDATA> --preview` | Previews gas and validates call before on-chain execution. |

---

## 🛡️ Critical Safety Rules (Strictly Enforced)

1. **> 10 Wallets Consensus**: A candidate contract is NEVER minted unless more than 10 distinct smart wallets (`REQUIRED_CONSENSUS = 11`) mint it within a 1-hour window.
2. **Gas Protection Floor**: If the wallet's BNB balance falls below `0.0015 BNB`, all minting halts automatically.
3. **Instant Liquidity Polling & BNB Dump**: Every newly minted token is monitored every 4 seconds. As soon as PancakeSwap reserves appear, it is dumped 100% to **BNB** (`0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE`).
4. **Scam Prevention**: All contract interactions are pre-simulated using BAW preflight checks (`--preview`). Approvals for unlimited token transfers are blocked.
