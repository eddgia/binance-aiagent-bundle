#!/usr/bin/env python3
"""
Binance AI Agent Master Runner
Launches the Smart Sniper Daemon, Portfolio Price Sentinel, and Twitter Alpha Sentinel in parallel with auto-recovery.
"""

import subprocess
import sys
import os
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def start_daemons():
    print("=" * 60, flush=True)
    print("      BINANCE AI AGENT - MASTER DAEMON LAUNCHER (PC)", flush=True)
    print("=" * 60, flush=True)
    
    scripts = [
        ("Smart Sniper Daemon v3.5 (Nancy v2.8.3 Suite)", "smart_sniper_daemon.py"),
        ("Portfolio & Price Sentinel v2.3 (ApprovalsWatchdog & Pools)", "portfolio_price_sentinel.py"),
        ("Twitter Alpha Sentinel", "twitter_alpha_sentinel.py"),
        ("Telegram Alpha Sentinel (@agentidmintalerts)", "telegram_alpha_sentinel.py")
    ]
    
    managed = []
    for name, script_file in scripts:
        script_path = os.path.join(BASE_DIR, script_file)
        if os.path.exists(script_path):
            print(f"▶️ Starting: {name} ({script_file})...", flush=True)
            p = subprocess.Popen([sys.executable, "-u", script_path])
            managed.append({"name": name, "path": script_path, "proc": p})
            time.sleep(1)
        else:
            print(f"⚠️ Missing: {script_path}", flush=True)
            
    print("=" * 60, flush=True)
    print("✅ All services active! Monitoring health...", flush=True)
    print("=" * 60, flush=True)
    
    try:
        while True:
            time.sleep(5)
            for item in managed:
                proc = item["proc"]
                if proc.poll() is not None:
                    print(f"⚠️ Warning: {item['name']} stopped (code {proc.returncode}). Restarting...", flush=True)
                    time.sleep(2)
                    new_p = subprocess.Popen([sys.executable, "-u", item["path"]])
                    item["proc"] = new_p
    except KeyboardInterrupt:
        print("\n🛑 Shutting down all daemons...", flush=True)
        for item in managed:
            try:
                item["proc"].terminate()
            except Exception:
                pass
        print("Done.", flush=True)

if __name__ == "__main__":
    start_daemons()
