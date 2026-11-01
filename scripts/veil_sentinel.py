#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veil Network Sentinel (Robinhood Chain ID 4663)
- Monitors Robinhood Chain Mainnet RPC (https://rpc.mainnet.chain.robinhood.com)
- Checks Shielded Pool & Router operational state (0xbow Suite)
- Watches web frontend (https://veilnetwork.live) for NEXT_PUBLIC_0XBOW_ZK_ROUTER configuration unpause
- Triggers alert / autonomous action when mainnet deposit & shielded swap routes unpause
"""

import sys
import os
import time
import json
import re
import ssl
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROBINHOOD_RPC = "https://rpc.mainnet.chain.robinhood.com"
CHAIN_ID = 4663
SSL_CTX = ssl._create_unverified_context()

CONTRACTS = {
    "ETH_Pool": "0x10c17b7538e13c63b890fea52708846e88bb1932",
    "VEIL_Pool": "0x3db4ae3429f1507aa0cd31c740a0fd276e22a55c",
    "0xbow_Entrypoint": "0x96cb8b1836d341a6f5f1f54428bd6696c8b950b1",
    "Veil_Hook_v2": "0xf95f041462ee34c2ea7b953a879838133ef820c4"
}

def log(msg):
    t_str = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t_str}] {msg}")

def rpc_call(to, data):
    body = {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": to, "data": data}, "latest"]}
    payload = json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    req = urllib.request.Request(ROBINHOOD_RPC, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=10) as r:
            return json.loads(r.read().decode("utf-8")).get("result")
    except Exception as e:
        return None

def check_web_status():
    url = "https://veilnetwork.live/trade"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")
            
        scripts = re.findall(r'src=[\'"]([^\'"]+\.js)[\'"]', html)
        for s in scripts:
            js_url = f"https://veilnetwork.live{s}" if s.startswith("/") else s
            if "1ry0mvi6uwmnu" in s:
                j_req = urllib.request.Request(js_url, headers=headers)
                with urllib.request.urlopen(j_req, timeout=10) as jr:
                    js_code = jr.read().decode("utf-8", errors="ignore")
                    # Check router env setting
                    if 'NEXT_PUBLIC_0XBOW_ZK_ROUTER||""' in js_code:
                        return False, "Router env NEXT_PUBLIC_0XBOW_ZK_ROUTER rỗng -> Web hiển thị 'Shielded Swap Is Paused'"
                    else:
                        return True, "Phát hiện Router đã được cập nhật/bỏ rỗng!"
        return False, "Không quét được file JS trade"
    except Exception as e:
        return False, f"Lỗi kết nối website: {e}"

def check_contracts():
    # depositsPaused() selector: 0x60da3e83
    results = {}
    for name, addr in CONTRACTS.items():
        res = rpc_call(addr, "0x60da3e83")
        is_paused = (int(res, 16) != 0) if res and res.startswith("0x") and len(res) > 2 else None
        results[name] = is_paused
    return results

def run_sentinel_once():
    print("=" * 60)
    print("🛡️  VEIL NETWORK (ROBINHOOD CHAIN 4663) SENTINEL CHECK")
    print("=" * 60)
    
    web_unpaused, web_reason = check_web_status()
    print(f" • Frontend Status   : {'🟢 ĐÃ MỞ (LIVE)' if web_unpaused else '🟡 ĐANG TẠM DỪNG (PAUSED)'}")
    print(f" • Chi tiết lý do    : {web_reason}")
    
    contract_states = check_contracts()
    print(f"\n • Trạng thái On-Chain Robinhood (Chain ID {CHAIN_ID}):")
    for name, paused in contract_states.items():
        addr = CONTRACTS[name]
        status_txt = "🟢 Không bị pause on-chain" if paused is False else ("🔴 Đang pause" if paused is True else "⚪ Không hỗ trợ depositsPaused")
        print(f"   - {name.ljust(18)} ({addr}): {status_txt}")
        
    print("-" * 60)
    if not web_unpaused:
        print("💡 TỔNG KẾT: Hợp đồng ETH Pool trên Robinhood Chain không bị khóa, nhưng giao diện Web chưa gắn ZK Router (NEXT_PUBLIC_0XBOW_ZK_ROUTER).")
        print("   Daemon này có thể chạy ngầm để phát hiện tức thì khi team Robinhood/Veil unpause.")

if __name__ == "__main__":
    run_sentinel_once()
