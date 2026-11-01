#!/usr/bin/env python3
"""
Binance AI Agent Safe Contract Interactor
Pre-simulates arbitrary smart contract calls using BAW preview, checks for drainer/allowance risks,
and safely executes approved transactions.
Usage:
    python contract_interactor.py --to 0xContract... --data 0xCalldata... [--value 0] [--yes]
"""

import sys
import json
import argparse
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
    parser = argparse.ArgumentParser(description="Simulate and execute contract calls safely")
    parser.add_argument("--to", required=True, help="Target smart contract address")
    parser.add_argument("--data", required=True, help="Hex calldata (starts with 0x)")
    parser.add_argument("--value", default="0", help="Value in wei (default: 0)")
    parser.add_argument("--yes", action="store_true", help="Auto-confirm execution if simulation is clean")
    args = parser.parse_args()

    print(f"=== Simulating Contract Call on BSC ({CHAIN_ID}) ===")
    print(f"Target: {args.to}")
    print(f"Value:  {args.value} wei")
    print(f"Data:   {args.data[:66]}...")

    prev_cmd = [
        BAW_CMD, "contract-call", "preview",
        "--binanceChainId", CHAIN_ID,
        "--from", USER_WALLET,
        "--to", args.to,
        "--value", str(args.value),
        "--inputData", args.data,
        "--json"
    ]
    res_p = subprocess.run(prev_cmd, capture_output=True, text=True)
    if res_p.returncode != 0:
        print(f"Simulation failed to execute: {res_p.stderr}")
        sys.exit(1)

    p_data = json.loads(res_p.stdout)
    if not p_data.get("success"):
        print(f"Simulation Reverted / Rejected: {p_data.get('error')}")
        sys.exit(1)

    sim = p_data["data"].get("simulationResult", {})
    code = sim.get("simulationCode")
    allowance = sim.get("allowanceChanges", [])
    authority = sim.get("authorityChanges", [])
    bal_changes = sim.get("balanceChanges", [])
    req_id = p_data["data"].get("requestId")

    print("\n--- Simulation Results ---")
    print(f"Code: {code} ({'SUCCESS' if code == '000000000' else 'FAILED'})")
    print(f"Balance Changes: {len(bal_changes)}")
    for b in bal_changes:
        print(f"  Token: {b.get('contractAddress')} | Change: {b.get('change')} | Type: {b.get('tokenType')}")

    # Security verification
    if len(allowance) > 0 or len(authority) > 0:
        print("\n[CRITICAL WARNING] Authority or allowance changes detected! This may be a wallet drainer.")
        print(f"Allowance changes: {allowance}")
        print(f"Authority changes: {authority}")
        sys.exit(1)

    if code != "000000000":
        print(f"\n[ERROR] Simulation failed with code {code}.")
        sys.exit(1)

    print("\n[VERIFIED SAFE] 100% clean simulation.")
    if not args.yes:
        confirm = input("Execute transaction on-chain? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Cancelled by user.")
            sys.exit(0)

    print("=== Broadcasting Transaction ===")
    exec_cmd = [BAW_CMD, "contract-call", "execute", "--requestId", req_id, "--json"]
    res_e = subprocess.run(exec_cmd, capture_output=True, text=True)
    if res_e.returncode == 0:
        e_data = json.loads(res_e.stdout)
        if e_data.get("success"):
            tx_hash = e_data["data"].get("txHash")
            print(f"Transaction Broadcasted Successfully! TxHash: {tx_hash}")
        else:
            print(f"Execute failed: {e_data.get('error')}")
    else:
        print(f"Execute command error: {res_e.stderr}")

if __name__ == "__main__":
    main()
