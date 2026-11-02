#!/usr/bin/env python3
"""
Relay.link Bridge & SoulBoard Auto-Minter
End-to-End Orchestrator:
1. Bridge 0.0015 BNB from BSC (56) -> ETH on Robinhood Chain (4663) via relay.link
2. Wait for Relay intent settlement (~5-15s)
3. Automatically mint 1,000 SoulBoard ($BOARD) free share on Robinhood Chain!
"""

import sys
import os
import json
import time
import ssl
import urllib.request
import subprocess

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

WALLET = "0x0C1D734cA7cD3Ae50A03D18a6913cD5Ee6A285d7"
SOULBOARD_CONTRACT = "0x9518a406109d6072a76aC7aB8816cF267ad291c3"
RELAY_QUOTE_URL = "https://api.relay.link/quote"
RELAY_STATUS_URL = "https://api.relay.link/intents/status"

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

def step_1_bridge_bnb(amount_bnb=0.0015):
    print(f"\n==========================================")
    print(f"[*] BƯỚC 1: Khởi tạo Bridge trên Relay.link")
    print(f"    - Nguồn: {amount_bnb} BNB trên BSC (Chain 56)")
    print(f"    - Đích: ETH trên Robinhood Chain (Chain 4663)")
    print(f"    - Ví nhận: {WALLET}")
    print(f"==========================================")

    amount_wei = str(int(amount_bnb * 1e18))
    payload = {
        "user": WALLET,
        "originChainId": 56,
        "destinationChainId": 4663,
        "originCurrency": "0x0000000000000000000000000000000000000000",
        "destinationCurrency": "0x0000000000000000000000000000000000000000",
        "recipient": WALLET,
        "amount": amount_wei,
        "tradeType": "EXACT_INPUT"
    }

    req = urllib.request.Request(
        RELAY_QUOTE_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, context=CTX, timeout=10) as res:
        quote = json.loads(res.read())

    req_id = quote.get("requestId")
    exp_eth = quote.get("details", {}).get("route", {}).get("destination", {}).get("outputCurrency", {}).get("amountFormatted")
    item = quote["steps"][0]["items"][0]["data"]
    to_addr = item["to"]
    call_data = item["data"]
    call_val = item["value"]

    print(f"[+] Đã nhận Quote từ Relay:")
    print(f"    - Relay Request ID: {req_id}")
    print(f"    - Dự kiến nhận: {exp_eth} ETH trên Robinhood Chain")
    print(f"    - Hợp đồng Depository BSC: {to_addr}")

    print(f"[*] Đang mô phỏng giao dịch qua Binance Agentic Wallet (BAW)...")
    cmd_prev = [
        "baw", "contract-call", "preview",
        "--binanceChainId", "56",
        "--from", WALLET,
        "--to", to_addr,
        "--value", str(call_val),
        "--inputData", call_data,
        "--json"
    ]
    res_prev = subprocess.run(cmd_prev, shell=True, capture_output=True, text=True)
    prev_json = json.loads(res_prev.stdout)
    if not prev_json.get("success"):
        print(f"[!] BAW Preview thất bại: {prev_json}")
        return None, None

    baw_req_id = prev_json["data"]["requestId"]
    sim_code = prev_json["data"].get("simulationResult", {}).get("simulationCode")
    print(f"[+] Preview thành công (Code: {sim_code})! BAW RequestId: {baw_req_id}")

    print(f"[*] Đang thực thi gửi 0.0015 BNB vào Relay Depository...")
    cmd_exec = ["baw", "contract-call", "execute", "--requestId", baw_req_id, "--json"]
    res_exec = subprocess.run(cmd_exec, shell=True, capture_output=True, text=True)
    exec_json = json.loads(res_exec.stdout)
    if not exec_json.get("success"):
        print(f"[!] BAW Execute thất bại: {exec_json}")
        return None, None

    tx_hash = exec_json.get("data", {}).get("txHash")
    print(f"[🎉] Giao dịch nạp Bridge đã phát sóng thành công!")
    print(f"    - TxHash (BSC): {tx_hash}")
    print(f"    - BscScan: https://bscscan.com/tx/{tx_hash}")

    return req_id, tx_hash

def step_2_wait_relay_settlement(relay_req_id):
    print(f"\n==========================================")
    print(f"[*] BƯỚC 2: Chờ Relay Solver khớp lệnh & chuyển ETH...")
    print(f"==========================================")
    url = f"{RELAY_STATUS_URL}?requestId={relay_req_id}"
    for i in range(25):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=CTX, timeout=6) as res:
                data = json.loads(res.read())
                status = data.get("status")
                print(f"    [{i+1}/25] Trạng thái Relay: {status}...")
                if status == "success":
                    print(f"[🎉] Bridge hoàn tất 100%! ETH đã được ghi có trên Robinhood Chain!")
                    return True
                elif status in ["failure", "refunded"]:
                    print(f"[!] Giao dịch Bridge thất bại hoặc được hoàn lại: {status}")
                    return False
        except Exception as e:
            print(f"    Lỗi thăm dò: {e}")
        time.sleep(3)
    print("[!] Hết thời gian chờ Relay API, tiếp tục kiểm tra số dư on-chain trực tiếp...")
    return False

def step_3_mint_soulboard():
    print(f"\n==========================================")
    print(f"[*] BƯỚC 3: Kích hoạt Mint miễn phí 1.000 SoulBoard ($BOARD)")
    print(f"==========================================")
    cmd = ["python", r"C:\Users\PC\.agyent\workspace\binance-aiagent-bundle\scripts\soulboard_minter.py"]
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print(res.stderr)
    return "SUCCESS!" in res.stdout or "already owns" in res.stdout

def main():
    relay_req_id, bsc_tx = step_1_bridge_bnb(0.0015)
    if not relay_req_id:
        print("[!] Không thể tiếp tục do bước Bridge không thành công.")
        return

    step_2_wait_relay_settlement(relay_req_id)

    # Chờ thêm 3s cho RPC Robinhood Chain cập nhật block
    time.sleep(3)

    # Mint SoulBoard
    step_3_mint_soulboard()

if __name__ == "__main__":
    main()
