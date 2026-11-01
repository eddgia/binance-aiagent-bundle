# 🚀 Binance AI Agent & Smart Sniper Suite v3.4

Trọn bộ công cụ tự động hóa & mã nguồn cho **Binance Agentic Wallet (`baw`)** trên mạng **BNB Smart Chain (BSC)**, tích hợp toàn diện các chuẩn kiểm soát rủi ro từ **Nancy v2.7.2** và chạy độc lập 24/7.

---

## 🌟 Điểm Mới Nổi Bật Trong Bản v3.4 (Nancy v2.7.2 Deep Integration)

1. **Xác Minh Độc Quyền Agent ID (Agent ID Exclusivity Guard)**:
   - Tự động kiểm tra mã bytecode contract xem có liên kết hợp đồng Space ID Registry (`0x60B9...022F`) hay không.
   - Hỗ trợ **phân giải Proxy (ProxyResolver)**: Tự động truy vết EIP-1967 Implementation slot, Beacon slot (`0x5c60da1b`), và EIP-1167 Minimal Proxy clone để không bỏ sót các hợp đồng ủy quyền như FAGENT hay bibiai.
   - Nếu contract dùng xác minh chữ ký backend website: Phân tích 3,000 block gần nhất, **yêu cầu tối thiểu 60% số ví gọi contract phải sở hữu .ai Agent ID thật** mới kích hoạt. Loại bỏ triệt để các dự án memecoin mạo danh.

2. **Tự Động Chuẩn Hóa & Thích Ứng Dữ Liệu Gọi (Dynamic Calldata Adapter)**:
   - **Làm mới thời hạn (Fresh Deadline)**: Tự động phát hiện các tham số timestamp sắp hết hạn trong calldata và gia hạn thành `now + 15 phút` để tránh lỗi `EXPIRED_DEADLINE`.
   - **Thay thế người nhận (Safe Address)**: Phát hiện địa chỉ ví của người khác trong calldata và tự động thay bằng địa chỉ ví của chủ nhân (`USER_WALLET`).
   - **Thay thế mã Token ID Agent (Safe Agent Token ID)**: Phát hiện mã `tokenId` Agent ID của người khác và tự động thay bằng mã Token ID chính chủ của tên miền `dop.ai` (`5834...39146`).

3. **Mô Phỏng Phòng Chống Rút Ruột & Rọ Lừa (Honeypot Pre-sell Simulation)**:
   - Trước khi thực hiện lệnh xả token trên PancakeSwap, bot tự động mô phỏng chuyển token vào cặp LP qua `eth_call`.
   - Nếu hàm chuyển bị chặn (dấu hiệu Honeypot chỉ cho mua/mint mà không cho bán), bot lập tức hủy lệnh để bảo toàn phí gas.

4. **Cảnh Báo Gom Hàng Dev (Dev Heavy Holding Guard)**:
   - Kiểm tra ví deployer và owner (`0x8da5cb5b`).
   - Nếu dev/owner nắm giữ **trên 30% tổng cung** token, bot ghi nhận cảnh báo nguy cơ xả hàng (dump risk) tức thì.

5. **Giới Hạn Chi Tiêu Mint Có Phí (Daily Paid Cap: $60 USD/ngày)**:
   - Giám sát tổng chi phí mint trả phí hàng ngày, dừng khi chạm ngưỡng 60 USD (hoặc tương đương trong BNB/USDT), tự động reset lúc 00:00 UTC.

6. **Chó Săn Rà Soát Ủy Quyền Nguy Hiểm (Approvals Watchdog)**:
   - Quét danh sách ủy quyền (`baw approvals list`) định kỳ mỗi 10 phút.
   - Tự động thu hồi (`baw approvals revoke`) các ủy quyền đối với các địa chỉ độc hại hoặc giao thức từng bị chiếm quyền DNS (như Flap).

7. **Bộ 4 Lớp Kiểm Soát Rủi Ro Cốt Lõi (v3.3)**:
   - **Daily spend cap (0.01 BNB/ngày gas)**: Đọc receipt on-chain thực tế, dừng khi hết quota gas.
   - **Mass-deployer skip (≥10 deploy/24h)**: Chặn deployer spam hàng loạt.
   - **Junk-NFT check (tokenURI)**: Loại bỏ NFT không có hình/metadata rác.
   - **Fail limit (2 lần/contract/ngày)**: Dừng thử lại contract lỗi quá 2 lần trong ngày.

---

## 📁 Cấu Trúc Gói Bundle

```
binance-aiagent-bundle/
├── config.json                     # Cấu hình tập trung (RPC, Ví, Agent ID, Cap chi tiêu, Tham số rủi ro)
├── SKILL.md                        # Định nghĩa Skill cho Claude Code / Muse Agent
├── README.md                       # Tài liệu hướng dẫn sử dụng
├── data/
│   ├── deployer_cache.json         # Bộ nhớ đệm số contract của từng deployer
│   └── smart_wallets_list.json     # Cơ sở dữ liệu 4,942 Smart Wallets uy tín hàng đầu BSC
├── logs/                           # Thư mục lưu nhật ký vận hành tự động
│   ├── risk_state.json             # Trạng thái rủi ro (quota gas, quota chi tiêu, lỗi contract)
│   ├── sniper_activity.log         # Lịch sử săn kèo mint & xả token
│   ├── portfolio_sentinel.log      # Lịch sử biến động giá Hash21, IAO & Vault FAGENT
│   ├── session_keepalive.log       # Lịch sử giữ nhịp kết nối ví BAW
│   └── twitter_alpha.log           # Lịch sử quét alpha từ KOLs
├── scripts/
│   ├── risk_guards.py              # Thư viện bảo mật (ProxyResolver, AgentExclusivity, PayloadAdapter, Honeypot, DevHolding, ApprovalsWatchdog)
│   ├── run_all.py                  # Kịch bản khởi chạy & tự phục hồi toàn bộ daemon
│   ├── session_keepalive_daemon.py # Daemon duy trì phiên BAW chống ngắt kết nối
│   ├── smart_sniper_daemon.py      # Daemon săn kèo v3.4 (tích hợp 9 lớp kiểm soát rủi ro)
│   ├── portfolio_price_sentinel.py # Daemon canh giá & giám sát cổ tức v2.2 (tích hợp ApprovalsWatchdog)
│   ├── twitter_alpha_sentinel.py   # Daemon quét tweet alpha
│   ├── ptah_iao_manager.py         # Kịch bản kiểm tra tiến độ IAO & airdrop
│   ├── market_order_swapper.py     # Công cụ swap nhanh token trên PancakeSwap qua BAW
│   ├── solve_agentic_pixels.py     # Giải toán PoW on-chain Agentic Pixels & kiểm tra $AGENT
│   ├── veil_sentinel.py            # Giám sát unpause Robinhood Chain (4663) & Veil ZK Router
│   ├── fist_agent_manager.py       # Kiểm định Agent ID allocation FISTAGENT
│   ├── contract_interactor.py      # Công cụ mô phỏng & gọi contract an toàn
│   └── wallet_portfolio_scanner.py # Công cụ kiểm kê số dư & tài sản on-chain
└── references/                     # 17 tài liệu tra cứu lệnh BAW chi tiết
```

---

## 🛠️ Hướng Dẫn Vận Hành

```bash
# Khởi chạy toàn bộ hệ thống daemon (Keepalive + Smart Sniper v3.4 + Sentinel v2.2 + Twitter Alpha)
python scripts/run_all.py
```
Hệ thống tự động giám sát các tiến trình con, tự phục hồi nếu xảy ra sự cố ngắt quãng và ghi nhật ký đầy đủ tại thư mục `logs/`.
