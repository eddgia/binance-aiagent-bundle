#!/usr/bin/env python3
"""
Binance AI Agent Master Runner
Launches the Smart Sniper Daemon, Portfolio Price Sentinel, and Twitter Alpha Sentinel in parallel.
"""

import subprocess
import sys
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def start_daemons():
    print("=" * 60)
    print("      BINANCE AI AGENT - MASTER DAEMON LAUNCHER")
    print("=" * 60)
    
    scripts = [
        ("Smart Sniper Daemon v3.2 (>10 Wallets Consensus)", "smart_sniper_daemon.py"),
        ("Portfolio & Price Sentinel v2.0", "portfolio_price_sentinel.py"),
        ("Twitter Alpha Sentinel", "twitter_alpha_sentinel.py")
    ]
    
    processes = []
    for name, script in scripts:
        script_path = os.path.join(BASE_DIR, script)
        if os.path.exists(script_path):
            print(f"▶️ Starting: {name}...")
            p = subprocess.Popen([sys.executable, script_path])
            processes.append((name, p))
            time.sleep(1)
        else:
            print(f"⚠️ Missing: {script_path}")
            
    print("=" * 60)
    print("✅ All services active! Press Ctrl+C to terminate all.")
    print("=" * 60)
    
    try:
        while True:
            time.sleep(5)
            for name, p in processes:
                if p.poll() is not None:
                    print(f"⚠️ Warning: {name} stopped with exit code {p.returncode}. Restarting...")
                    script_path = os.path.join(BASE_DIR, script)
                    new_p = subprocess.Popen([sys.executable, script_path])
                    processes.remove((name, p))
                    processes.append((name, new_p))
    except KeyboardInterrupt:
        print("\n🛑 Shutting down all daemons...")
        for name, p in processes:
            p.terminate()
        print("Done.")

if __name__ == "__main__":
    start_daemons()
