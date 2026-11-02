#!/usr/bin/env python3
"""
Binance AI Agent Portfolio & Price Sentinel v2.2 (Nancy v2.7.2 Approvals & Risk Integration)
Monitors active mining protocols (Hash21), dividend vaults (FAGENT PoA), IAO launch, PancakeSwap pools,
and runs background security watchdogs (ApprovalsWatchdog for compromised spenders).
"""

import sys
import json
import time
import os
import urllib.request
from Crypto.Hash import keccak

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUNDLE_ROOT = os.path.dirname(BASE_DIR)
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
PANCAKE_FACTORY_V2 = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
USDT = "0x55d398326f99059fF775485246999027B3197955"

# Monitored Protocols
HASH21_POOL = "0x6884D40B10c55A6c2faB2D3c829d41c3C798279D"
HASH21_PAIR = "0x8f581c63c41b5a1123139a43b982e136b0706165"
LEAF_TOKEN = "0xE9Be17e5995ff27f31F686E69D5B6a2c91E0e857"
ALTAR = "0x01a451256ac22070d4af503fa7fe03b7337273e0"
IAO_TOKEN = "0x0810c5eb5d86d1B8D408F75Bd1f5ABeFb6d79999"
IAO_OFFERING = "0xa2556377118dD333F9f09600DE0bBCf54Cbc69A0"
FAGENT_CARD = "0xD87ADb2E47979d6cb323896B1A9320E0dd132213"
FAGENT_VAULT = "0x773d4E6b70176D2cf41938F8FE6d7c7136015Bf8"
FIREBEARER_TOKEN = "0x8b47354E7b76B1970a0D06365c8244a810d37493"
QILIN_TOKEN = "0x4FB644959F79848674acc4a48D8a3d99fc767aC2"
QILIN_MINT = "0xbb77f247e6b57f4dcd09c5900b2ffc4250b6b88f"

LOG_FILE = os.path.join(LOGS_DIR, "portfolio_sentinel.log")

from risk_guards import ApprovalsWatchdog

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

def get_sel(sig):
    k = keccak.new(digest_bits=256)
    k.update(sig.encode('utf-8'))
    return "0x" + k.hexdigest()[:8]

def eth_call(to, calldata):
    data = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": to, "data": calldata}, "latest"]
    }).encode('utf-8')
    req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode())
            return res.get("result")
    except Exception:
        return None

def get_balance(addr):
    data = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getBalance",
        "params": [addr, "latest"]
    }).encode('utf-8')
    req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode())
            if "result" in res:
                return int(res["result"], 16) / 1e18
    except Exception:
        pass
    return 0.0

def get_pancake_pair(token_a, token_b):
    pad_a = token_a[2:].lower().rjust(64, '0')
    pad_b = token_b[2:].lower().rjust(64, '0')
    calldata = get_sel("getPair(address,address)") + pad_a + pad_b
    res = eth_call(PANCAKE_FACTORY_V2, calldata)
    if res and res != "0x" and len(res) >= 66:
        addr = "0x" + res[-40:]
        if addr != "0x0000000000000000000000000000000000000000":
            return addr
    return None

def get_reserves(pair_addr):
    calldata = get_sel("getReserves()")
    res = eth_call(pair_addr, calldata)
    if res and res != "0x" and len(res) >= 130:
        raw = res[2:]
        r0 = int(raw[0:64], 16)
        r1 = int(raw[64:128], 16)
        return r0, r1
    return 0, 0

def get_wbnb_price_usd():
    pair = get_pancake_pair(WBNB, USDT)
    if not pair:
        return 700.0
    r0, r1 = get_reserves(pair)
    if r0 == 0 or r1 == 0:
        return 700.0
    token0 = eth_call(pair, get_sel("token0()"))
    if token0 and token0.lower().endswith(WBNB[2:].lower()):
        return (r1 / 1e18) / (r0 / 1e18)
    else:
        return (r0 / 1e18) / (r1 / 1e18)

def check_hash21(wbnb_usd):
    pad_wallet = USER_WALLET[2:].lower().rjust(64, '0')
    res_pending = eth_call(HASH21_POOL, "0xf44136a1" + pad_wallet) # pendingOf(address)
    res_hash = eth_call(HASH21_POOL, "0x5d007281" + pad_wallet)    # hashOf(address)
    claimable_tokens = int(res_pending, 16) / 1e18 if res_pending and res_pending != "0x" else 0.0
    hash_power = int(res_hash, 16) / 1e18 if res_hash and res_hash != "0x" else 0.0

    r0, r1 = get_reserves(HASH21_PAIR)
    price_usd = 0.0
    liq_usd = 0.0
    if r0 > 0 and r1 > 0:
        token0 = eth_call(HASH21_PAIR, get_sel("token0()"))
        # HASH21_PAIR is USDT / HASH
        if token0 and token0.lower().endswith(USDT[2:].lower()):
            price_usd = (r0 / 1e18) / (r1 / 1e18)
            liq_usd = (r0 / 1e18) * 2
        else:
            price_usd = (r1 / 1e18) / (r0 / 1e18)
            liq_usd = (r1 / 1e18) * 2

    val_usd = claimable_tokens * price_usd
    log(f"[HASH21] Mining: {claimable_tokens:,.4f} HASH (Power: {hash_power:.0f} H) | Price: ${price_usd:.6f} | Liq: ${liq_usd:,.2f} | Value: ${val_usd:.4f}")

def check_iao(wbnb_usd):
    pair = get_pancake_pair(IAO_TOKEN, WBNB)
    total_dep_res = eth_call(IAO_OFFERING, get_sel("totalDeposited()"))
    total_bnb = 0.0
    if total_dep_res and total_dep_res != "0x":
        total_bnb = int(total_dep_res, 16) / 1e18

    end_res = eth_call(IAO_OFFERING, get_sel("end()"))
    rem_min = 0
    if end_res and end_res != "0x":
        end_ts = int(end_res, 16)
        rem_min = max(0, int((end_ts - time.time()) / 60))

    liq_str = "No Official Pool"
    if pair:
        r0, r1 = get_reserves(pair)
        if r0 > 0 and r1 > 0:
            liq_str = f"Pair Active ({r0/1e18:.2f} / {r1/1e18:.4f})"
    log(f"[PTAH IAO] Presale: {total_bnb:,.2f} BNB (${total_bnb*wbnb_usd:,.0f}) | Closes in: {rem_min} mins | LP: {liq_str}")

def check_fagent_vault():
    sel_total = get_sel("totalMinted()")
    res_card = eth_call(FAGENT_CARD, sel_total)
    curr_card = 0
    if res_card and res_card != "0x":
        curr_card = int(res_card, 16)
    vault_bnb = get_balance(FAGENT_VAULT)
    round4_progress = max(0, min(100.0, (curr_card - 28500) / 9500 * 100)) if curr_card >= 28500 else 0
    log(f"[FAGENT VAULT] Card #{curr_card:,} | R4 Progress: {round4_progress:.1f}% | Vault Pool: {vault_bnb:,.2f} BNB (~Target #38,000)")

def check_firebearer(wbnb_usd):
    try:
        pad_wallet = USER_WALLET[2:].lower().rjust(64, '0')
        bal_res = eth_call(FIREBEARER_TOKEN, get_sel("balanceOf(address)") + pad_wallet)
        bal = int(bal_res, 16) / 1e18 if bal_res and bal_res != "0x" else 0.0
        minted_res = eth_call(FIREBEARER_TOKEN, get_sel("freeMinted()"))
        minted = int(minted_res, 16) if minted_res and minted_res != "0x" else 0
        pair_res = eth_call(FIREBEARER_TOKEN, get_sel("pancakePair()"))
        pair = ("0x" + pair_res[-40:]) if pair_res and pair_res != "0x" and len(pair_res) >= 66 else None
        liq_res = eth_call(FIREBEARER_TOKEN, get_sel("liquidityAdded()"))
        liq_added = bool(int(liq_res, 16)) if liq_res and liq_res != "0x" else False
        
        status_lp = f"Minting {minted}/1,000 (No LP yet)"
        if liq_added and pair and pair != "0x0000000000000000000000000000000000000000":
            r0, r1 = get_reserves(pair)
            status_lp = f"LP Active ({pair[:10]}...)"
        log(f"[FIREBEARER] Balance: {bal:,.0f} 传火人 | Minted: {minted}/1,000 | Status: {status_lp}")
    except Exception as e:
        pass

def check_qilin(wbnb_usd):
    try:
        pad_wallet = USER_WALLET[2:].lower().rjust(64, '0')
        bal_res = eth_call(QILIN_TOKEN, get_sel("balanceOf(address)") + pad_wallet)
        bal = int(bal_res, 16) / 1e18 if bal_res and bal_res != "0x" else 0.0
        sold_res = eth_call(QILIN_MINT, get_sel("cardsSold()"))
        sold = int(sold_res, 16) if sold_res and sold_res != "0x" else 0
        rem_res = eth_call(QILIN_MINT, get_sel("freeCardsRemaining()"))
        free_rem = int(rem_res, 16) if rem_res and rem_res != "0x" else 0
        pair = get_pancake_pair(QILIN_TOKEN, WBNB)
        status_lp = f"Minting {sold}/10,000 (Free Left: {free_rem:,})"
        if pair:
            r0, r1 = get_reserves(pair)
            if r0 > 0 and r1 > 0:
                status_lp = f"LP Active ({pair[:10]}...)"
        log(f"[QILIN] Balance: {bal:,.0f} QILIN | Sold: {sold}/10,000 | Status: {status_lp}")
    except Exception as e:
        pass

def open_watch():
    """Nancy v2.8.0 / v2.8.2: Rapid 15s scanner for newly opened liquidity pools.
    Detects when minting completes and PancakeSwap pool launches without waiting for slow portfolio cycles.
    """
    try:
        # Check Firebearer
        pair_res = eth_call(FIREBEARER_TOKEN, get_sel("pancakePair()"))
        pair = ("0x" + pair_res[-40:]) if pair_res and pair_res != "0x" and len(pair_res) >= 66 else None
        liq_res = eth_call(FIREBEARER_TOKEN, get_sel("liquidityAdded()"))
        liq_added = bool(int(liq_res, 16)) if liq_res and liq_res != "0x" else False
        if liq_added and pair and pair != "0x0000000000000000000000000000000000000000":
            r0, r1 = get_reserves(pair)
            if r0 > 0 and r1 > 0:
                log(f"🚀 [POOL OPENED] Firebearer (传火人) LP Active on PancakeSwap V2! Pair: {pair}")

        # Check QILIN
        qilin_pair = get_pancake_pair(QILIN_TOKEN, WBNB)
        if qilin_pair:
            r0, r1 = get_reserves(qilin_pair)
            if r0 > 0 and r1 > 0:
                log(f"🚀 [POOL OPENED] QILIN LP Active on PancakeSwap V2! Pair: {qilin_pair}")
    except Exception:
        pass

def run_sentinel():
    log("🛰️ Binance AI Agent Portfolio & Price Sentinel v2.3 (Nancy v2.8.2 Rapid Sentinel) active!")
    log(f"   • Wallet: {USER_WALLET}")
    log(f"   • Protocols: Hash21, Altar, FAGENT PoA Vault, Ptah IAO, Firebearer, QILIN")
    log(f"   • Rapid Sentinels: 15s openWatch & fresh-token tracking, 10m ApprovalsWatchdog")

    last_watchdog = 0
    last_full_cycle = 0

    while True:
        try:
            now = time.time()
            # Rapid 15s check for open pools
            open_watch()

            # Full portfolio cycle every 120s
            if now - last_full_cycle >= 120:
                last_full_cycle = now
                wbnb_usd = get_wbnb_price_usd()
                check_hash21(wbnb_usd)
                check_fagent_vault()
                check_iao(wbnb_usd)
                check_firebearer(wbnb_usd)
                check_qilin(wbnb_usd)

            # Approvals Watchdog every 10 minutes (600s)
            if now - last_watchdog > 600:
                last_watchdog = now
                revoked = ApprovalsWatchdog.scan_and_revoke()
                if revoked:
                    for r in revoked:
                        log(f"🚨 [APPROVAL REVOKED] Revoked risky approval to {r['name']} ({r['spender']}) for token {r['token']}")
                else:
                    log("🛡️ [APPROVALS AUDIT] 0 suspicious authorizations found in wallet.")

        except Exception as e:
            log(f"[SENTINEL ERROR] {e}")
        time.sleep(15)

if __name__ == "__main__":
    run_sentinel()
