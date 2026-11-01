#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentRob ($ROB) Fair Mint Manager
Chain: Robinhood Chain (Chain ID: 4663)
Gate: Verified .ai Agent-ID on BNB Chain (0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F)
Mint Contract: 0x6a0837e93ee51fb77425573cb42269298fc8fd3a
Token Contract: 0x68b93afa31d59a0fddfac13576952ccc95f13df0
"""

import sys
import os
import time
import json
import ssl
import random
import subprocess
import urllib.request
from eth_utils import keccak

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Constants
WALLET = "0x0C1D734cA7cD3Ae50A03D18a6913cD5Ee6A285d7"
ROBINHOOD_RPC = "https://rpc.mainnet.chain.robinhood.com"
BSC_RPC = "https://bsc-dataseed.binance.org"
CHAIN_ID = 4663

MINT_CONTRACT = "0x6a0837e93ee51fb77425573cb42269298fc8fd3a"
TOKEN_CONTRACT = "0x68b93afa31d59a0fddfac13576952ccc95f13df0"
AGENT_REGISTRY = "0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F"

# dop.ai tokenId = uint256(keccak256("dop"))
DOP_TOKEN_ID = int.from_bytes(keccak(text="dop"), "big")
API_BASE = "https://agentrob.live"

SSL_CTX = ssl._create_unverified_context()

def log(msg):
    t_str = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t_str}] {msg}")

def rpc_call(rpc_url, method, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
    req = urllib.request.Request(rpc_url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=10) as r:
            return json.loads(r.read().decode("utf-8")).get("result")
    except Exception as e:
        log(f"RPC error on {rpc_url}: {e}")
        return None

def check_onchain_status():
    log("=== [1] KIỂM TRA TRẠNG THÁI ON-CHAIN ROBINHOOD CHAIN (4663) ===")
    
    # totalMinted() selector: 0xa2309ff8
    minted_hex = rpc_call(ROBINHOOD_RPC, "eth_call", [{"to": MINT_CONTRACT, "data": "0xa2309ff8"}, "latest"])
    total_minted = int(minted_hex, 16) if minted_hex else 0
    
    # paused() selector: 0x5c975abb
    paused_hex = rpc_call(ROBINHOOD_RPC, "eth_call", [{"to": MINT_CONTRACT, "data": "0x5c975abb"}, "latest"])
    paused = int(paused_hex, 16) if paused_hex else 0
    
    log(f"Mint Contract: {MINT_CONTRACT}")
    log(f"Trạng thái: {'ĐANG MỞ' if paused == 0 else 'TẠM DỪNG (PAUSED)'}")
    log(f"Đã mint: {total_minted:,} / 1,000 suất miễn phí (Tổng pool: 4,440,000 shares)")
    
    # Check wallet ETH balance on Robinhood Chain
    bal_hex = rpc_call(ROBINHOOD_RPC, "eth_getBalance", [WALLET, "latest"])
    bal_eth = int(bal_hex, 16) / 1e18 if bal_hex else 0.0
    log(f"Số dư ví {WALLET} trên Robinhood Chain: {bal_eth:.6f} ETH")
    
    return {
        "total_minted": total_minted,
        "paused": paused != 0,
        "bal_eth": bal_eth
    }

def verify_agent_id():
    log("\n=== [2] XÁC THỰC BINANCE AGENT ID TRÊN BNB CHAIN (56) ===")
    owner_data = "0x6352211e" + hex(DOP_TOKEN_ID)[2:].rjust(64, "0")
    res = rpc_call(BSC_RPC, "eth_call", [{"to": AGENT_REGISTRY, "data": owner_data}, "latest"])
    if res and res != "0x":
        owner = "0x" + res[-40:].lower()
        is_owner = (owner == WALLET.lower())
        log(f"Agent-ID: dop.ai (TokenID: {DOP_TOKEN_ID})")
        log(f"Chủ sở hữu trên BSC: {owner}")
        log(f"Khớp ví đang quản lý: {'ĐÚNG (HỢP LỆ 100%)' if is_owner else 'SAI'}")
        return is_owner
    log("Không thể truy vấn registry trên BSC.")
    return False

def check_backend_allowance():
    log("\n=== [3] KIỂM TRA QUOTA TẠI AGENTROB API ===")
    url = f"{API_BASE}/wallet/allowance"
    payload = json.dumps({"wallet": WALLET, "agentId": DOP_TOKEN_ID}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=10) as r:
            res = json.loads(r.read().decode("utf-8"))
            log(f"Phản hồi từ server: {res}")
            free_rem = res.get("freeRemaining", 0)
            log(f"Suất miễn phí còn lại: {free_rem} share (= 50,000 $ROB)")
            return res
    except Exception as e:
        log(f"Lỗi kiểm tra allowance: {e}")
        return None

def fetch_mint_voucher(max_attempts=15):
    log("\n=== [4] LẤY EIP-712 MINT VOUCHER (SIGNER TỪ AGENTROB) ===")
    url = f"{API_BASE}/prepare/mint"
    payload = json.dumps({"wallet": WALLET, "tokenId": str(DOP_TOKEN_ID), "shares": 1}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Origin": API_BASE,
        "Referer": f"{API_BASE}/"
    }
    
    for attempt in range(1, max_attempts + 1):
        log(f"Lượt {attempt}/{max_attempts}: Đang yêu cầu voucher...")
        try:
            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=8) as r:
                res = json.loads(r.read().decode("utf-8"))
                if res.get("ok"):
                    log(">>> THÀNH CÔNG! Đã lấy được voucher ký hợp lệ! <<<")
                    return res
        except urllib.error.HTTPError as e:
            if e.code == 429:
                log("Server báo 429 (Rate limit do nghẽn Cloudflare / nhiều bot cùng request). Chờ retry...")
            else:
                log(f"HTTP Lỗi {e.code}: {e.read().decode('utf-8', errors='ignore')[:80]}")
        except Exception as e:
            log(f"Lỗi mạng: {e}")
        time.sleep(random.uniform(1.5, 3.0))
        
    log("Chưa lấy được voucher do server đang bị rate limit gắt gao.")
    return None

def main():
    log("Khởi động AgentRob Manager...")
    status = check_onchain_status()
    is_valid_agent = verify_agent_id()
    if not is_valid_agent:
        log("LỖI: Ví không sở hữu Agent ID dop.ai!")
        return

    check_backend_allowance()
    
    if status["bal_eth"] < 0.00001:
        log("\n" + "="*60)
        log("⚠️ CẢNH BÁO GAS: Số dư ETH trên Robinhood Chain của ví là 0.000000 ETH.")
        log("Mặc dù suất mint này là MIỄN PHÍ (cost = 0 ETH), mạng Robinhood Chain")
        log("vẫn cần một lượng gas ETH cực nhỏ (khoảng 0.000005 ETH ~ 0.012 USD / 300 VNĐ).")
        log("Cần nạp một lượng ETH nhỏ vào ví trên Robinhood Chain (Chain ID: 4663) trước khi bấm gửi tx.")
        log("="*60)

if __name__ == "__main__":
    main()
