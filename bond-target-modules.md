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
1. **Metadata Solana:** `process_bond_sol.py` có xử lý try-catch khi không tìm thấy Metadata. Cần xác nhận việc thiếu Metadata có ảnh hưởng đến cách hiển thị thông tin hay không (hiện tại tên bond vẫn được lấy từ DB).
2. **Fallback Price:** `get_token_price_unified` sử dụng thứ tự: ApeBond API -> CoinGecko -> DexScreener. Cần xác nhận độ trễ (Latency) của API này khi cache chưa có.
3. **Vesting Term bằng 0:** Trong code `calc_debt_decay`, nếu `vesting_term == 0` thì trả về `total_debt`. Đây là trường hợp Bond đã hết hạn cần xử lý đặc biệt?
4. **Hardcode Mainnet & Keys:** `RPC_URLS` đang dùng link Mainnet và API Key hardcode. Cần chuyển các key này sang `.env`.
5. **Cập nhật Bug Fix:** Lỗi thiếu import `get_connection` trong `index.py` và `API_URLS` trong `process_bond_evm.py` đã được sửa hoàn tất.