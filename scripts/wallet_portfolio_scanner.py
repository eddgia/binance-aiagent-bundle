#!/usr/bin/env python3
"""
Binance AI Agent Wallet & Portfolio Scanner
Queries on-chain balances, token values, gas, and NFT portfolio for Binance Agentic Wallet.
"""

import sys
import json
import subprocess
import os
import shutil

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

CHAIN_ID = CONFIG["binance_chain_id"]
USER_WALLET = CONFIG["wallet_address"]

BAW_CMD = CONFIG.get("baw_path", "auto")
if BAW_CMD == "auto":
    candidate = shutil.which("baw")
    if not candidate and sys.platform == "win32":
        candidate = shutil.which("baw.cmd")
        if not candidate:
            appdata = os.environ.get("APPDATA", "")
            npm_baw = os.path.join(appdata, "npm", "baw.cmd")
            if os.path.exists(npm_baw):
                candidate = npm_baw
    BAW_CMD = candidate or "baw"

def main():
    print("=" * 60)
    print("       BINANCE AI AGENT PORTFOLIO AUDIT REPORT")
    print("=" * 60)
    print(f"Wallet Address: {USER_WALLET}")
    print(f"Chain ID:       BSC ({CHAIN_ID})")

    # 1. Check Agent ID
    cmd_agent = [BAW_CMD, "wallet", "agent-id", "--json"]
    res_a = subprocess.run(cmd_agent, capture_output=True, text=True)
    if res_a.returncode == 0:
        data_a = json.loads(res_a.stdout)
        if data_a.get("success"):
            print(f"Agent ID:       {data_a['data'].get('domain', 'None')}")
            print(f"Claimed:        {data_a['data'].get('claimed', False)}")

    # 2. Check Balances
    print("\n--- TOKEN BALANCES ---")
    cmd_bal = [BAW_CMD, "wallet", "balance", "--binanceChainId", CHAIN_ID, "--json"]
    res_b = subprocess.run(cmd_bal, capture_output=True, text=True)
    total_usd = 0.0
    if res_b.returncode == 0:
        data_b = json.loads(res_b.stdout)
        tokens = data_b.get("data", [])
        for t in tokens:
            sym = t.get("symbol")
            bal = float(t.get("balance", "0"))
            val = float(t.get("value", "0"))
            price = float(t.get("price", "0"))
            total_usd += val
            print(f" • {sym:8} | Balance: {bal:>16.6f} | Price: ${price:>10.4f} | Value: ${val:>8.2f} USD")
    print(f"\nTotal Liquid Portfolio Value: ${total_usd:.2f} USD")

    # 3. Check Sniper History
    hist_file = os.path.join(BASE_DIR, "sniper_history.json")
    if os.path.exists(hist_file):
        with open(hist_file, "r") as f:
            h = json.load(f)
            minted = h.get("minted", [])
            print(f"\nTotal NFT Collections Sniped: {len(minted)} collections")

    print("=" * 60)

if __name__ == "__main__":
    main()
