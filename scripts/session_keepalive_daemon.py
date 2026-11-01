#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Binance Agentic Wallet (BAW) Session Keepalive Daemon
- Periodically pings BAW CLI (wallet status & balance) to prevent idle session timeout
- Keeps the authenticated cloud session active 24/7
- Monitors BNB gas balance & connection health
- Records heartbeats into logs/session_keepalive.log
"""

import sys
import os
import time
import json
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(ROOT_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGS_DIR, "session_keepalive.log")

INTERVAL_SECONDS = 90  # Ping every 90 seconds (well within idle expiration window)

def log(msg):
    t_str = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{t_str}] {msg}"
    print(formatted, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def run_baw_json(args):
    cmd = ["baw"] + args + ["--json"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=30)
        if res.returncode == 0:
            return json.loads(res.stdout)
        else:
            return {"success": False, "stderr": res.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}

def keepalive_loop():
    log("==================================================")
    log("🟢 BAW SESSION KEEPALIVE DAEMON STARTED")
    log(f" • Heartbeat Interval : {INTERVAL_SECONDS} seconds")
    log(f" • Target Log File    : {LOG_FILE}")
    log("==================================================")

    heartbeat_count = 0
    while True:
        try:
            heartbeat_count += 1
            # 1. Ping wallet status
            status_data = run_baw_json(["wallet", "status"])
            is_connected = status_data.get("data", {}).get("status") == "CONNECTED"
            
            if is_connected:
                # Every 5 pings (~7.5 minutes), fetch balance to keep full wallet session refreshed
                if heartbeat_count % 5 == 1:
                    bal_data = run_baw_json(["wallet", "balance"])
                    tokens = bal_data.get("data", [])
                    bnb_bal = "N/A"
                    for t in tokens:
                        if t.get("symbol") == "BNB":
                            bnb_bal = f"{float(t.get('balance', 0)):.5f} BNB (~${float(t.get('value', 0)):.2f})"
                            break
                    log(f"💓 [HEARTBEAT #{heartbeat_count}] Session ACTIVE & CONNECTED | Balance: {bnb_bal}")
                else:
                    log(f"💓 [HEARTBEAT #{heartbeat_count}] Session ACTIVE & CONNECTED")
            else:
                log(f"⚠️ [WARNING #{heartbeat_count}] Session status: {status_data}")
                
        except Exception as e:
            log(f"❌ [ERROR #{heartbeat_count}] Keepalive error: {e}")

        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    keepalive_loop()
