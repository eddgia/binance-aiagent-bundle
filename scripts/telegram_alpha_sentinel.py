#!/usr/bin/env python3
"""
Telegram Alpha Sentinel (agentidmintalerts) - 24/7 Automated Alpha Sniper
Author: KPL & Antigravity (Nancy v2.8.3 Architecture)

Monitors https://t.me/s/agentidmintalerts for new Agent ID mint drops.
Extracts contract address, network, mint method, and executes Free Mints automatically!
"""

import sys
import os
import json
import time
import ssl
import re
import urllib.request
import subprocess

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

WALLET = "0x0C1D734cA7cD3Ae50A03D18a6913cD5Ee6A285d7"
TELE_URL = "https://t.me/s/agentidmintalerts"
SEEN_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "seen_telegram_alerts.json")
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
ALERTS_LOG = os.path.join(LOG_DIR, "telegram_alerts.log")

RPC_BSC = "https://bsc.publicnode.com"

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(ALERTS_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
    except Exception:
        pass

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_seen(seen_set):
    try:
        os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen_set), f, indent=2)
    except Exception:
        pass

def fetch_channel_messages():
    req = urllib.request.Request(TELE_URL, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=10) as res:
            html = res.read().decode("utf-8", errors="ignore")
    except Exception as e:
        log(f"[!] Error fetching telegram channel: {e}")
        return []

    # Extract posts: data-post="agentidmintalerts/123"
    post_blocks = re.findall(
        r'<div class="tgme_widget_message[^"]*" data-post="([^"]+)"[^>]*>.*?<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
        html,
        re.DOTALL
    )
    
    extracted = []
    for post_id, raw_text in post_blocks:
        clean_text = re.sub(r'<br\s*/?>', '\n', raw_text)
        clean_text = re.sub(r'<[^>]+>', '', clean_text).strip()
        extracted.append({"id": post_id, "text": clean_text})

    return extracted

def parse_alert(text):
    # Check if free mint
    is_free = bool(re.search(r'(miễn phí|free mint|🆓|value\s*0|0\s*usdt|0\s*bnb)', text, re.IGNORECASE))
    
    # Extract contract address 0x...
    contracts = re.findall(r'0x[a-fA-F0-9]{40}', text)
    primary_ca = contracts[0] if contracts else None
    
    # Extract chain
    chain = "BSC"
    if re.search(r'(robinhood|chain\s*4663)', text, re.IGNORECASE):
        chain = "ROBINHOOD"
    elif re.search(r'(base|chain\s*8453)', text, re.IGNORECASE):
        chain = "BASE"
    elif re.search(r'(arbitrum|chain\s*42161)', text, re.IGNORECASE):
        chain = "ARBITRUM"
    elif re.search(r'(solana|sol)', text, re.IGNORECASE):
        chain = "SOLANA"

    # Extract method hints
    method_match = re.search(r'(mint\w*\([^\)]*\)|claim\w*\([^\)]*\))', text, re.IGNORECASE)
    method_hint = method_match.group(1) if method_match else "mint"

    title_line = text.split('\n')[0] if text else "Unknown Alert"

    return {
        "title": title_line,
        "is_free": is_free,
        "contract": primary_ca,
        "chain": chain,
        "method_hint": method_hint,
        "contracts": contracts,
        "raw": text
    }

def try_auto_mint_bsc(contract, method_hint):
    log(f"[*] Analyzing auto-mint for BSC contract: {contract} (hint: {method_hint})")
    
    # 1. Check code
    req = urllib.request.Request(RPC_BSC, data=json.dumps({
        "jsonrpc": "2.0", "method": "eth_getCode", "params": [contract, "latest"], "id": 1
    }).encode(), headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=6) as res:
            code = json.loads(res.read()).get("result", "")
    except Exception as e:
        log(f"[!] RPC error: {e}")
        return False

    if len(code) <= 2:
        log("[!] Not a contract or no code.")
        return False

    # Possible selectors for free mint
    # 0xa0712d68 -> mint(uint256)
    # 0x1249c58b -> mint()
    # 0xa0712d68 with param 0
    # 0x40c10f19 -> mint(address,uint256)
    # 0x6a627842 -> mint(address)
    # 0x4f02c420 -> mintFree() / 0xd473060a
    candidate_calls = []
    
    if "mint(0)" in method_hint or "a0712d68" in code:
        candidate_calls.append(("0xa0712d68" + ("0" * 64), "mint(0)"))
    
    # Check for mint() 0x1249c58b
    if "1249c58b" in code:
        candidate_calls.append(("0x1249c58b", "mint()"))

    # Check for mint(address) 0x6a627842
    if "6a627842" in code:
        candidate_calls.append(("0x6a627842" + WALLET[2:].lower().zfill(64), "mint(address)"))

    # Check for mintFree() 0xd473060a / 0x4f02c420
    if "d473060a" in code:
        candidate_calls.append(("0xd473060a", "mintFree()"))

    # Check for mintPass("") 0x
    if "mintpass" in method_hint.lower():
        # mintPass(string)
        candidate_calls.append(("0x68b91dc800000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000000", "mintPass('')"))

    if not candidate_calls:
        # Default fallback to mint(0)
        candidate_calls.append(("0xa0712d68" + ("0" * 64), "mint(0)"))

    for calldata, call_desc in candidate_calls:
        log(f"[*] Simulating candidate call: {call_desc} (data: {calldata[:10]})...")
        cmd_prev = [
            "baw", "contract-call", "preview",
            "--binanceChainId", "56",
            "--from", WALLET,
            "--to", contract,
            "--value", "0",
            "--inputData", calldata,
            "--json"
        ]
        res_prev = subprocess.run(cmd_prev, shell=True, capture_output=True, text=True)
        try:
            prev_json = json.loads(res_prev.stdout)
        except Exception:
            continue

        if prev_json.get("success"):
            sim_code = prev_json["data"].get("simulationResult", {}).get("simulationCode")
            if sim_code == "000000000":
                req_id = prev_json["data"]["requestId"]
                log(f"[+] Preview SUCCESS! RequestId: {req_id}. Executing free mint now...")
                cmd_exec = ["baw", "contract-call", "execute", "--requestId", req_id, "--json"]
                res_exec = subprocess.run(cmd_exec, shell=True, capture_output=True, text=True)
                exec_json = json.loads(res_exec.stdout)
                if exec_json.get("success"):
                    tx = exec_json.get("data", {}).get("txHash")
                    log(f"[🎉] AUTO-MINT SUCCESS! Tx: {tx} | BscScan: https://bscscan.com/tx/{tx}")
                    return True
                else:
                    log(f"[!] Execute failed: {exec_json.get('error')}")
            else:
                log(f"[-] Preview reverted with simCode: {sim_code}")
    
    return False

def process_alert(alert):
    title = alert["title"]
    is_free = alert["is_free"]
    contract = alert["contract"]
    chain = alert["chain"]
    method_hint = alert["method_hint"]

    log(f"\n==========================================")
    log(f"[🚨] KÈO MỚI PHÁT HIỆN: {title}")
    log(f"    - Chain: {chain} | Hợp đồng: {contract}")
    log(f"    - Loại kèo: {'🆓 MIỄN PHÍ' if is_free else '💎 TRẢ PHÍ'}")
    log(f"    - Method Hint: {method_hint}")
    log(f"==========================================")

    if not contract:
        log("[-] Không tìm thấy địa chỉ hợp đồng trong bài đăng.")
        return

    if is_free:
        if chain == "BSC":
            success = try_auto_mint_bsc(contract, method_hint)
            if success:
                log(f"[🎉] Đã tự động húp trọn kèo miễn phí: {title}")
            else:
                log(f"[!] Không thể tự động mint (có thể yêu cầu backend voucher hoặc pool chưa mở).")
        elif chain == "ROBINHOOD":
            log("[*] Kèo trên Robinhood Chain -> Kiểm tra SoulBoard hoặc contract tương ứng...")
            # Run soulboard minter if contract matches
            if contract.lower() == "0x9518a406109d6072a76ac7ab8816cf267ad291c3":
                subprocess.run(["python", r"C:\Users\PC\.agyent\workspace\binance-aiagent-bundle\scripts\soulboard_minter.py"], shell=True)
    else:
        log(f"[*] Kèo trả phí -> Đã ghi nhận thông tin, không tự ý trừ tiền của chủ nhân.")

def run_loop(poll_interval=15):
    log(f"[*] Khởi động Telegram Alpha Sentinel (@agentidmintalerts)...")
    log(f"    - Giám sát: {TELE_URL}")
    log(f"    - Chu kỳ quét: mỗi {poll_interval} giây")
    seen_ids = load_seen()
    log(f"    - Đã lưu vết: {len(seen_ids)} bài viết cũ.")

    # Initial check
    messages = fetch_channel_messages()
    for m in messages:
        if m["id"] not in seen_ids:
            seen_ids.add(m["id"])
    save_seen(seen_ids)
    log(f"[+] Đồng bộ ban đầu hoàn tất. Bắt đầu trực chiến theo thời gian thực...")

    while True:
        try:
            messages = fetch_channel_messages()
            for m in messages:
                post_id = m["id"]
                if post_id not in seen_ids:
                    seen_ids.add(post_id)
                    save_seen(seen_ids)
                    alert_info = parse_alert(m["text"])
                    process_alert(alert_info)
        except Exception as e:
            log(f"[!] Loop error: {e}")

        time.sleep(poll_interval)

if __name__ == "__main__":
    interval = 15
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        interval = int(sys.argv[1])
    run_loop(interval)
