# bond-notify-overview.md

## 1. Mục tiêu
Tool `bond_notify` là một hệ thống tự động dùng để quét, phân tích và thông báo các cơ hội đầu tư (Bond) từ giao thức **ApeBond** trên cả hai nền tảng blockchain là **EVM** (Ethereum, BSC, Polygon, Arbitrum, Base, Linea, Sonic, Berachain, Unichain, Hyperliquid) và **Solana**.

## 2. Kiến trúc tổng quan
Hệ thống được xây dựng theo mô hình **Batch Processing (Xử lý theo lô)**. Nó không chạy real-time theo block, mà chạy theo chu kỳ thời gian (mặc định 10 phút/lần trong vòng lặp).

**Entry Point (Điểm bắt đầu):**
- File chính: `index.py`
- Logic chạy chính nằm trong khối `if __name__ == "__main__":`.
- Luồng chính: 
    1. Cập nhật danh sách Bond từ API ApeBond vào DB.
    2. Lấy danh sách Bond cần theo dõi từ DB.
    3. Chia luồng xử lý (EVM và Solana).
    4. Tính toán Bonus/Price.
    5. Xếp hạng Top 10.
    6. Lưu lịch sử vào DB.
    7. Gửi thông báo Discord.

## 3. Công nghệ sử dụng
- **Ngôn ngữ:** Python 3.x
- **Thư viện EVM:** `web3.py`, `requests`
- **Thư viện Solana:** `solana-py` (v0.36.0), `solders`
- **Database:** `MySQL` (thông qua `mysql-connector-python`)
- **Môi trường config:** `python-dotenv` (file `.env`)
- **Đa luồng:** `concurrent.futures.ThreadPoolExecutor` để tăng tốc xử lý nhiều Bond cùng lúc.