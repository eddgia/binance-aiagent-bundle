#!/usr/bin/env python3
"""
Binance AI Agent Risk Guards & Helper Modules (v3.4)
Ported and enhanced from Nancy v2.7.2 audit:
1. ProxyResolver: Resolves EIP-1967 Implementation, Beacon slot, and EIP-1167 Minimal Proxy.
2. AgentExclusivityGuard: Verifies contract is Agent ID exclusive (bytecode or >=60% callers hold Agent ID).
3. PayloadAdapter: Replaces expired deadlines, foreign recipients, and foreign Agent Token IDs.
4. HoneypotChecker: Simulates token transfer to Pancake pair prior to sell execution.
5. DevHoldingGuard: Checks if contract dev / owner holds > 30% of total token supply.
6. ApprovalsWatchdog: Periodically monitors BAW approvals and revokes malicious/compromised spenders.
"""

import sys
import os
import json
import time
import subprocess
import shutil
import urllib.request
import ssl

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUNDLE_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(BUNDLE_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

RPC_URL = "https://bsc-dataseed.binance.org"
REGISTRY = "0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F".lower()
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c".lower()
USDT = "0x55d398326f99059fF775485246999027B3197955".lower()
BAW_CMD = shutil.which("baw") or shutil.which("baw.cmd") or "baw"

ctx = ssl._create_unverified_context()

def rpc(method, params, timeout=10):
    req = urllib.request.Request(
        RPC_URL,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            res = json.loads(r.read().decode("utf-8"))
            return res.get("result")
    except Exception:
        return None

def eth_call(to, data, from_addr=None):
    params = [{"to": to, "data": data}]
    if from_addr:
        params[0]["from"] = from_addr
    return rpc("eth_call", [params[0], "latest"])


class ProxyResolver:
    """Resolves implementation code behind upgradeable proxies and clones."""

    @staticmethod
    def get_full_code(contract_addr):
        addr = contract_addr.lower()
        code = (rpc("eth_getCode", [addr, "latest"]) or "").lower()
        if len(code) < 4:
            return code
        if REGISTRY[2:] in code:
            return code

        # 1. EIP-1967 Implementation Slot
        impl_slot = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
        impl_val = rpc("eth_getStorageAt", [addr, impl_slot, "latest"])
        if impl_val and int(impl_val, 16) != 0:
            impl_addr = "0x" + impl_val[-40:].lower()
            code += (rpc("eth_getCode", [impl_addr, "latest"]) or "").lower()

        # 2. EIP-1967 Beacon Slot
        beacon_slot = "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"
        bc_val = rpc("eth_getStorageAt", [addr, beacon_slot, "latest"])
        if bc_val and int(bc_val, 16) != 0:
            bc_addr = "0x" + bc_val[-40:].lower()
            bc_impl = eth_call(bc_addr, "0x5c60da1b") # implementation()
            if bc_impl and len(bc_impl) >= 66 and int(bc_impl, 16) != 0:
                impl_addr = "0x" + bc_impl[-40:].lower()
                code += (rpc("eth_getCode", [impl_addr, "latest"]) or "").lower()

        # 3. EIP-1167 Minimal Proxy check: 363d3d373d3d3d363d73<target>5af4...
        if "363d3d373d3d3d363d73" in code:
            idx = code.find("363d3d373d3d3d363d73") + len("363d3d373d3d3d363d73")
            target_addr = "0x" + code[idx:idx+40]
            code += (rpc("eth_getCode", [target_addr, "latest"]) or "").lower()

        return code


class AgentExclusivityGuard:
    """Verifies whether a contract is an exclusive .ai Agent ID project."""

    def __init__(self):
        self.cache = {}

    def is_agent_exclusive(self, contract_addr):
        addr = contract_addr.lower()
        if addr in self.cache:
            return self.cache[addr]

        code = ProxyResolver.get_full_code(addr)
        reg_clean = REGISTRY[2:].lower()
        if reg_clean in code:
            self.cache[addr] = (True, "Bytecode contains Space ID / Agent ID Registry")
            return self.cache[addr]

        # Check caller consensus over recent blocks
        curr_blk_hex = rpc("eth_blockNumber", [])
        if not curr_blk_hex:
            return False, "Could not fetch current block"
        curr_blk = int(curr_blk_hex, 16)
        from_blk = hex(max(0, curr_blk - 2000))

        logs = rpc("eth_getLogs", [{"address": addr, "fromBlock": from_blk, "toBlock": "latest"}]) or []
        tx_hashes = list(set(l.get("transactionHash") for l in logs if l.get("transactionHash")))[-25:]

        callers = set()
        for th in tx_hashes:
            tx_info = rpc("eth_getTransactionByHash", [th])
            if tx_info and tx_info.get("from"):
                callers.add(tx_info["from"].lower())

        if len(callers) >= 4:
            agent_holders = 0
            sample_callers = list(callers)[:12]
            for c in sample_callers:
                pad_c = c[2:].rjust(64, "0")
                bal_res = eth_call(REGISTRY, "0x70a08231" + pad_c)
                if bal_res and int(bal_res, 16) > 0:
                    agent_holders += 1
            pct = agent_holders / len(sample_callers)
            if pct >= 0.60:
                self.cache[addr] = (True, f"Consensus verified: {agent_holders}/{len(sample_callers)} ({pct*100:.0f}%) callers hold Agent ID")
                return self.cache[addr]
            self.cache[addr] = (False, f"Only {agent_holders}/{len(sample_callers)} ({pct*100:.0f}%) callers hold Agent ID")
            return self.cache[addr]

        self.cache[addr] = (False, "Contract does not reference Agent ID registry and lacks verified caller consensus")
        return self.cache[addr]


class PayloadAdapter:
    """Adapts copied calldata: replaces expired timestamps, recipient addresses, and Agent ID TokenIds."""

    @staticmethod
    def adapt(calldata, user_wallet, user_token_id, contract_addr=None):
        if not calldata or len(calldata) < 10:
            return calldata

        sel = calldata[:10]
        payload = calldata[10:]
        if len(payload) % 64 != 0:
            return calldata

        words = [payload[i:i+64] for i in range(0, len(payload), 64)]
        now = int(time.time())
        user_addr_clean = user_wallet[2:].lower().rjust(64, "0")
        user_tid_hex = hex(int(user_token_id))[2:].rjust(64, "0") if user_token_id else ""

        new_words = []
        for w in words:
            w_lower = w.lower()
            val = int(w, 16)

            # 1. Fresh Deadline Timestamp (within 30 days of now)
            if (now - 30 * 86400) < val < (now + 30 * 86400):
                fresh = hex(now + 900)[2:].rjust(64, "0")
                new_words.append(fresh)
                continue

            # 2. Agent ID Token ID (> 2^128)
            if user_tid_hex and val > 2**128 and w_lower != user_tid_hex.lower():
                owner_res = eth_call(REGISTRY, "0x6352211e" + w)
                if owner_res and len(owner_res) >= 66 and int(owner_res, 16) != 0:
                    new_words.append(user_tid_hex)
                    continue

            # 3. Foreign Recipient Address parameter
            if w_lower.startswith("000000000000000000000000") and w_lower[24:] != "0000000000000000000000000000000000000000":
                param_addr = "0x" + w_lower[24:]
                skip_set = {user_wallet.lower(), WBNB, USDT}
                if contract_addr:
                    skip_set.add(contract_addr.lower())
                if param_addr not in skip_set:
                    # Test substituting with user_wallet
                    test_words = list(new_words) + [user_addr_clean] + words[len(new_words)+1:]
                    test_calldata = sel + "".join(test_words)
                    if contract_addr:
                        sim_call = eth_call(contract_addr, test_calldata, from_addr=user_wallet)
                        if sim_call is not None:
                            new_words.append(user_addr_clean)
                            continue

            new_words.append(w)

        return sel + "".join(new_words)


class HoneypotChecker:
    """Pre-sell simulation to detect honeypots where transfer to LP pair reverts."""

    @staticmethod
    def simulate_sell_transfer(token_addr, pair_addr, amount=1000):
        pad_pair = pair_addr[2:].lower().rjust(64, "0")
        amount_hex = hex(amount)[2:].rjust(64, "0")
        calldata = "0xa9059cbb" + pad_pair + amount_hex
        res = eth_call(token_addr, calldata)
        if res is None:
            return False, "Transfer to Pancake pair reverted (Likely Honeypot / Transfer Blocked)"
        return True, "Clean (Transfer to Pancake pair simulated successfully)"


class DevHoldingGuard:
    """Detects whether dev or contract owner holds > 30% of total token supply."""

    @staticmethod
    def check_dev_holding(token_addr, deployer_addr=None, warning_pct=0.30):
        res_ts = eth_call(token_addr, "0x18160ddd") # totalSupply()
        if not res_ts or res_ts == "0x":
            return False, 0.0, "Could not read totalSupply"
        total_supply = int(res_ts, 16)
        if total_supply == 0:
            return False, 0.0, "Zero totalSupply"

        devs = set()
        if deployer_addr:
            devs.add(deployer_addr.lower())
        res_ow = eth_call(token_addr, "0x8da5cb5b") # owner()
        if res_ow and len(res_ow) >= 66 and int(res_ow, 16) != 0:
            devs.add("0x" + res_ow[-40:].lower())

        max_pct = 0.0
        heavy_dev = None
        for d in devs:
            pad_d = d[2:].rjust(64, "0")
            bal_res = eth_call(token_addr, "0x70a08231" + pad_d)
            if bal_res and bal_res != "0x":
                b = int(bal_res, 16)
                pct = b / total_supply
                if pct > max_pct:
                    max_pct = pct
                    heavy_dev = d

        if max_pct > warning_pct:
            return True, max_pct, f"Dev/Owner {heavy_dev} holds {max_pct*100:.1f}% > {warning_pct*100:.0f}% of supply (Heavy Dev Dump Risk)"
        return False, max_pct, f"Dev/Owner holds {max_pct*100:.1f}% (Normal)"


class ApprovalsWatchdog:
    """Scans active BAW approvals and revokes any authorizations to compromised spenders."""

    COMPROMISED_KEYWORDS = {"flap", "drainer", "phish", "fake"}

    @classmethod
    def scan_and_revoke(cls):
        try:
            cmd = [BAW_CMD, "approvals", "list", "--limit", "100", "--json"]
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
            if res.returncode != 0:
                return []
            data = json.loads(res.stdout)
            if not data.get("success"):
                return []

            revoked = []
            approvals = data.get("data", {}).get("list", [])
            for item in approvals:
                spender_name = (item.get("spenderName") or "").lower()
                spender_addr = (item.get("spender") or "").lower()
                tok = item.get("tokenContract")
                app_type = item.get("type", "approve")

                is_risky = any(k in spender_name for k in cls.COMPROMISED_KEYWORDS)
                if is_risky and tok and spender_addr:
                    revoke_cmd = [
                        BAW_CMD, "approvals", "revoke",
                        "--binanceChainId", "56",
                        "--tokenContract", tok,
                        "--spender", spender_addr,
                        "--type", app_type,
                        "--json"
                    ]
                    rev_res = subprocess.run(revoke_cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20)
                    if rev_res.returncode == 0:
                        revoked.append({"token": tok, "spender": spender_addr, "name": spender_name})
            return revoked
        except Exception:
            return []


class NftStrictGuard:
    """Nancy v2.7.3: Deep NFT artwork validation and duplicate image detection across contracts."""

    def __init__(self, data_dir=DATA_DIR):
        self.seen_path = os.path.join(data_dir, "seen_nft_images.json")
        self.seen = self._load()

    def _load(self):
        if os.path.exists(self.seen_path):
            try:
                with open(self.seen_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        try:
            with open(self.seen_path, "w", encoding="utf-8") as f:
                json.dump(self.seen, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def _resolve_gw(url):
        if not url:
            return ""
        if url.startswith("ipfs://"):
            return "https://ipfs.io/ipfs/" + url[7:]
        return url

    def check_nft_strict(self, contract_addr):
        ca = contract_addr.lower()
        # Query tokenURI(1), tokenURI(0), uri(1)
        uri = ""
        for sel, tid in [("0xc87b56dd", "0000000000000000000000000000000000000000000000000000000000000001"),
                         ("0xc87b56dd", "0000000000000000000000000000000000000000000000000000000000000000"),
                         ("0x0e89341c", "0000000000000000000000000000000000000000000000000000000000000001")]:
            res = eth_call(ca, sel + tid)
            if res and len(res) > 130:
                try:
                    s = bytes.fromhex(res[130:]).decode("utf-8", errors="ignore").strip("\x00")
                    if s:
                        uri = s
                        break
                except Exception:
                    pass

        if not uri:
            return True, "No public tokenURI yet (New deployment)"

        # Parse metadata
        meta = None
        try:
            if uri.startswith("data:application/json;base64,"):
                import base64
                meta = json.loads(base64.b64decode(uri.split(",")[1]).decode("utf-8"))
            elif uri.startswith("data:application/json,"):
                import urllib.parse
                meta = json.loads(urllib.parse.unquote(uri.split(",")[1]))
            elif uri.startswith("http://") or uri.startswith("https://") or uri.startswith("ipfs://"):
                url = self._resolve_gw(uri)
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8, context=ctx) as r:
                    meta = json.loads(r.read().decode("utf-8", errors="ignore"))
        except Exception:
            pass

        if not meta or not isinstance(meta, dict):
            return True, "Metadata not yet parsed or off-chain"

        img = meta.get("image") or meta.get("image_url") or meta.get("animation_url")
        if not img:
            return False, "NFT metadata exists but contains no valid image link"

        # Calculate image hash / normalized signature
        import hashlib
        img_sig = ""
        try:
            if img.startswith("data:image/"):
                img_sig = hashlib.sha256(img.encode("utf-8")).hexdigest()
            else:
                img_url = self._resolve_gw(img)
                req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
                    img_bytes = r.read(512000)
                    if len(img_bytes) > 100:
                        img_sig = hashlib.sha256(img_bytes).hexdigest()
        except Exception:
            img_sig = hashlib.sha256(str(img).encode("utf-8")).hexdigest()

        if img_sig:
            if img_sig in self.seen and self.seen[img_sig] != ca:
                prior_contract = self.seen[img_sig]
                return False, f"Duplicate NFT image detected! Exact artwork was already used in contract {prior_contract[:10]}... (Rug/Spam prevention)"
            self.seen[img_sig] = ca
            self._save()

        return True, "Valid distinctive NFT artwork verified"


class HybridPaidGuard:
    """Nancy v2.7.4: Detects contracts where the first mint is free but others are paying."""

    @staticmethod
    def is_hybrid_paid(contract_addr):
        ca = contract_addr.lower()
        curr_blk_hex = rpc("eth_blockNumber", [])
        if not curr_blk_hex:
            return False
        curr_blk = int(curr_blk_hex, 16)
        from_blk = hex(max(1, curr_blk - 1500))

        logs = rpc("eth_getLogs", [{"address": ca, "fromBlock": from_blk, "toBlock": "latest"}]) or []
        tx_hashes = list(set(l.get("transactionHash") for l in logs if l.get("transactionHash")))[-20:]
        if len(tx_hashes) < 4:
            return False

        paid_calls = 0
        total_calls = 0
        for th in tx_hashes:
            tx = rpc("eth_getTransactionByHash", [th])
            if tx and (tx.get("to") or "").lower() == ca:
                total_calls += 1
                if int(tx.get("value", "0x0"), 16) > 0:
                    paid_calls += 1

        if total_calls >= 4 and (paid_calls / total_calls) >= 0.50:
            return True
        return False


class TargetedPhishingGuard:
    """Nancy v2.8.0: Anti-Targeted Phishing Guard.
    Prevents scam projects with tiny pools where a few wallets artificially push progress to 70%.
    Criteria:
    1. Total pool market cap must be >= 10 BNB (cap * unitPrice >= 10 BNB).
    2. Sold shares must be >= 500 OR raised >= 5 BNB.
    3. Our wallet cannot buy > 2% of total cap.
    """
    @staticmethod
    def check_pool_depth(contract_addr, unit_bnb, total_cap, sold_shares):
        ca = contract_addr.lower()
        if unit_bnb > 0 and total_cap:
            total_raised_bnb = total_cap * unit_bnb
            if total_raised_bnb < 10.0:
                return False, f"Targeted Phishing: Total pool too small ({total_cap} shares * {unit_bnb:.4f} BNB = {total_raised_bnb:.2f} BNB < 10 BNB threshold)"
        if sold_shares is not None:
            raised_so_far = (sold_shares * unit_bnb) if unit_bnb > 0 else 0
            if sold_shares < 500 and (unit_bnb == 0 or raised_so_far < 5.0):
                return False, f"Targeted Phishing: Sold shares too low ({sold_shares} shares, ~{raised_so_far:.2f} BNB < 500 shares / 5 BNB threshold)"
        return True, "Passed pool depth & anti-targeted phishing audit"

    @staticmethod
    def get_max_our_bnb(total_cap, unit_bnb, num_wallets=1):
        if total_cap and unit_bnb > 0:
            return (total_cap * unit_bnb * 0.02) / max(1, num_wallets)
        return 0.0


class SybilAgentGuard:
    """Nancy v2.8.1: Anti-Sybil Alt-Account Guard.
    When verifying the 100+ Agent ID wallet consensus, filters out:
    1. Fresh Agent IDs registered within 24 hours (last ~28,800 BSC blocks).
    2. Wallets with < 8 transactions on-chain (throwaway bot wallets).
    """
    _fresh_agents = set()
    _last_fresh_check = 0
    _nonce_cache = {}

    @classmethod
    def get_fresh_agents(cls):
        now = time.time()
        if cls._fresh_agents and (now - cls._last_fresh_check < 900):  # 15 mins cache
            return cls._fresh_agents
        try:
            head_hex = rpc("eth_blockNumber", [])
            if not head_hex:
                return cls._fresh_agents
            head = int(head_hex, 16)
            fresh_set = set()
            topic_transfer = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
            topic_zero = "0x" + "0" * 64
            from_blk = hex(max(1, head - 28800))
            logs = rpc("eth_getLogs", [{
                "address": REGISTRY,
                "fromBlock": from_blk,
                "toBlock": hex(head),
                "topics": [topic_transfer, topic_zero]
            }]) or []
            for l in logs:
                topics = l.get("topics") or []
                if len(topics) >= 3:
                    recipient = "0x" + topics[2][-40:].lower()
                    fresh_set.add(recipient)
            cls._fresh_agents = fresh_set
            cls._last_fresh_check = now
        except Exception:
            pass
        return cls._fresh_agents

    @classmethod
    def filter_valid_agents(cls, address_list):
        fresh = cls.get_fresh_agents()
        valid_agents = []
        for addr in address_list:
            a = addr.lower()
            if a in fresh:
                continue
            nonce = cls._nonce_cache.get(a)
            if nonce is None:
                nonce_hex = rpc("eth_getTransactionCount", [a, "latest"])
                nonce = int(nonce_hex, 16) if nonce_hex else 0
                cls._nonce_cache[a] = nonce
            if nonce >= 8:
                valid_agents.append(a)
        return valid_agents


class ContractTreasuryGuard:
    """Nancy v2.7.8: Safe Treasury Assets Accounting.
    When checking if funds are drained from a project contract, counts held BNB, WBNB, and USDT
    to prevent false positives on legit projects holding assets in stablecoins/wrapped tokens.
    """
    @staticmethod
    def get_contract_treasury_value_bnb(contract_addr):
        ca = contract_addr.lower()
        bal_bnb_hex = rpc("eth_getBalance", [ca, "latest"])
        bnb_val = int(bal_bnb_hex, 16) / 1e18 if bal_bnb_hex else 0.0
        padded_ca = ca[2:].rjust(64, "0")
        wbnb_bal_hex = rpc("eth_call", [{"to": WBNB, "data": "0x70a08231" + padded_ca}, "latest"])
        if wbnb_bal_hex and wbnb_bal_hex != "0x":
            bnb_val += int(wbnb_bal_hex, 16) / 1e18
        usdt_bal_hex = rpc("eth_call", [{"to": USDT, "data": "0x70a08231" + padded_ca}, "latest"])
        if usdt_bal_hex and usdt_bal_hex != "0x":
            usdt_amt = int(usdt_bal_hex, 16) / 1e18
            bnb_val += (usdt_amt / 700.0)
        return bnb_val

