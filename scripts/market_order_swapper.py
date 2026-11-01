#!/usr/bin/env python3
"""
Binance AI Agent Market Order Swapper
Executes rapid token swaps on PancakeSwap DEX via Binance Agentic Wallet (BAW) CLI.
Usage:
    python market_order_swapper.py --from 0xToken... --to 0xToken... --amount 1000 [--slippage 10]
    python market_order_swapper.py --from 0xToken... --to BNB --amount all
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
NATIVE_BNB = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"

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

def get_token_balance(token_addr):
    cmd = [BAW_CMD, "wallet", "balance", "--binanceChainId", CHAIN_ID, "--json"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        data = json.loads(res.stdout)
        for t in data.get("data", []):
            if t.get("address", "").lower() == token_addr.lower():
                return float(t.get("balance", "0"))
    return 0.0

def main():
    parser = argparse.ArgumentParser(description="Swap tokens on DEX via BAW CLI")
    parser.add_argument("--fromToken", required=True, help="Source token contract address (or symbol)")
    parser.add_argument("--toToken", default="BNB", help="Destination token (default: BNB)")
    parser.add_argument("--amount", required=True, help="Amount to swap or 'all'")
    parser.add_argument("--slippage", default="auto", help="Slippage percentage (default: auto)")
    args = parser.parse_args()

    from_addr = NATIVE_BNB if args.fromToken.upper() == "BNB" else args.fromToken
    to_addr = NATIVE_BNB if args.toToken.upper() == "BNB" else args.toToken

    if args.amount.lower() == "all":
        qty = get_token_balance(from_addr)
        if qty <= 0:
            print(f"Error: Token balance for {from_addr} is 0 or not found.")
            sys.exit(1)
        amount_str = str(qty)
    else:
        amount_str = str(args.amount)

    print(f"=== Quoting Swap: {amount_str} from {from_addr} -> {to_addr} ===")
    quote_cmd = [
        BAW_CMD, "market-order", "quote",
        "--binanceChainId", CHAIN_ID,
        "--fromToken", from_addr,
        "--toToken", to_addr,
        "--fromTokenQty", amount_str,
        "--json"
    ]
    res_q = subprocess.run(quote_cmd, capture_output=True, text=True)
    if res_q.returncode == 0:
        q_data = json.loads(res_q.stdout)
        if q_data.get("success"):
            out_amt = q_data["data"].get("toCoinAmount")
            print(f"Quote received: Expected output = {out_amt} {args.toToken.upper()}")
        else:
            print(f"Quote warning: {q_data.get('error')}")

    print("=== Executing Market Order Swap ===")
    swap_cmd = [
        BAW_CMD, "market-order", "swap",
        "--binanceChainId", CHAIN_ID,
        "--fromToken", from_addr,
        "--toToken", to_addr,
        "--fromTokenQty", amount_str,
        "--json"
    ]
    if args.slippage != "auto":
        swap_cmd.extend(["--slippage", str(args.slippage)])

    res_s = subprocess.run(swap_cmd, capture_output=True, text=True)
    if res_s.returncode == 0:
        s_data = json.loads(res_s.stdout)
        if s_data.get("success"):
            order_id = s_data["data"].get("orderId")
            print(f"SUCCESS! Swap Order Broadcasted. Order ID: {order_id}")
            # Check market-order list
            list_cmd = [BAW_CMD, "market-order", "list", "--binanceChainId", CHAIN_ID, "--json"]
            res_l = subprocess.run(list_cmd, capture_output=True, text=True)
            if res_l.returncode == 0:
                l_data = json.loads(res_l.stdout)
                for order in l_data.get("data", {}).get("list", [])[:3]:
                    if order.get("orderId") == order_id:
                        print(f"Status: {order.get('status')} | TxHash: {order.get('txHash')} | Out: {order.get('toTokenActualQty')} BNB")
                        break
        else:
            print(f"Swap Failed: {s_data.get('error')}")
    else:
        print(f"Command Error: {res_s.stderr}")

if __name__ == "__main__":
    main()
