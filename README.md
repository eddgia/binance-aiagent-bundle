# 🚀 Binance AI Agent & Smart Sniper Suite v3.2

Trọn bộ công cụ tự động hóa & mã nguồn cho **Binance Agentic Wallet (`baw`)** trên mạng **BNB Smart Chain (BSC)**, sẵn sàng để ném vào **Muse** hoặc chạy độc lập 24/7.

---

## 🌟 Điểm Mới Nổi Bật Trong Bản v3.2

1. **Lọc Đồng Thuận Khắt Khe (> 10 Ví Smart Wallet)**:
   - Chỉ kích hoạt mint khi có **trên 10 ví smart wallet độc lập** (`>= 11 ví`) cùng mint cùng một contract trong vòng 1 giờ.
   - Loại bỏ 100% tình trạng bot spam mint rác vô thanh khoản làm hao hụt gas.

2. **Cơ Chế Bắt Thanh Khoản & Auto-Dump Về BNB Siêu Tốc**:
   - Quét pool PancakeSwap V2 liên tục mỗi **4 giây** cho toàn bộ token mới mint.
   - Khi phát hiện thanh khoản, lập tức xả sạch 100% token trực tiếp ra **BNB** (`0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE`) để tái nạp phí gas cho ví!

3. **Lá Chắn Bảo Vệ Gas (Gas Floor Shield)**:
   - Ngưỡng an toàn tối thiểu: `0.0015 BNB`. Nếu số dư ví tụt dưới ngưỡng này, hệ thống tự động ngừng mint mới.

4. **Theo Dõi Danh Mục Đầu Tư Toàn Diện (Portfolio Sentinel v2.0)**:
   - **FAGENT PoA Vault**: Giám sát tiến độ mở thẻ (#36,200+ / 38,000) và quỹ cổ tức Round 4 (hiện đạt 35+ BNB).
   - **Ptah Trade IAO**: Theo dõi hợp đồng huy động 424 BNB và đếm ngược giờ lập pool PancakeSwap.
   - **Hash21**: Giám sát phần thưởng $HASH, giá trị USD và thanh khoản pool.

5. **Theo Dõi Alpha Từ KOL Trên X (Twitter Alpha Sentinel)**:
   - Giám sát các tweet từ KOL hàng đầu (AKAKAY04, nancy_c813, erjie22...) để phát hiện sớm các đợt phát hành contract mới.

---

## 📁 Cấu Trúc Gói Bundle

```
binance-aiagent-bundle/
├── config.json                     # Cấu hình tập trung (RPC, Ví, Ngưỡng đồng thuận, Gas floor)
├── SKILL.md                        # Định nghĩa Skill cho Claude Code / Muse Agent
├── README.md                       # Tài liệu hướng dẫn sử dụng
├── data/
│   └── smart_wallets_list.json     # Cơ sở dữ liệu 4,942 Smart Wallets uy tín hàng đầu BSC
├── logs/                           # Thư mục lưu nhật ký vận hành tự động
│   ├── sniper_activity.log         # Lịch sử săn kèo mint & xả token
│   ├── portfolio_sentinel.log      # Lịch sử biến động giá Hash21, IAO & Vault FAGENT
│   └── twitter_alpha.log           # Lịch sử quét alpha từ KOLs
├── scripts/
│   ├── run_all.py                  # Kịch bản khởi chạy đồng thời tất cả daemon
│   ├── smart_sniper_daemon.py      # Daemon săn kèo v3.2 (>10 ví, canh LP 4s, dump BNB)
│   ├── portfolio_price_sentinel.py # Daemon canh giá & giám sát cổ tức v2.0
│   ├── twitter_alpha_sentinel.py   # Daemon quét tweet alpha
│   ├── ptah_iao_manager.py         # Kịch bản kiểm tra tiến độ IAO & airdrop
│   ├── market_order_swapper.py     # Công cụ swap nhanh token trên PancakeSwap qua BAW
│   ├── contract_interactor.py      # Công cụ mô phỏng & gọi contract an toàn
│   └── wallet_portfolio_scanner.py # Công cụ kiểm kê số dư & tài sản on-chain
└── references/                     # 17 tài liệu tra cứu lệnh BAW chi tiết
```

---

## 🛠️ Hướng Dẫn Kích Hoạt Nhanh

### Cách 1: Ném Trực Tiếp Vào Muse
- Chỉ cần ném thư mục `binance-aiagent-bundle` hoặc tệp `binance-aiagent-bundle.zip` vào **Muse**.
- Muse sẽ tự động đọc `SKILL.md` và hiểu toàn bộ tập lệnh, quy tắc an toàn cũng như cấu trúc dự án.

### Cách 2: Chạy Bằng Lệnh Terminal
```bash
# 1. Chạy tất cả các cỗ máy (Sniper + Sentinel + Alpha Tracker)
python scripts/run_all.py

# 2. Hoặc chạy riêng từng cỗ máy theo nhu cầu
python scripts/smart_sniper_daemon.py       # Săn mint & auto-dump về BNB
python scripts/portfolio_price_sentinel.py  # Canh giá & cổ tức
python scripts/ptah_iao_manager.py          # Kiểm tra tiến độ IAO & airdrop
python scripts/wallet_portfolio_scanner.py  # Kiểm kê tài sản ví
```
