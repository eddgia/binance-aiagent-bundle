#!/usr/bin/env python3
"""
Ptah Trade IAO Manager
Query Initial Agent Offering state, check airdrop eligibility, claim status, and PancakeSwap liquidity.
"""

import sys
import json
import time
import os
import urllib.request
import subprocess
import shutil

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUNDLE_ROOT = os.path.dirname(BASE_DIR)

CONFIG_PATH = os.path.join(BUNDLE_ROOT, "config.json")
config = {}
if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        pass

RPC_URL = config.get("rpc_url", "https://bsc-dataseed.binance.org")
USER_WALLET = config.get("wallet_address", "0x0C1D734cA7cD3Ae50A03D18a6913cD5Ee6A285d7")
CHAIN_ID = config.get("binance_chain_id", "56")

IAO_TOKEN = "0x0810c5eb5d86d1B8D408F75Bd1f5ABeFb6d79999"
IAO_OFFERING = "0xa2556377118dD333F9f09600DE0bBCf54Cbc69A0"
PANCAKE_FACTORY = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
USDT = "0x55d398326f99059fF775485246999027B3197955"

BAW_CMD = shutil.which("baw") or shutil.which("baw.cmd") or "baw"

def eth_rpc(method, params):
    data = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode('utf-8')
    req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

def eth_call(to, data):
    res = eth_rpc("eth_call", [{"to": to, "data": data}, "latest"])
    return res.get("result")

def check_iao_status(wallet=USER_WALLET):
    print("=" * 60)
    print("       PTAH TRADE - INITIAL AGENT OFFERING (IAO) AUDIT")
    print("=" * 60)
    
    tot_res = eth_call(IAO_OFFERING, "0x40023408")
    total_bnb = int(tot_res, 16) / 1e18 if tot_res and tot_res != "0x" else 0.0
    
    end_res = eth_call(IAO_OFFERING, "0xefbe1c1c")
    end_ts = int(end_res, 16) if end_res and end_res != "0x" else 0
    rem_sec = max(0, int(end_ts - time.time()))
    
    closed_res = eth_call(IAO_OFFERING, "0x6bb0473a")
    is_closed = int(closed_res, 16) if closed_res and closed_res != "0x" else 0
    
    print(f"Offering Address:   {IAO_OFFERING}")
    print(f"Total Presale BNB:  {total_bnb:,.2f} BNB (~${total_bnb*700:,.0f} USD)")
    print(f"Time Remaining:     {rem_sec // 60}m {rem_sec % 60}s")
    print(f"Offering Closed:    {'YES' if is_closed else 'NO (Still Open)'}")
    print("-" * 60)
    
    padded_wallet = wallet[2:].lower().rjust(64, '0')
    reg_res = eth_call(IAO_OFFERING, "0xc3c5a547" + padded_wallet)
    is_reg = int(reg_res, 16) if reg_res and reg_res != "0x" else 0
    
    claimed_res = eth_call(IAO_OFFERING, "0xd1b6dd30" + padded_wallet)
    is_claimed = int(claimed_res, 16) if claimed_res and claimed_res != "0x" else 0
    
    bal_res = eth_call(IAO_TOKEN, "0x70a08231" + padded_wallet)
    bal_iao = int(bal_res, 16) / 1e18 if bal_res and bal_res != "0x" else 0.0
    
    print(f"Target Wallet:      {wallet}")
    print(f"Registered:         {'YES' if is_reg else 'NO'}")
    print(f"Airdrop Claimed:    {'YES (Already Claimed)' if is_claimed else 'NO (Ready to Claim)'}")
    print(f"IAO Wallet Balance: {bal_iao:,.2f} IAO")
    print("-" * 60)
    
    def get_pair(t0, t1):
        p0 = t0[2:].lower().rjust(64, '0')
        p1 = t1[2:].lower().rjust(64, '0')
        r = eth_call(PANCAKE_FACTORY, "0xe6a43905" + p0 + p1)
        if r and len(r) >= 66:
            a = "0x" + r[-40:]
            if a != "0x0000000000000000000000000000000000000000":
                return a
        return None
        
    pair_bnb = get_pair(IAO_TOKEN, WBNB)
    pair_usdt = get_pair(IAO_TOKEN, USDT)
    print(f"Pancake WBNB Pair:  {pair_bnb or 'None'}")
    print(f"Pancake USDT Pair:  {pair_usdt or 'None'}")
    print("=" * 60)

def claim_airdrop():
    print(f"Simulating claimAirdrop() for {USER_WALLET}...")
    preview_cmd = [
        BAW_CMD, "contract-call", "preview",
        "--binanceChainId", CHAIN_ID,
        "--from", USER_WALLET,
        "--to", IAO_OFFERING,
        "--value", "0",
        "--inputData", "0x5b88349d",
        "--json"
    ]
    res = subprocess.run(preview_cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
    try:
        data = json.loads(res.stdout)
        if not data.get("success"):
            print("❌ Preview failed:", data.get("error") or data.get("message"))
            return
        req_id = data.get("data", {}).get("requestId")
        print(f"✅ Preview clean! RequestId: {req_id}. Executing claim...")
        exec_cmd = [
            BAW_CMD, "contract-call", "execute",
            "--binanceChainId", CHAIN_ID,
            "--requestId", req_id,
            "--json"
        ]
        exec_res = subprocess.run(exec_cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=25)
        print("Execution result:", exec_res.stdout)
    except Exception as e:
        print("Claim exception:", e)

if __name__ == "__main__":
    wallet = sys.argv[1] if len(sys.argv) > 1 else USER_WALLET
    check_iao_status(wallet)
