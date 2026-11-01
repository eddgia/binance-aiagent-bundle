#!/usr/bin/env python3
"""
Binance AI Agent Smart Sniper Daemon v3.2 (Production / Battle-Tested)
Autonomous sniper with >10 Wallets Consensus, Fast LP Polling, Drainer Guard & Instant BNB Dump.
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

# Dynamic BAW CLI resolution
BAW_CMD = shutil.which("baw") or shutil.which("baw.cmd") or "baw"

# Tokens & DEX
BNB_ADDRESS = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
WBNB_ADDRESS = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
USDT_ADDRESS = "0x55d398326f99059fF775485246999027B3197955"
PANCAKE_FACTORY = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"

# Safety Parameters
MIN_BNB_GAS_FLOOR = config.get("safety", {}).get("min_bnb_gas_floor", 0.0015)
REQUIRED_CONSENSUS = config.get("sniper", {}).get("required_consensus", 11)
CONSENSUS_WINDOW_SEC = config.get("sniper", {}).get("consensus_window_sec", 3600)
FAST_WATCH_DURATION_SEC = config.get("sniper", {}).get("fast_watch_duration_sec", 2700)

WALLETS_PATH = os.path.join(DATA_DIR, "smart_wallets_list.json")
if os.path.exists(WALLETS_PATH):
    with open(WALLETS_PATH, "r", encoding="utf-8") as f:
        TRACKED_WALLETS = set(w.lower() for w in json.load(f))
else:
    TRACKED_WALLETS = set()

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

FAILED_CONTRACTS = set()
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

def rpc(method, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
    req = urllib.request.Request(RPC_URL, data=payload, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())["result"]

def get_bnb_balance():
    try:
        res = rpc("eth_getBalance", [USER_WALLET, "latest"])
        return int(res, 16) / 10**18
    except Exception as e:
        return 0.0

class ConsensusTracker:
    def __init__(self, required=REQUIRED_CONSENSUS, window=CONSENSUS_WINDOW_SEC):
        self.required = required
        self.window = window
        self.candidates = defaultdict(dict)
        self.payloads = {}

    def record(self, contract_addr, source_wallet, input_data):
        now = time.time()
        ca = contract_addr.lower()
        sw = source_wallet.lower()
        self.candidates[ca] = {w: ts for w, ts in self.candidates[ca].items() if now - ts <= self.window}
        self.candidates[ca][sw] = now
        self.payloads[ca] = input_data
        count = len(self.candidates[ca])
        return (count >= self.required), count, self.payloads[ca]

tracker = ConsensusTracker()

def run_baw_preview(to, input_data, value="0"):
    cmd = [
        BAW_CMD, "contract-call", "preview",
        "--binanceChainId", CHAIN_ID,
        "--from", USER_WALLET,
        "--to", to,
        "--value", str(value),
        "--inputData", input_data,
        "--json"
    ]
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
        if res.returncode == 0:
            return json.loads(res.stdout)
    except Exception as e:
        log(f"Preview exception: {e}")
    return None

def run_baw_execute(request_id):
    cmd = [
        BAW_CMD, "contract-call", "execute",
        "--binanceChainId", CHAIN_ID,
        "--requestId", request_id,
        "--json"
    ]
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=25)
        if res.returncode == 0:
            return json.loads(res.stdout)
    except Exception as e:
        log(f"Execute exception: {e}")
    return None

def check_pancake_lp_reserves(token_addr):
    try:
        for quote_token in [WBNB_ADDRESS, USDT_ADDRESS]:
            pad_a = token_addr[2:].lower().rjust(64, '0')
            pad_b = quote_token[2:].lower().rjust(64, '0')
            calldata = "0xe6a43905" + pad_a + pad_b
            pair_res = rpc("eth_call", [{"to": PANCAKE_FACTORY, "data": calldata}, "latest"])
            if pair_res and pair_res != "0x" and len(pair_res) >= 66:
                pair_addr = "0x" + pair_res[-40:]
                if pair_addr != "0x0000000000000000000000000000000000000000":
                    reserves_data = rpc("eth_call", [{"to": pair_addr, "data": "0x0902f1ac"}, "latest"])
                    if reserves_data and len(reserves_data) >= 130:
                        raw = reserves_data[2:]
                        r0 = int(raw[0:64], 16)
                        r1 = int(raw[64:128], 16)
                        if r0 > 0 and r1 > 0:
                            return r0 + r1, pair_addr
        return 0, None
    except Exception:
        return 0, None

def auto_dump_token_to_bnb(token_addr):
    """Immediately sells entire balance of token to BNB to replenish gas."""
    try:
        padded = USER_WALLET[2:].lower().rjust(64, '0')
        res_d = rpc("eth_call", [{"to": token_addr, "data": "0x313ce567"}, "latest"])
        dec = int(res_d, 16) if res_d and res_d != "0x" else 18

        res_b = rpc("eth_call", [{"to": token_addr, "data": "0x70a08231" + padded}, "latest"])
        bal_int = int(res_b, 16) if res_b and res_b != "0x" else 0
        if bal_int == 0:
            return False

        qty_str = str(bal_int / (10**dec))
        if '.' in qty_str:
            qty_str = qty_str.rstrip('0').rstrip('.')

        quote_cmd = [
            BAW_CMD, "market-order", "quote",
            "--binanceChainId", CHAIN_ID,
            "--fromToken", token_addr,
            "--toToken", BNB_ADDRESS,
            "--fromTokenQty", qty_str,
            "--json"
        ]
        q_res = subprocess.run(quote_cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=12)
        if q_res.returncode == 0:
            q_data = json.loads(q_res.stdout)
            if q_data.get("success"):
                to_bnb = float(q_data.get("data", {}).get("toCoinAmount", 0))
                sym = q_data.get("data", {}).get("fromCoinSymbol", token_addr)
                if to_bnb > 0.0001:
                    log(f"🔥 [INSTANT LP DETECTED] {qty_str} {sym} -> {to_bnb:.6f} BNB! Executing INSTANT DUMP to BNB...")
                    swap_cmd = [
                        BAW_CMD, "market-order", "swap",
                        "--binanceChainId", CHAIN_ID,
                        "--fromToken", token_addr,
                        "--toToken", BNB_ADDRESS,
                        "--fromTokenQty", qty_str,
                        "--slippage", "10",
                        "--json"
                    ]
                    s_res = subprocess.run(swap_cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20)
                    if s_res.returncode == 0:
                        s_data = json.loads(s_res.stdout)
                        if s_data.get("success"):
                            ord_id = s_data.get("data", {}).get("orderId")
                            log(f"✅ [INSTANT DUMP SUCCESS] Sold {qty_str} {sym} to BNB! OrderId: {ord_id}")
                            return True
        return False
    except Exception as e:
        log(f"[AUTO-DUMP ERROR] {token_addr}: {e}")
        return False

def fast_lp_watch_loop():
    now = time.time()
    expired = []
    dumped = []

    for t_addr, meta in list(ACTIVE_FAST_WATCH.items()):
        if now - meta['minted_at'] > FAST_WATCH_DURATION_SEC:
            expired.append(t_addr)
            continue

        if now - meta.get('last_check', 0) < 4:
            continue

        meta['last_check'] = now
        reserves, pair = check_pancake_lp_reserves(t_addr)
        if reserves > 0:
            log(f"⚡ [LP OPENED ON PANCAKE] Token {t_addr} has live reserves in pair {pair}! Dumping to BNB...")
            success = auto_dump_token_to_bnb(t_addr)
            if success:
                dumped.append(t_addr)

    for e in expired:
        ACTIVE_FAST_WATCH.pop(e, None)
    for d in dumped:
        ACTIVE_FAST_WATCH.pop(d, None)

def periodic_liquidity_sweep():
    try:
        cmd = [BAW_CMD, "wallet", "balance", "--json"]
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            if data.get("success"):
                items = data.get("data", [])
                for it in items:
                    addr = it.get("address")
                    val = float(it.get("value", 0))
                    if val > 0.05 and addr and addr.lower() not in [BNB_ADDRESS.lower(), WBNB_ADDRESS.lower()]:
                        auto_dump_token_to_bnb(addr)
    except Exception:
        pass

def handle_candidate(to_addr, input_data, consensus_count, source_wallet):
    to_lower = to_addr.lower()
    if to_lower in KNOWN_MINTED or to_lower in FAILED_CONTRACTS:
        return

    current_bnb = get_bnb_balance()
    if current_bnb < MIN_BNB_GAS_FLOOR:
        log(f"[GAS SHIELD BLOCKED] Current BNB {current_bnb:.5f} < {MIN_BNB_GAS_FLOOR} BNB. Skipping mint to preserve gas!")
        return

    log(f"🎯 [HIGH-CONVICTION TARGET] Contract: {to_addr} | Consensus: {consensus_count} smart wallets | Triggered by: {source_wallet[:10]}...")

    preview_res = run_baw_preview(to_addr, input_data, value="0")
    if not preview_res or not preview_res.get("success"):
        FAILED_CONTRACTS.add(to_lower)
        log(f"[FAIL] Candidate {to_addr} simulation failed or rejected.")
        return

    data = preview_res.get("data", {})
    sim = data.get("simulationResult", {})
    risks = data.get("risks", {})
    authority_changes = sim.get("authorityChanges", [])
    allowance_changes = sim.get("allowanceChanges", [])
    sim_code = sim.get("simulationCode")
    req_id = data.get("requestId")

    if sim_code != "000000000":
        FAILED_CONTRACTS.add(to_lower)
        log(f"[FAIL] Sim code {sim_code} != 000000000 for {to_addr}")
        return

    if len(authority_changes) > 0 or len(allowance_changes) > 0:
        FAILED_CONTRACTS.add(to_lower)
        log(f"[DRAINER GUARD BLOCK] Authority/allowance change on {to_addr}! Blocked.")
        return

    if len(risks.get("riskDetails", [])) > 0 or len(risks.get("riskBehaviors", [])) > 0:
        FAILED_CONTRACTS.add(to_lower)
        log(f"[SECURITY BLOCK] Risks flagged on {to_addr}! Blocked.")
        return

    balance_changes = sim.get("balanceChanges", [])
    log(f"[CLEAN] Simulation 100% CLEAN! Balance changes: {len(balance_changes)}. Executing mint...")

    exec_res = run_baw_execute(req_id)
    if exec_res and exec_res.get("success"):
        tx_h = exec_res.get("data", {}).get("txHash")
        log(f"🚀 [SUCCESSFUL HIGH-CONSENSUS MINT] Contract: {to_addr} | Tx: {tx_h}")
        KNOWN_MINTED.add(to_lower)

        ACTIVE_FAST_WATCH[to_lower] = {
            "minted_at": time.time(),
            "last_check": 0,
            "tx_hash": tx_h
        }

def run_loop():
    log(f"🚀 Binance AI Agent Smart Sniper Daemon v3.2 active!")
    log(f"   • Wallet: {USER_WALLET}")
    log(f"   • Consensus Threshold: > 10 distinct smart wallets ({REQUIRED_CONSENSUS} wallets)")
    log(f"   • Gas Protection Floor: {MIN_BNB_GAS_FLOOR} BNB")
    log(f"   • Auto-Dump Target: 100% to BNB ({BNB_ADDRESS})")
    
    last_block = None
    last_sweep = time.time()

    while True:
        try:
            fast_lp_watch_loop()

            if time.time() - last_sweep > 300:
                last_sweep = time.time()
                periodic_liquidity_sweep()

            curr_block_hex = rpc("eth_blockNumber", [])
            curr_block = int(curr_block_hex, 16)
            if last_block is None:
                last_block = curr_block - 1

            if curr_block > last_block:
                for b in range(last_block + 1, curr_block + 1):
                    block_data = rpc("eth_getBlockByNumber", [hex(b), True])
                    txs = block_data.get("transactions", [])
                    for tx in txs:
                        from_a = (tx.get("from") or "").lower()
                        to_a = (tx.get("to") or "").lower()
                        val = int(tx.get("value", "0x0"), 16)

                        if from_a in TRACKED_WALLETS and to_a and val == 0:
                            inp = tx.get("input", "")
                            if len(inp) >= 10:
                                ready, count, payload = tracker.record(to_a, from_a, inp)
                                if ready:
                                    handle_candidate(to_a, payload, count, from_a)
                last_block = curr_block
            time.sleep(2)
        except Exception:
            time.sleep(2)

if __name__ == "__main__":
    run_loop()
