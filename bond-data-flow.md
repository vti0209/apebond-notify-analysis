# bond-data-flow.md

## 1. Sequence Diagram: API → RPC → Tính toán → DB → Discord

**Flow tổng quát (từ `index.py`):**

1. `index.py` (Main Loop) gọi `fetch_and_update_bonds()`.
2. `execute_data.py` -> Gọi `requests.get(APEBOND_API_URL)` -> Lấy dữ liệu API.
3. `execute_data.py` -> Update dữ liệu vào bảng `list_bond_contract_notify`.
4. `index.py` -> Gọi `fetch_bond_data("EVM")` và `fetch_bond_data("SOL")`.
5. `execute_data.py` -> Truy vấn DB `list_bond_contract_notify` lấy các record `active`.
6. Luồng chia nhánh:
    - **Branch A (EVM):** `process_bonds(bond_datas_evm)`.
        - Dùng `web3.py` + Multicall để đọc State của Smart Contract.
        - Tính toán `bonus`.
    - **Branch B (Solana):** `process_bond_sol(bond_datas_sol)`.
        - Dùng `solana-py` RPC Client gọi `get_account_info`.
        - Parse `BondIssuance`, `BondPricing`, `BondTerm` từ Account Data Bytes.
        - Gọi `get_token_price_unified` để lấy giá Payout và Principal.
        - Tính toán `bonus`.
7. Kết quả từ 2 branch được gộp lại (list `bond_results`).
8. `save_and_notify_top_bonds_by_bonus()`:
    - Sắp xếp lấy **Top 10 theo max_bonus**.
    - `INSERT` dữ liệu của top 10 vào bảng `bond_history`.
    - Gọi `send_discord_webhook_message()` để gửi thông báo lên Discord.

## 2. Xử lý dữ liệu thô (On-chain Data Parsing)
- **EVM:** Sử dụng **Multicall V3** để gộp nhiều `eth_call` vào 1 RPC Request nhằm giảm latency và tránh rate limit.
- **Solana:** Sử dụng `struct` và `solders` để decode bytes raw từ `get_account_info`.
    - `parse_bond_issuance()`: Decode các biến liên quan đến Mint, Treasury, Fees.
    - `parse_bond_pricing()`: Decode Total Debt, Decay, Last Update.
    - `parse_bond_term()`: Decode Control Variable, Minimum Price, Max Payout.