# bond-dependency-map.md

## Cấu trúc cây phụ thuộc (Import Tree)

**Main Entry:** `index.py`
- Chạy vòng lặp chính và điều phối luồng.

**Phụ thuộc bậc 1:**
- `execute_data.py`: Xử lý toàn bộ Database và tương tác với API ApeBond.
    - *Phụ thuộc:* `config.py` (DB_CONFIG), `mysql.connector`, `requests`.
- `process_bond_evm.py`: Xử lý dữ liệu EVM.
    - *Phụ thuộc:* `config.py`, `call_multicall.py`, `web3`, `helpers.py`, `logging_setup.py`.
- `process_bond_sol.py`: Xử lý dữ liệu Solana.
    - *Phụ thuộc:* `config.py`, `solana.rpc.api`, `solders`, `helpers.py`, `mysql.connector`, `logging_setup.py`.
- `helpers.py`: Các hàm hỗ trợ (lấy giá token, discord webhook, tính giờ ngủ...).
    - *Phụ thuộc:* `config.py`, `requests`.
- `logging_setup.py`: Cấu hình hệ thống Log.
- `call_multicall.py`: Hàm gọi contract EVM qua Multicall.
    - *Phụ thuộc:* `config.py` (RPC_URLS, MULTICALL_V3_ADDRESS).

## Xác định Module sở hữu:
- **Pricing (Định giá):** `process_bond_evm.py` và `process_bond_sol.py` (các hàm `calc_...` nằm trong 2 file này).
- **Ranking (Xếp hạng):** `index.py` (hàm `save_and_notify_top_bonds_by_bonus`).
- **Persistence (Lưu DB):** `execute_data.py` (Tất cả các hàm `INSERT`, `UPDATE`, `CREATE TABLE`).
- **Notification (Thông báo):** `helpers.py` (hàm `send_discord_webhook_message`).

## Config & Dữ liệu nhạy cảm:
- Tất cả các biến cấu hình, API Key, RPC URL, Discord Webhook được tập trung vào file **`config.py`** (đọc từ `.env`).
- **Lưu ý bảo mật:** File `.env` nằm trong `.gitignore` để không bị đẩy lên GitHub, tránh lộ API Key.