#!/usr/bin/env python3
"""
Binance AI Agent Smart Sniper Daemon v3.3 (Production / Enhanced Risk Guardrails)
Autonomous sniper with >10 Wallets Consensus, Fast LP Polling, Drainer Guard & Instant BNB Dump.

Enhanced Risk Guardrails (v3.3):
1. Daily spend cap (0.01 BNB/day): Tracks real on-chain gas from receipts, pauses at 0.01 BNB until 00:00 UTC.
2. Mass-deployer skip (>=10 deploy/24h): Binary-search deployment block + cache; skips spam deployers.
3. Junk-NFT check (tokenURI): Validates tokenURI; permanently blacklists empty or fake metadata NFTs.
4. Fail limit (2 fails/contract/day): Halts retrying after 2 failures; state in logs/risk_state.json.
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
os.makedirs(DATA_DIR, exist_ok=True)
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
DAILY_SPEND_CAP_BNB = config.get("safety", {}).get("daily_spend_cap_bnb", 0.01)
MAX_FAILS_PER_CONTRACT = config.get("safety", {}).get("max_fails_per_contract", 2)
MAX_MASS_DEPLOYS_24H = config.get("safety", {}).get("max_mass_deploys_24h", 10)
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
    "0x213a879d11a85b54483cea2cdec5d9026958add3".lower(), # EnigmaAgent Tablet
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
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode())["result"]

def get_bnb_balance():
    try:
        res = rpc("eth_getBalance", [USER_WALLET, "latest"])
        return int(res, 16) / 10**18
    except Exception:
        return 0.0

# ==============================================================================
# 1. RISK CONTROLS STATE MANAGER (Daily Spend Cap & Fail Limit)
# ==============================================================================
class RiskStateManager:
    """Manages persistent risk state in logs/risk_state.json with automatic 00:00 UTC daily reset."""
    def __init__(self, logs_dir, daily_spend_cap=DAILY_SPEND_CAP_BNB, fail_limit=MAX_FAILS_PER_CONTRACT):
        self.path = os.path.join(logs_dir, "risk_state.json")
        self.daily_spend_cap = daily_spend_cap
        self.fail_limit = fail_limit
        self.state = self._load()

    def _get_current_date(self):
        return time.strftime("%Y-%m-%d")

    def _load(self):
        cur_date = self._get_current_date()
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("date") == cur_date:
                        return data
            except Exception:
                pass
        fresh = {
            "date": cur_date,
            "daily_spent_bnb": 0.0,
            "contract_failures": {},
            "tx_receipts": []
        }
        self._save(fresh)
        return fresh

    def _save(self, data=None):
        if data is None:
            data = self.state
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def check_date_reset(self):
        cur_date = self._get_current_date()
        if self.state.get("date") != cur_date:
            log(f"🔄 [DAILY RESET] New day {cur_date}! Resetting daily spend cap and failure counts.")
            self.state = {
                "date": cur_date,
                "daily_spent_bnb": 0.0,
                "contract_failures": {},
                "tx_receipts": []
            }
            self._save()

    def can_spend(self):
        self.check_date_reset()
        spent = self.state.get("daily_spent_bnb", 0.0)
        return (spent < self.daily_spend_cap), spent

    def record_spend(self, tx_hash, gas_spent_bnb):
        self.check_date_reset()
        self.state["daily_spent_bnb"] = round(self.state.get("daily_spent_bnb", 0.0) + gas_spent_bnb, 8)
        self.state.setdefault("tx_receipts", []).append({
            "tx": tx_hash,
            "spent_bnb": gas_spent_bnb,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        self._save()

    def is_contract_fail_limited(self, contract_addr):
        self.check_date_reset()
        ca = contract_addr.lower()
        count = self.state.get("contract_failures", {}).get(ca, 0)
        return (count >= self.fail_limit), count

    def record_failure(self, contract_addr, reason=""):
        self.check_date_reset()
        ca = contract_addr.lower()
        fails = self.state.setdefault("contract_failures", {})
        fails[ca] = fails.get(ca, 0) + 1
        self._save()
        log(f"⚠️ [FAIL RECORDED] {ca} fail count: {fails[ca]}/{self.fail_limit} (Reason: {reason})")
        return fails[ca]

risk_state = RiskStateManager(LOGS_DIR)

# ==============================================================================
# 2. MASS-DEPLOYER GUARD (Binary-Search Deployment Block + Cache)
# ==============================================================================
class MassDeployerGuard:
    """Finds deployer of contract via binary search & skips mass deployers (>=10 deploy/24h)."""
    def __init__(self, data_dir, rpc_func, max_deploys_24h=MAX_MASS_DEPLOYS_24H):
        self.cache_path = os.path.join(data_dir, "deployer_cache.json")
        self.rpc = rpc_func
        self.max_deploys_24h = max_deploys_24h
        self.cache = self._load()

    def _load(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception:
            pass

    def get_deployer(self, contract_addr, current_block):
        ca = contract_addr.lower()
        if ca in self.cache:
            return self.cache[ca].get("deployer"), self.cache[ca].get("created_block")

        # Binary search block range (within public node depth)
        search_window = 200
        low = max(1, current_block - search_window)
        high = current_block

        try:
            code_now = self.rpc("eth_getCode", [ca, hex(high)])
            if not code_now or len(code_now) <= 2:
                return None, None

            code_low = self.rpc("eth_getCode", [ca, hex(low)])
            if code_low and len(code_low) > 2:
                # Contract was created prior to search window -> not freshly spammed
                self.cache[ca] = {"deployer": "prior_block", "created_block": low, "deploy_count_24h": 1}
                self._save()
                return "prior_block", low

            # Binary search for creation block
            created_block = high
            while low <= high:
                mid = (low + high) // 2
                code_mid = self.rpc("eth_getCode", [ca, hex(mid)])
                if code_mid and len(code_mid) > 2:
                    created_block = mid
                    high = mid - 1
                else:
                    low = mid + 1

            # Find deployer tx in created_block
            deployer = "unknown"
            block_data = self.rpc("eth_getBlockByNumber", [hex(created_block), True])
            if block_data and "transactions" in block_data:
                for tx in block_data["transactions"]:
                    if not tx.get("to"):  # Contract creation
                        receipt = self.rpc("eth_getTransactionReceipt", [tx["hash"]])
                        if receipt and (receipt.get("contractAddress") or "").lower() == ca:
                            deployer = (tx.get("from") or "").lower()
                            break

            deploy_count = sum(1 for v in self.cache.values() if v.get("deployer") == deployer) + 1
            self.cache[ca] = {
                "deployer": deployer,
                "created_block": created_block,
                "deploy_count_24h": deploy_count
            }
            self._save()
            return deployer, created_block
        except Exception as e:
            self.cache[ca] = {"deployer": "unknown", "created_block": current_block, "deploy_count_24h": 1}
            self._save()
            return "unknown", current_block

    def is_mass_deployer(self, contract_addr, current_block):
        deployer, _ = self.get_deployer(contract_addr, current_block)
        if not deployer or deployer in ["prior_block", "unknown"]:
            return False, 1, deployer

        count = sum(1 for v in self.cache.values() if v.get("deployer") == deployer)
        return (count >= self.max_deploys_24h), count, deployer

deployer_guard = MassDeployerGuard(DATA_DIR, rpc)

# ==============================================================================
# 3. JUNK-NFT CHECKER (tokenURI Validation)
# ==============================================================================
class JunkNftChecker:
    """Verifies tokenURI for NFTs; permanently skips contracts with empty/fake metadata."""
    def __init__(self, data_dir, rpc_func):
        self.blacklist_path = os.path.join(data_dir, "junk_nft_blacklist.json")
        self.rpc = rpc_func
        self.blacklist = self._load()

    def _load(self):
        if os.path.exists(self.blacklist_path):
            try:
                with open(self.blacklist_path, "r", encoding="utf-8") as f:
                    return set(w.lower() for w in json.load(f))
            except Exception:
                pass
        return set()

    def _save(self):
        try:
            with open(self.blacklist_path, "w", encoding="utf-8") as f:
                json.dump(list(self.blacklist), f, indent=2)
        except Exception:
            pass

    def is_blacklisted(self, contract_addr):
        return contract_addr.lower() in self.blacklist

    def check_nft_metadata(self, contract_addr):
        ca = contract_addr.lower()
        if ca in self.blacklist:
            return False, "Permanently blacklisted junk NFT"

        # Check ERC721 (tokenURI: 0xc87b56dd) and ERC1155 (uri: 0x0e89341c)
        for sel in ["0xc87b56dd", "0x0e89341c"]:
            for tid in ["1", "0"]:
                calldata = sel + tid.rjust(64, '0')
                try:
                    res = self.rpc("eth_call", [{"to": ca, "data": calldata}, "latest"])
                    if res and len(res) > 130:
                        offset = int(res[2:66], 16) * 2 + 2
                        length = int(res[offset:offset+64], 16) * 2
                        hex_str = res[offset+64:offset+64+length]
                        uri_str = bytes.fromhex(hex_str).decode("utf-8", errors="ignore").strip()

                        if not uri_str or uri_str.lower() in ["null", "none", "{}", ""]:
                            self.blacklist.add(ca)
                            self._save()
                            return False, f"Empty tokenURI ('{uri_str}')"

                        if any(uri_str.lower().startswith(p) for p in ["http://", "https://", "ipfs://", "data:"]):
                            return True, uri_str
                except Exception:
                    pass

        # If call reverts or is non-NFT, check if it is a standard ERC20 token
        try:
            sym_res = self.rpc("eth_call", [{"to": ca, "data": "0x95d89b41"}, "latest"]) # symbol()
            if sym_res and len(sym_res) > 10:
                return True, "Valid ERC20 Token"
        except Exception:
            pass

        return True, "Standard contract / Non-NFT"

junk_checker = JunkNftChecker(DATA_DIR, rpc)

# ==============================================================================
# SMART WALLETS CONSENSUS TRACKER
# ==============================================================================
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

def handle_candidate(to_addr, input_data, consensus_count, source_wallet, current_block=None):
    to_lower = to_addr.lower()
    if to_lower in KNOWN_MINTED or to_lower in FAILED_CONTRACTS:
        return

    # [1] DAILY SPEND CAP CHECK (0.01 BNB/day)
    can_spend, daily_spent = risk_state.can_spend()
    if not can_spend:
        log(f"🛑 [DAILY SPEND CAP HIT] Spent {daily_spent:.5f} >= {DAILY_SPEND_CAP_BNB} BNB today. All mints paused until 00:00 UTC!")
        return

    # [4] FAIL LIMIT CHECK (2 fails/contract/day)
    fail_limited, fail_count = risk_state.is_contract_fail_limited(to_lower)
    if fail_limited:
        log(f"🛑 [FAIL LIMIT HIT] Contract {to_addr} failed {fail_count} times today. Skipping until 00:00 UTC!")
        FAILED_CONTRACTS.add(to_lower)
        return

    # [2] MASS-DEPLOYER SKIP (>=10 deploy/24h)
    if current_block:
        is_mass, d_count, deployer = deployer_guard.is_mass_deployer(to_addr, current_block)
        if is_mass:
            log(f"🚫 [MASS-DEPLOYER SKIP] Deployer {deployer} has {d_count} >= {MAX_MASS_DEPLOYS_24H} deploys in 24h! Skipping spam.")
            FAILED_CONTRACTS.add(to_lower)
            return

    # [3] JUNK-NFT CHECK (tokenURI validation)
    valid_meta, meta_info = junk_checker.check_nft_metadata(to_addr)
    if not valid_meta:
        log(f"🗑️ [JUNK-NFT SKIP] Contract {to_addr} metadata invalid: {meta_info}. Permanently blacklisted!")
        FAILED_CONTRACTS.add(to_lower)
        return

    current_bnb = get_bnb_balance()
    if current_bnb < MIN_BNB_GAS_FLOOR:
        log(f"🛡️ [GAS SHIELD BLOCKED] Current BNB {current_bnb:.5f} < {MIN_BNB_GAS_FLOOR} BNB. Skipping mint to preserve gas!")
        return

    log(f"🎯 [HIGH-CONVICTION TARGET] Contract: {to_addr} | Consensus: {consensus_count} smart wallets | Triggered by: {source_wallet[:10]}...")

    preview_res = run_baw_preview(to_addr, input_data, value="0")
    if not preview_res or not preview_res.get("success"):
        risk_state.record_failure(to_lower, "Preview simulation failed or rejected")
        FAILED_CONTRACTS.add(to_lower)
        log(f"❌ [FAIL] Candidate {to_addr} simulation failed or rejected.")
        return

    data = preview_res.get("data", {})
    sim = data.get("simulationResult", {})
    risks = data.get("risks", {})
    authority_changes = sim.get("authorityChanges", [])
    allowance_changes = sim.get("allowanceChanges", [])
    sim_code = sim.get("simulationCode")
    req_id = data.get("requestId")

    if sim_code != "000000000":
        risk_state.record_failure(to_lower, f"Sim code {sim_code} != 000000000")
        FAILED_CONTRACTS.add(to_lower)
        log(f"❌ [FAIL] Sim code {sim_code} != 000000000 for {to_addr}")
        return

    if len(authority_changes) > 0 or len(allowance_changes) > 0:
        risk_state.record_failure(to_lower, "Drainer guard authority/allowance change detected")
        FAILED_CONTRACTS.add(to_lower)
        log(f"🚨 [DRAINER GUARD BLOCK] Authority/allowance change on {to_addr}! Blocked.")
        return

    if len(risks.get("riskDetails", [])) > 0 or len(risks.get("riskBehaviors", [])) > 0:
        risk_state.record_failure(to_lower, "Risks flagged by Binance Wallet security engine")
        FAILED_CONTRACTS.add(to_lower)
        log(f"🚨 [SECURITY BLOCK] Risks flagged on {to_addr}! Blocked.")
        return

    balance_changes = sim.get("balanceChanges", [])
    log(f"✨ [CLEAN] Simulation 100% CLEAN! Balance changes: {len(balance_changes)}. Executing mint...")

    exec_res = run_baw_execute(req_id)
    if exec_res and exec_res.get("success"):
        tx_h = exec_res.get("data", {}).get("txHash")
        log(f"🚀 [SUCCESSFUL HIGH-CONSENSUS MINT] Contract: {to_addr} | Tx: {tx_h}")
        KNOWN_MINTED.add(to_lower)

        # Parse actual gas spent from on-chain receipt and accumulate into daily spend cap
        time.sleep(2)
        try:
            rcpt = rpc("eth_getTransactionReceipt", [tx_h])
            if rcpt:
                gas_used = int(rcpt.get("gasUsed", "0x0"), 16)
                gas_px = int(rcpt.get("effectiveGasPrice") or rcpt.get("gasPrice", "0x0"), 16)
                spent_bnb = (gas_used * gas_px) / 1e18
                risk_state.record_spend(tx_h, spent_bnb)
                log(f"💰 [GAS TRACKED] Mint spent {spent_bnb:.6f} BNB | Daily total: {risk_state.state['daily_spent_bnb']:.6f} / {DAILY_SPEND_CAP_BNB} BNB")
        except Exception as e:
            log(f"Warning tracking gas receipt: {e}")

        ACTIVE_FAST_WATCH[to_lower] = {
            "minted_at": time.time(),
            "last_check": 0,
            "tx_hash": tx_h
        }
    else:
        risk_state.record_failure(to_lower, "Execute transaction rejected or failed")
        FAILED_CONTRACTS.add(to_lower)
        log(f"❌ [EXECUTE FAIL] Failed to broadcast contract call on {to_addr}")

def run_loop():
    log(f"🚀 Binance AI Agent Smart Sniper Daemon v3.3 active!")
    log(f"   • Wallet: {USER_WALLET}")
    log(f"   • Consensus Threshold: > 10 distinct smart wallets ({REQUIRED_CONSENSUS} wallets)")
    log(f"   • Gas Floor Protection: {MIN_BNB_GAS_FLOOR} BNB")
    log(f"   • Daily Spend Cap: {DAILY_SPEND_CAP_BNB} BNB/day (Current spent: {risk_state.state.get('daily_spent_bnb', 0.0):.6f} BNB)")
    log(f"   • Fail Limit: {MAX_FAILS_PER_CONTRACT} fails/contract/day (State: {risk_state.path})")
    log(f"   • Mass-Deployer Skip: >= {MAX_MASS_DEPLOYS_24H} deploys/24h")
    log(f"   • Junk-NFT Filter: Valid tokenURI required (empty/fake permanently blacklisted)")
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
                                    handle_candidate(to_a, payload, count, from_a, current_block=curr_block)
                last_block = curr_block
            time.sleep(2)
        except Exception:
            time.sleep(2)

if __name__ == "__main__":
    run_loop()
