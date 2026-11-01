#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EnigmaAgent "MINT THE TABLET" Autonomous Minter (BNB Chain - Chain ID 56)
- Contract: 0x213A879D11a85b54483CEA2cdEC5D9026958Add3
- Agent ID Registry: 0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F
- Gated by .ai Agent ID
- Free mint (0 BNB value, BSC gas only)
- Solved Nonce: 11400538897593481594 (33 leading zero bits)
"""

import sys
import os
import json
import urllib.request
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

RPC_URL = CONFIG.get("rpc_url", "https://bsc-dataseed.binance.org")
WALLET = CONFIG.get("wallet_address", "0x0C1D734cA7cD3Ae50A03D18a6913cD5Ee6A285d7")

NFT_CONTRACT = "0x213A879D11a85b54483CEA2cdEC5D9026958Add3"
REGISTRY_CONTRACT = "0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F"

# Solved nonce for wallet 0x0C1D734cA7cD3Ae50A03D18a6913cD5Ee6A285d7 (>= 33 zero bits)
SOLVED_NONCE = 11400538897593481594

def eth_call(to, data):
    body = {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": to, "data": data}, "latest"]}
    req = urllib.request.Request(RPC_URL, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8")).get("result")
    except Exception as e:
        return None

def check_status():
    print("=" * 60)
    print("🗿 ENIGMAAGENT 'MINT THE TABLET' ON-CHAIN STATUS")
    print("=" * 60)
    
    # 1. Registry check
    reg_raw = eth_call(REGISTRY_CONTRACT, "0x70a08231" + WALLET[2:].lower().zfill(64))
    has_agent_id = int(reg_raw, 16) > 0 if reg_raw else False
    print(f" • Ví tác chiến           : {WALLET}")
    print(f" • Sở hữu Agent ID        : {'✅ HỢP LỆ (dop.ai)' if has_agent_id else '❌ Chưa có Agent ID'}")
    
    # 2. NFT hasMinted check
    minted_raw = eth_call(NFT_CONTRACT, "0x38e21cce" + WALLET[2:].lower().zfill(64))
    has_minted = int(minted_raw, 16) == 1 if minted_raw else False
    print(f" • Đã Mint trước đây      : {'⚠️ ĐÃ MINT RỒI (Tối đa 1 cái/ví)' if has_minted else '🟢 CHƯA MINT (Sẵn sàng nhận)'}")
    
    # 3. publicMinted & difficulty
    pub_raw = eth_call(NFT_CONTRACT, "0xa4f4f8af")
    pub_minted = int(pub_raw, 16) if pub_raw else 0
    diff_raw = eth_call(NFT_CONTRACT, "0x249379ad")
    diff_bits = int(diff_raw, 16) if diff_raw else 33
    
    print(f" • Tiến độ Mint toàn mạng : {pub_minted} / 3,338 ({3338 - pub_minted} slots còn lại)")
    print(f" • Độ khó hiện tại        : {diff_bits} bits")
    print(f" • Nonce đã giải sẵn      : {SOLVED_NONCE} (0x{SOLVED_NONCE:064x})")
    
    return has_agent_id, has_minted, pub_minted, diff_bits

def simulate_mint(nonce):
    calldata = "0xa0712d68" + hex(nonce)[2:].zfill(64)
    tx_obj = {
        "from": WALLET,
        "to": NFT_CONTRACT,
        "data": calldata,
        "value": "0x0"
    }
    body = {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [tx_obj, "latest"]}
    req = urllib.request.Request(RPC_URL, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read().decode("utf-8"))
            if "result" in res and res["result"] == "0x":
                return True, "Mô phỏng eth_call THÀNH CÔNG 100% (No revert)"
            return False, f"Revert: {res.get('error')}"
    except Exception as e:
        return False, str(e)

def execute_baw_mint(nonce):
    calldata = "0xa0712d68" + hex(nonce)[2:].zfill(64)
    print("\n🚀 [BƯỚC 1] Gửi preview giao dịch qua BAW CLI...")
    cmd_preview = [
        "baw", "contract-call", "preview",
        "--binanceChainId", "56",
        "--from", WALLET,
        "--to", NFT_CONTRACT,
        "--value", "0",
        "--inputData", calldata,
        "--json"
    ]
    try:
        p_res = subprocess.run(cmd_preview, capture_output=True, text=True, shell=True)
        print("Preview output:", p_res.stdout)
        if p_res.returncode != 0:
            print("Preview stderr:", p_res.stderr)
            return
            
        data = json.loads(p_res.stdout)
        req_id = data.get("data", {}).get("requestId")
        if not req_id:
            print("Không lấy được requestId từ preview.")
            return
            
        print(f"✅ Preview thành công! RequestId: {req_id}")
        print("🚀 [BƯỚC 2] Thực thi lệnh mint on-chain...")
        cmd_exec = ["baw", "contract-call", "execute", "--requestId", req_id, "--json"]
        e_res = subprocess.run(cmd_exec, capture_output=True, text=True, shell=True)
        print("Execute output:", e_res.stdout)
    except Exception as e:
        print("Lỗi thực thi BAW:", e)

if __name__ == "__main__":
    has_id, minted, pub, diff = check_status()
    if has_id and not minted and pub < 3338:
        ok, msg = simulate_mint(SOLVED_NONCE)
        print(f"\n🔍 Kết quả mô phỏng Sandbox: {msg}")
        if ok:
            print("\n💡 LỆNH THỰC THI QUA BAW CLI (Dành cho Muse hoặc PC sau khi login):")
            calldata = "0xa0712d68" + hex(SOLVED_NONCE)[2:].zfill(64)
            print(f"baw contract-call preview --binanceChainId 56 --from {WALLET} --to {NFT_CONTRACT} --value 0 --inputData {calldata}")
            execute_baw_mint(SOLVED_NONCE)
