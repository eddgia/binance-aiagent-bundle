#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agentic Pixels & $AGENT Solver & Inspector (BNB Chain - Chain ID 56)
- Evaluates on-chain arithmetic challenges from Agentic Pixels (AGPX: 0x51D87A14B0c0736608e71AEfe8c571faE5Cf19ca)
- Resolves caller's Binance Agent ID (e.g., dop.ai)
- Checks $AGENT fair mint status (0xA2643B889eEb232708a644f15f70f951773dDEF9)
- Automates BAW contract-call preview/execute if minting opens
"""

import sys
import os
import json
import re
import urllib.request
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

RPC_URL = CONFIG.get("rpc_url", "https://bsc-dataseed.binance.org")
WALLET = CONFIG.get("wallet_address", "0x0C1D734cA7cD3Ae50A03D18a6913cD5Ee6A285d7")

AGPX_CONTRACT = "0x51D87A14B0c0736608e71AEfe8c571faE5Cf19ca"
AGENT_TOKEN = "0xA2643B889eEb232708a644f15f70f951773dDEF9"

def eth_call(to, data):
    body = {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": to, "data": data}, "latest"]}
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(RPC_URL, data=payload, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8")).get("result")
    except Exception as e:
        return None

def solve_challenge_text(text, agent_handle):
    # Example text: "What is 28 x 24 plus the number of characters in your Agent ID (without .ai)?"
    clean_handle = agent_handle.replace(".ai", "").strip()
    handle_len = len(clean_handle)
    
    # Pattern: What is (\d+) x (\d+) plus the number of characters...
    match_mult = re.search(r'(\d+)\s*[x\*]\s*(\d+)', text, re.I)
    if match_mult:
        a = int(match_mult.group(1))
        b = int(match_mult.group(2))
        base = a * b
        if "plus" in text.lower() or "add" in text.lower():
            ans = base + handle_len
        elif "minus" in text.lower() or "subtract" in text.lower():
            ans = base - handle_len
        else:
            ans = base + handle_len
        return ans, f"{a} * {b} + {handle_len} = {ans}"
    return None, "Unable to parse pattern"

def inspect_agent_token():
    print(f"\n==================================================")
    print(f"🪙 [1] $AGENT FAIR-MINT TOKEN STATUS (0xA264...DEF9)")
    print(f"==================================================")
    # balanceOf(WALLET) -> 0x70a08231
    data_bal = "0x70a08231" + WALLET[2:].lower().zfill(64)
    raw_bal = eth_call(AGENT_TOKEN, data_bal)
    bal = int(raw_bal, 16) / 1e18 if raw_bal else 0
    
    raw_supply = eth_call(AGENT_TOKEN, "0x18160ddd")
    supply = int(raw_supply, 16) / 1e18 if raw_supply else 0
    
    print(f" • Token Total Supply : {supply:,.0f} AGENT")
    print(f" • Wallet Address      : {WALLET}")
    print(f" • Wallet $AGENT Bal  : {bal:,.0f} AGENT")
    if bal >= 9000:
        print(f" ✅ THÔNG BÁO: Ví đã hoàn tất Fair-Mint tối đa 9,000 $AGENT từ trước!")
    else:
        print(f" ⚠️ Ví chưa nhận đủ 9,000 $AGENT. Sẵn sàng gọi hàm mint() (0x1249c58b).")

def inspect_and_solve_agentic_pixels():
    print(f"\n==================================================")
    print(f"🎨 [2] AGENTIC PIXELS (AGPX) ON-CHAIN SOLVER (0x51D8...19ca)")
    print(f"==================================================")
    
    # Check totalMinted
    raw_minted = eth_call(AGPX_CONTRACT, "0xa2309ff8")
    total_minted = int(raw_minted, 16) if raw_minted else 0
    
    raw_max = eth_call(AGPX_CONTRACT, "0x32cb6b0c")
    max_supply = int(raw_max, 16) if raw_max else 2000
    
    raw_open = eth_call(AGPX_CONTRACT, "0x24bbd049")
    mint_open = int(raw_open, 16) if raw_open else 0
    
    print(f" • Total Minted  : {total_minted} / {max_supply}")
    print(f" • Mint Status   : {'🟢 ĐANG MỞ (OPEN)' if mint_open == 1 else '🔴 ĐÃ ĐÓNG / FULL (CLOSED)'}")
    
    # Query agentIdOf(WALLET) -> 0xe9c9ec73
    raw_agent = eth_call(AGPX_CONTRACT, "0xe9c9ec73" + WALLET[2:].lower().zfill(64))
    agent_handle = "dop"
    if raw_agent and len(raw_agent) >= 130:
        try:
            length = int(raw_agent[66:130], 16)
            agent_handle = bytes.fromhex(raw_agent[130:130 + length * 2]).decode("utf-8")
        except Exception:
            pass
    print(f" • Detected Agent ID : '{agent_handle}' (without .ai, len={len(agent_handle)})")
    
    # Query challengeOf(WALLET) -> 0x6cc23c5d
    raw_ch = eth_call(AGPX_CONTRACT, "0x6cc23c5d" + WALLET[2:].lower().zfill(64))
    if raw_ch and len(raw_ch) >= 194:
        try:
            # ABI returns (string prompt, uint256 a, uint256 b)
            # Offset is word 0 (chars 2:66)
            # a is word 1 (chars 66:130)
            # b is word 2 (chars 130:194)
            # string length is word 3 (chars 194:258)
            num_a = int(raw_ch[66:130], 16)
            num_b = int(raw_ch[130:194], 16)
            ch_len = int(raw_ch[194:258], 16)
            ch_text = bytes.fromhex(raw_ch[258:258 + ch_len * 2]).decode("utf-8")
            
            print(f" • On-chain Challenge: \"{ch_text}\"")
            print(f" • Raw Challenge Params: a={num_a}, b={num_b}")
            
            ans, explanation = solve_challenge_text(ch_text, agent_handle)
            # Fallback to direct calculation if regex fails:
            if ans is None:
                ans = (num_a * num_b) + len(agent_handle)
                explanation = f"{num_a} * {num_b} + {len(agent_handle)} = {ans}"
                
            print(f" 🧮 Giải thuật PoW     : {explanation}")
            print(f" 🎯 Lời giải chính xác : {ans}")
            
            if mint_open == 1 and total_minted < max_supply:
                print(f"\n🚀 Sẵn sàng tự động gửi giao dịch mint(uint256 answer={ans}, uint256 amount=1) qua BAW CLI!")
            else:
                print(f"\nℹ️ Hiện tại bộ sưu tập 2,000/2,000 NFT đã được mint sạch (Sold out). Script đã lưu sẵn logic giải đề tự động khi mở Phase tiếp theo!")
        except Exception as e:
            print(f" ⚠️ Không giải mã được chuỗi challenge: {e}")

if __name__ == "__main__":
    inspect_agent_token()
    inspect_and_solve_agentic_pixels()
