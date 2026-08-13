# bond-target-modules.md

## 1. Phân biệt chức năng của từng Module

| Module / File | Vai trò chính | Đầu vào (Input) | Đầu ra (Output) |
| :--- | :--- | :--- | :--- |
| **index.py** | **Điều phối (Orchestrator)** | `.env` config, DB Schema | Top 10 Bond DB record, Discord Webhook |
| **config.py** | **Quản lý cấu hình** | `.env` file | Các biến toàn cục (Keys, RPC, Maps) |
| **execute_data.py** | **Database & API Handler** | APEBOND_API_URL, DB Connection | Bảng `list_bond_contract_notify` và `bond_history` |
| **process_bond_evm.py** | **EVM Parser** | RPC_URLs, Contract Addresses | Danh sách Bond EVM đã tính Bonus |
| **process_bond_sol.py** | **Solana Parser** | HELIUS_RPC_URL, Account Pubkeys | Danh sách Bond SOL đã tính Bonus |
| **helpers.py** | **Utility Functions** | Giá token, URL Webhook | Giá token hợp lệ, HTTP POST to Discord |

## 2. Sự khác biệt cốt lõi giữa luồng EVM và Solana

| Đặc điểm | Luồng EVM (`process_bond_evm.py`) | Luồng Solana (`process_bond_sol.py`) |
| :--- | :--- | :--- |
| **Cách truy vấn** | Gọi hàm Smart Contract (`eth_call`) thông qua Multicall. | Đọc trực tiếp Account Info (`get_account_info`) với Pubkey. |
| **Dữ liệu thô** | Dạng JSON (Decoded ABI) -> Dùng `web3` chuyển sang Python object. | Dạng Bytes (Binary) -> Dùng `struct` và `Pubkey` để decode thủ công từng byte. |
| **Địa chỉ Contract** | Dạng `0x...` (40 ký tự hex). | Dạng Base58 Pubkey (ví dụ `57GQDh...`). |
| **Phân biệt chain** | Dựa vào ID mạng trong `CHAIN_IDS` và `RPC_URLS` dictionary. | Chỉ có 1 RPC duy nhất là `HELIUS_RPC_URL`. |
| **Lấy Metadata** | Thường lấy trực tiếp từ Token Contract. | Phải tính PDA (Program Derived Address) với Metaplex Program ID để tìm Metadata Account. |

## 3. Rủi ro và câu hỏi cần xác nhận (Question Log)
1. **Metadata Solana:** `process_bond_sol.py` có bỏ qua lỗi khi không tìm thấy Metadata. Cần xác nhận việc thiếu Metadata có ảnh hưởng đến cách tính toán giá sau này không?
2. **Fallback Price:** `get_token_price_unified` sử dụng cả CoinGecko và DexScreener. Cần xác nhận độ trễ (Latency) của API này khi cache chưa có.
3. **Vesting Term bằng 0:** Trong code `calc_debt_decay`, nếu `vesting_term == 0` thì trả về `total_debt`. Đây là trường hợp Bond đã hết hạn cần xử lý đặc biệt?
4. **Hardcode Mainnet:** `RPC_URLS` đang hardcode các link Mainnet. Trong thực tế, code có cần hỗ trợ Testnet để dev không?
5. **Lỗi Database:** `list_bond_contract_notify` chưa có cột `updated_at` nếu chạy lần đầu, cần đảm bảo script init DB chạy trước khi tool chạy.