#!/usr/bin/env python3
"""
Binance AI Agent Smart Sniper Daemon v3.2
Autonomous sniper with >10 Wallets Consensus, Fast LP Polling & Instant BNB Dump.
"""

import sys
import json
import time
import subprocess
import os
import shutil
import urllib.request
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUNDLE_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(BUNDLE_ROOT, "data")
LOGS_DIR = os.path.join(BUNDLE_ROOT, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Load configuration if present
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

# Resolve baw executable
BAW_CMD = shutil.which("baw") or shutil.which("baw.cmd") or "baw"

# Tokens & DEX
BNB_ADDRESS = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
WBNB_ADDRESS = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
USDT_ADDRESS = "0x55d398326f99059fF775485246999027B3197955"
PANCAKE_FACTORY = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"

# Safety & Consensus Parameters
MIN_BNB_GAS_FLOOR = config.get("min_bnb_gas_floor", 0.0015)  # Stop minting if BNB < 0.0015
REQUIRED_CONSENSUS = config.get("required_consensus", 11)   # Strictly > 10 distinct wallets
CONSENSUS_WINDOW_SEC = config.get("consensus_window_sec", 3600)
FAST_WATCH_DURATION_SEC = 2700  # Poll LP reserves for 45 minutes

# Load tracked wallets (4,942 smart wallets)
WALLETS_PATH = os.path.join(DATA_DIR, "smart_wallets_list.json")
if os.path.exists(WALLETS_PATH):
    with open(WALLETS_PATH, "r", encoding="utf-8") as f:
        TRACKED_WALLETS = set(w.lower() for w in json.load(f))
else:
    TRACKED_WALLETS = set()

# Known minted or system contracts
KNOWN_MINTED = {
    "0x2bbad2A3421a0BBd62A319a9Db70122047839483".lower(), # Cogladius
    "0x5eB9936F910b1cFaA9994fbC7Ae98A279A3d0F89".lower(), # Moribundus
    "0x4515787b43D930CE6AF3B446FCB19C77513da281".lower(), # Wuse Pass
    "0x2dc57b951a42b7d86449cd7928dcbab67867a780".lower(), # StonkRobo
    "0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F".lower(), # Space ID
    "0x6b1D77D3DeDE3FC775ca8C7BDe08C2C2EAAb9BEA".lower(), # Hirelings
    "0x7638Bf791c601152A0E21899B1192cf2F7fe2348".lower(), # Printer Ai
    "0x6884D40B10c55A6c2faB2D3c829d41c3C798279D".lower(), # Hash21 Pool
    "0xa2556377118dD333F9f09600DE0bBCf54Cbc69A0".lower(), # Ptah IAO Offering
}

FAILED_CANDIDATES = set()
CANDIDATE_TIMESTAMPS = defaultdict(list)
ACTIVE_FAST_WATCH = {}

LOG_FILE = os.path.join(LOGS_DIR, "sniper_activity.log")
HISTORY_FILE = os.path.join(LOGS_DIR, "auto_mints_history.json")

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{ts}] {msg}"
    try:
        print(formatted, flush=True)
    except Exception:
        pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def save_history(record):
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    history.append(record)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def eth_rpc(method, params):
    data = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode('utf-8')
    req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

def get_bnb_balance(wallet):
    res = eth_rpc("eth_getBalance", [wallet, "latest"])
    if "result" in res:
        return int(res["result"], 16) / 1e18
    return 0.0

def get_pancake_pair(token_a, token_b):
    pad_a = token_a[2:].lower().rjust(64, '0')
    pad_b = token_b[2:].lower().rjust(64, '0')
    calldata = "0xe6a43905" + pad_a + pad_b
    res = eth_rpc("eth_call", [{"to": PANCAKE_FACTORY, "data": calldata}, "latest"])
    if "result" in res and res["result"] != "0x" and len(res["result"]) >= 66:
        addr = "0x" + res["result"][-40:]
        if addr != "0x0000000000000000000000000000000000000000":
            return addr
    return None

def get_pair_reserves(pair_address):
    calldata = "0x0902f1ac"
    res = eth_rpc("eth_call", [{"to": pair_address, "data": calldata}, "latest"])
    if "result" in res and res["result"] != "0x" and len(res["result"]) >= 130:
        raw = res["result"][2:]
        r0 = int(raw[0:64], 16)
        r1 = int(raw[64:128], 16)
        return r0, r1
    return 0, 0

def get_token_balance(token_address, wallet_address):
    pad_wallet = wallet_address[2:].lower().rjust(64, '0')
    calldata = "0x70a08231" + pad_wallet
    res = eth_rpc("eth_call", [{"to": token_address, "data": calldata}, "latest"])
    if "result" in res and res["result"] != "0x":
        return int(res["result"], 16)
    return 0

def get_token_decimals(token_address):
    res = eth_rpc("eth_call", [{"to": token_address, "data": "0x313ce567"}, "latest"])
    if "result" in res and res["result"] != "0x":
        try:
            return int(res["result"], 16)
        except Exception:
            return 18
    return 18

def dump_token_to_bnb(token_address, balance_int, decimals, symbol="TOKEN"):
    amount_str = f"{balance_int / (10 ** decimals):.6f}".rstrip('0').rstrip('.')
    if not amount_str or float(amount_str) <= 0:
        return None
    log(f"⚡ [DUMP] Liquidity detected for {symbol} ({token_address[:10]}...). Dumping {amount_str} directly to BNB...")
    cmd = [
        BAW_CMD, "market-order", "swap",
        "--binanceChainId", CHAIN_ID,
        "--fromToken", token_address,
        "--toToken", BNB_ADDRESS,
        "--amount", amount_str,
        "--slippage", "10",
        "--json"
    ]
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
        out = json.loads(res.stdout)
        if out.get("success"):
            tx_hash = out.get("data", {}).get("transactionHash", "unknown")
            log(f"🎉 [DUMP SUCCESS] Sold {amount_str} {symbol} for BNB! Tx: {tx_hash}")
            return tx_hash
        else:
            log(f"⚠️ [DUMP FAIL] {symbol} swap rejected: {out.get('error') or out.get('message')}")
    except Exception as e:
        log(f"⚠️ [DUMP ERROR] Failed to dump {symbol}: {e}")
    return None

def check_liquidity_and_dump(token_address, symbol="NEW_TOKEN"):
    pair_bnb = get_pancake_pair(token_address, WBNB_ADDRESS)
    pair_usdt = get_pancake_pair(token_address, USDT_ADDRESS)
    has_liq = False
    
    if pair_bnb:
        r0, r1 = get_pair_reserves(pair_bnb)
        if r0 > 0 and r1 > 0:
            has_liq = True
    if pair_usdt:
        r0, r1 = get_pair_reserves(pair_usdt)
        if r0 > 0 and r1 > 0:
            has_liq = True
            
    if has_liq:
        bal = get_token_balance(token_address, USER_WALLET)
        if bal > 0:
            dec = get_token_decimals(token_address)
            dump_token_to_bnb(token_address, bal, dec, symbol)
            return True
    return False

def fast_watch_cycle():
    now = time.time()
    expired = []
    for token, info in list(ACTIVE_FAST_WATCH.items()):
        if now - info["start_time"] > FAST_WATCH_DURATION_SEC:
            expired.append(token)
            continue
        if check_liquidity_and_dump(token, info["symbol"]):
            expired.append(token)
    for t in expired:
        ACTIVE_FAST_WATCH.pop(t, None)

def simulate_and_mint(contract_address, raw_calldata):
    curr_bnb = get_bnb_balance(USER_WALLET)
    if curr_bnb < MIN_BNB_GAS_FLOOR:
        log(f"🛑 [GAS SHIELD] BNB Balance ({curr_bnb:.5f} BNB) is below floor ({MIN_BNB_GAS_FLOOR} BNB). Halting mint.")
        return False

    cmd = [
        BAW_CMD, "contract", "call",
        "--binanceChainId", CHAIN_ID,
        "--contractAddress", contract_address,
        "--calldata", raw_calldata,
        "--preview",
        "--json"
    ]
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15, encoding='utf-8', errors='ignore')
        out = json.loads(res.stdout)
        if not out.get("success"):
            return False
        gas_fee = float(out.get("data", {}).get("networkFee", {}).get("feeValue", "0")) / 1e18
        if gas_fee > 0.001:
            return False
    except Exception:
        return False

    exec_cmd = [
        BAW_CMD, "contract", "call",
        "--binanceChainId", CHAIN_ID,
        "--contractAddress", contract_address,
        "--calldata", raw_calldata,
        "--json"
    ]
    try:
        res = subprocess.run(exec_cmd, shell=True, capture_output=True, text=True, timeout=25, encoding='utf-8', errors='ignore')
        out = json.loads(res.stdout)
        if out.get("success"):
            tx_hash = out.get("data", {}).get("transactionHash", "unknown")
            log(f"🎉 [MINT SUCCESS] Minted {contract_address}! Tx: {tx_hash}")
            KNOWN_MINTED.add(contract_address.lower())
            save_history({"contract": contract_address, "txHash": tx_hash, "time": time.time()})
            ACTIVE_FAST_WATCH[contract_address.lower()] = {"symbol": "TOKEN", "start_time": time.time()}
            return True
    except Exception as e:
        log(f"❌ [MINT ERROR] {contract_address}: {e}")
    return False

def run_loop():
    log(f"🚀 Binance AI Agent Smart Sniper Daemon v3.2 active!")
    log(f"   • Wallet: {USER_WALLET}")
    log(f"   • Consensus Threshold: > 10 distinct smart wallets (> 10)")
    log(f"   • Gas Floor: {MIN_BNB_GAS_FLOOR} BNB")
    log(f"   • Auto Dump Destination: 100% directly to BNB")
    
    last_block = None
    last_sweep = time.time()
    
    while True:
        try:
            fast_watch_cycle()
            
            # Periodic sweep every 5 minutes
            if time.time() - last_sweep > 300:
                last_sweep = time.time()
                for token in list(KNOWN_MINTED):
                    check_liquidity_and_dump(token)

            block_res = eth_rpc("eth_blockNumber", [])
            if "result" not in block_res:
                time.sleep(2)
                continue
            curr_block = int(block_res["result"], 16)
            if last_block is None:
                last_block = curr_block - 1

            if curr_block > last_block:
                for b in range(last_block + 1, curr_block + 1):
                    b_data = eth_rpc("eth_getBlockByNumber", [hex(b), True])
                    txs = b_data.get("result", {}).get("transactions", [])
                    now = time.time()

                    for tx in txs:
                        from_addr = (tx.get("from") or "").lower()
                        to_addr = (tx.get("to") or "").lower()
                        val = int(tx.get("value", "0x0"), 16)

                        if from_addr in TRACKED_WALLETS and to_addr and val == 0:
                            if to_addr in KNOWN_MINTED or to_addr in FAILED_CANDIDATES:
                                continue
                            
                            # Update candidate consensus
                            records = [r for r in CANDIDATE_TIMESTAMPS[to_addr] if now - r["ts"] < CONSENSUS_WINDOW_SEC]
                            if not any(r["wallet"] == from_addr for r in records):
                                records.append({"wallet": from_addr, "ts": now})
                            CANDIDATE_TIMESTAMPS[to_addr] = records

                            distinct_count = len(records)
                            if distinct_count >= REQUIRED_CONSENSUS:
                                log(f"🎯 [CONSENSUS HIT] Contract {to_addr} reached {distinct_count} wallets! Simulating...")
                                calldata = tx.get("input", "0x")
                                ok = simulate_and_mint(to_addr, calldata)
                                if not ok:
                                    FAILED_CANDIDATES.add(to_addr)

                last_block = curr_block
            time.sleep(3)
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    run_loop()
