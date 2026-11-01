# 🚀 Binance AI Agent & Smart Sniper Suite v3.5

Trọn bộ công cụ tự động hóa & mã nguồn cho **Binance Agentic Wallet (`baw`)** trên mạng **BNB Smart Chain (BSC)**, tích hợp toàn diện các chuẩn kiểm soát rủi ro từ **Nancy v2.8.3** và chạy độc lập 24/7.

---

## 🌟 Điểm Mới Nổi Bật Trong Bản v3.5 (Nancy v2.8.3 Deep Integration)

1. **Phòng Chống Dự Án Câu Nhử / Định Điểm (Anti-Targeted Phishing Guard - v2.8.0)**:
   - Ngăn chặn triệt để thủ đoạn dev tạo dự án có tổng quỹ cực nhỏ (ví dụ chỉ 1 BNB hoặc 20 suất), tự dùng ví phụ mint đẩy tiến độ lên 70% để bẫy bot theo sau.
   - **Quy tắc kiểm duyệt**:
     - Tổng quy mô đợt mở bán (`Total Cap`) phải **$\ge 10$ BNB**.
     - Đã bán tối thiểu **$\ge 500$ suất** HOẶC đã huy động thực tế **$\ge 5$ BNB**.
     - Hạn mức mua tối đa của ví bot không vượt quá **2% tổng quỹ dự án**.

2. **Chống Tài Khoản Ảo / Sybil Tự Thổi Hot (Anti-Sybil Alt-Account Filter - v2.8.1)**:
   - Khi tính toán số lượng ví Agent ID tham gia (ngưỡng 100+ ví):
     - **Loại trừ ví non trẻ**: Các ví vừa đăng ký `.ai` Agent ID trong vòng 24 giờ qua sẽ không được tính.
     - **Loại trừ ví rác/bot**: Các ví có số lượng giao dịch on-chain (nonce) **dưới 8 giao dịch** bị loại bỏ, tránh việc dev tạo hàng loạt ví rác để giả mạo cộng đồng đông đảo.

3. **Giám Sát Mở Pool & Bắt Đỉnh Tức Thì 15 Giây (Rapid 15s Open Sentinel - v2.8.2)**:
   - Vòng lặp `openWatch` độc lập quét mỗi 15 giây đối với các token vừa mint xong đang chờ thêm thanh khoản PancakeSwap V2.
   - Khi pool vừa mở trong vòng 30 phút đầu, bot theo dõi giá mỗi 15 giây để nắm bắt biến động nhạy bén, không bị trễ theo chu kỳ kiểm tra danh mục thông thường.

4. **Tự Động Mua Token AI Thịnh Hành (AI Trending Token Scanner - v2.8.3)**:
   - Tự động phát hiện các token mới có trên 100 ví Agent ID thực tương tác mua trong vòng 20 phút.
   - Kiểm tra an toàn: Không phải token cũ (> 3 ngày), thuế mua/bán $\le 10\%$, thanh khoản $\ge 10$ BNB, vượt qua kiểm tra Honeypot.

5. **Bộ Nhớ Đệm Chặn Đứng Mass-Deployer (Cached Mass-Deployer Skip - v2.7.7)**:
   - Các deployer bị phát hiện tạo $\ge 10$ contract/24h sẽ được đưa vào danh sách đen vĩnh viễn trong bộ nhớ đệm, giúp bot từ chối ngay lập tức các contract tiếp theo mà không tốn truy vấn RPC.

6. **Tính Đúng Tài Sản Ngân Khố (Treasury Asset Accounting - v2.7.8)**:
   - Khi đánh giá an toàn dòng tiền của dự án, bot tính cả số dư USDT (`0x55d3...7955`) và WBNB (`0xbb4C...095c`) trong hợp đồng, tránh báo động giả với các dự án swap tiền quyên góp sang stablecoin.

7. **Bộ Lớp Kiểm Soát Rủi Ro Kế Thừa (v3.4 / Nancy v2.7.3 & v2.7.4)**:
   - **Xác minh Agent ID độc quyền**: Qua bytecode & ProxyResolver (EIP-1967/Beacon/EIP-1167).
   - **Chống lặp hình ảnh NFT**: Kiểm tra mã băm SHA-256 ảnh gốc, chặn NFT rác dùng lại ảnh cũ.
   - **Xử lý Hybrid Paid**: Phát hiện hợp đồng có $\ge 50\%$ lượt gọi trả phí để áp trần ngân sách.
   - **Daily spend cap (0.01 BNB gas/ngày)** & **Fail limit (2 lần/contract/ngày)**.

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
