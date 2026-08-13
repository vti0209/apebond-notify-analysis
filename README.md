# 🚀 ApeBond Notify

**Automated Bond Monitoring, Analysis, Ranking & Notification System**

**Hệ thống tự động giám sát, phân tích, xếp hạng và thông báo cơ hội Bond**

---

# 🇬🇧 English

## 1. Project Overview

**ApeBond Notify** is an automated system designed to monitor, analyze, rank, and notify users about bonding opportunities from the **ApeBond** protocol.

The system supports both **EVM-compatible blockchains** and **Solana**.

### Main Features

* Synchronize active bond contracts from ApeBond.
* Monitor bond data across supported blockchain networks.
* Retrieve on-chain bond information.
* Calculate bond financial metrics.
* Retrieve token prices from external price providers.
* Rank bonds based on profitability.
* Store bond history in MySQL.
* Send qualified opportunities through Discord Webhook.
* Run automatically at configurable intervals.

---

## 2. Supported Networks

### EVM Networks

The project supports EVM-compatible networks including:

* Ethereum
* BNB Chain
* Polygon
* Arbitrum
* Base
* Linea
* Sonic
* Berachain

### Solana

Solana bonds are processed using Solana RPC and on-chain account data.

---

## 3. Technology Stack

| Component              | Technology                 |
| ---------------------- | -------------------------- |
| Programming Language   | Python 3.8+                |
| Database               | MySQL                      |
| EVM Interaction        | Web3.py, Multicall V3      |
| Solana Interaction     | Solana Python SDK, Solders |
| Environment Management | python-dotenv              |
| Concurrency            | ThreadPoolExecutor         |
| Notification           | Discord Webhook            |
| Token Price Sources    | CoinGecko / DexScreener    |

---

## 4. Project Structure

```text
apebond-notify/
│
├── index.py
├── config.py
├── helpers.py
├── execute_data.py
├── process_bond_evm.py
├── process_bond_sol.py
│
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

### Module Responsibilities

| Module                | Responsibility                                                 |
| --------------------- | -------------------------------------------------------------- |
| `index.py`            | Main execution flow, synchronization, ranking and notification |
| `process_bond_evm.py` | EVM bond data retrieval and calculations                       |
| `process_bond_sol.py` | Solana bond data retrieval and calculations                    |
| `execute_data.py`     | MySQL database operations                                      |
| `helpers.py`          | Shared utilities, token pricing and Discord notifications      |
| `config.py`           | Environment variables, RPC configuration and chain mappings    |

---

## 5. Installation

### Step 1 — Clone the Repository

```bash
git clone <your-repository-url>
cd apebond-notify
```

### Step 2 — Create Virtual Environment

#### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

#### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
```

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` is unavailable:

```bash
pip install python-dotenv requests web3 solana==0.36.0 solders mysql-connector-python
```

---

## 6. Configuration

Create a `.env` file in the project root:

```ini
ENV=local

DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

HELIUS_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_API_KEY

MIN_BONUS_NOTIFY=10.0

LOCAL_DB_HOST=localhost
LOCAL_DB_USER=root
LOCAL_DB_PASS=
LOCAL_DB_NAME=apebond-notify
LOCAL_DB_PORT=3306
```

### Configuration Parameters

| Variable              | Description                             |
| --------------------- | --------------------------------------- |
| `ENV`                 | Runtime environment                     |
| `DISCORD_WEBHOOK_URL` | Discord notification endpoint           |
| `HELIUS_RPC_URL`      | Solana RPC endpoint                     |
| `MIN_BONUS_NOTIFY`    | Minimum bonus required for notification |
| `LOCAL_DB_HOST`       | MySQL host                              |
| `LOCAL_DB_USER`       | MySQL username                          |
| `LOCAL_DB_PASS`       | MySQL password                          |
| `LOCAL_DB_NAME`       | MySQL database                          |
| `LOCAL_DB_PORT`       | MySQL port                              |

> **Security:** Never commit `.env` to Git. It may contain API keys, RPC credentials, database credentials, and Discord Webhook URLs.

---

## 7. Database Setup

Create the MySQL database:

```sql
CREATE DATABASE `apebond-notify`;
```

Example bond configuration table:

```sql
CREATE TABLE IF NOT EXISTS `list_bond_contract_notify` (
    `id` INT(11) NOT NULL AUTO_INCREMENT,
    `chain` VARCHAR(20) NOT NULL,
    `contract_address` VARCHAR(100) NOT NULL,
    `token_symbol` VARCHAR(50) NOT NULL,
    `status` VARCHAR(20) DEFAULT 'active',
    `notify_threshold` FLOAT DEFAULT '10',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `contract_address` (`contract_address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 8. Running the Application

Run the scanner once:

```bash
python index.py
```

To run it automatically every 10 minutes on Windows PowerShell:

```powershell
while ($true) {
    python index.py
    Start-Sleep -Seconds 600
}
```

### System Flow

```text
ApeBond API
     │
     ▼
Synchronize Bond Contracts
     │
     ▼
MySQL
     │
     ▼
Fetch Active Bonds
     │
     ├───────────────┐
     ▼               ▼
   EVM            Solana
     │               │
     ▼               ▼
On-chain Data    Account Data
     │               │
     └───────┬───────┘
             ▼
      Price & Metrics
             │
             ▼
        Rank by Bonus
             │
             ▼
        Save History
             │
             ▼
      Discord Webhook
```

---

## 9. Core Business Logic

### Validation Rules

A bond is processed only when:

1. Its status is `active`.
2. Required on-chain data is successfully retrieved.
3. Parsed data is valid.
4. Required token prices are greater than zero.
5. The calculated bonus satisfies `MIN_BONUS_NOTIFY`.

For example:

```ini
MIN_BONUS_NOTIFY=10.0
```

means only bonds with a qualifying bonus of at least **10%** are considered for notification.

---

## 10. Financial Calculations

### Debt Decay

```text
Debt Decay =
(total_debt × time_since_last_decay) / vesting_term
```

### Current Debt

```text
Current Debt =
total_debt - debt_decay
```

### Bill Price

```text
Bill Price =
(control_variable × debt_ratio × 10^16)
/
(10^principal_decimals × 10^18)
```

The calculated price is constrained by the bond's minimum price.

### True Bond Price

```text
True Bond Price =
(bill_price × 10^6)
/
(10^6 - fee_in_principal)
```

### Discount

```text
Discount =
((payout_price - bond_price) / payout_price) × 100
```

### Net Bonus

```text
Net Bonus =
(
    (1 + (payout_price / bond_price - 1))
    × (1 - (fee_in_payout / 10000) / 100)
    - 1
) × 100
```

---

## 11. EVM vs Solana

| Feature        | EVM                       | Solana             |
| -------------- | ------------------------- | ------------------ |
| Data Source    | Smart Contracts           | Solana Accounts    |
| RPC Method     | `eth_call` / Multicall V3 | `get_account_info` |
| Data Format    | ABI-decoded data          | Raw account bytes  |
| Parsing        | Web3.py / ABI             | Manual parsing     |
| Address        | `0x...`                   | Base58             |
| RPC            | Chain-specific RPCs       | Helius RPC         |
| Token Metadata | Token Contracts           | PDA / Metaplex     |

### EVM Processing

```text
Bond Contract
     ↓
Multicall V3
     ↓
Web3.py
     ↓
Decoded Contract Data
     ↓
Financial Calculation
```

### Solana Processing

```text
Bond Accounts
     ↓
Solana RPC
     ↓
Raw Account Bytes
     ↓
struct / Solders
     ↓
Financial Calculation
```

---

## 12. Token Price Resolution

Token prices are required for calculating bond profitability.

The project uses a unified token-price function:

```text
get_token_price_unified()
```

The system can use multiple external providers:

```text
CoinGecko
    ↓
Fallback
    ↓
DexScreener
```

If a required token price cannot be retrieved or is invalid, the bond is excluded from further processing.

---

## 13. Ranking & Notification

After processing valid bonds:

1. Calculate financial metrics.
2. Validate the results.
3. Rank bonds by profitability.
4. Select the highest-ranking opportunities.
5. Store the results in MySQL.
6. Send qualifying opportunities to Discord.

The main ranking and notification flow is handled by:

```text
index.py
```

---

## 14. Database Persistence

Database operations are centralized in:

```text
execute_data.py
```

The module handles operations such as:

* `SELECT`
* `INSERT`
* `UPDATE`
* `CREATE`

Centralizing database operations helps separate database logic from blockchain and calculation logic.

---

## 15. Discord Notification

Qualified bond opportunities are sent through a Discord Webhook.

The notification logic is handled by:

```text
helpers.py
```

The webhook is configured through:

```ini
DISCORD_WEBHOOK_URL=...
```

Only opportunities satisfying the configured conditions are sent.

---

## 16. Security

The following information must never be committed to the repository:

* API keys
* Helius credentials
* Discord Webhook URLs
* Database passwords
* Private RPC credentials
* Other secrets stored in `.env`

Recommended `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
*.pyc
```

If a secret is accidentally exposed, revoke and regenerate it immediately.

---

## 17. Technical Documentation

Additional project documentation may include:

| Document                 | Purpose                                             |
| ------------------------ | --------------------------------------------------- |
| `bond-business-rules.md` | Business rules, formulas and validation logic       |
| `bond-data-flow.md`      | Data flow and processing sequence                   |
| `bond-dependency-map.md` | Module dependencies and responsibilities            |
| `bond-target-modules.md` | EVM/Solana implementation details and risk analysis |

---

## 18. Project Objective

The main objective of ApeBond Notify is to build an automated monitoring pipeline that can identify and notify users about potentially attractive ApeBond opportunities.

The system combines:

* API synchronization
* Blockchain data
* Token price information
* Financial calculations
* Database persistence
* Profitability ranking
* Automated notifications

The architecture separates **data collection, blockchain processing, calculation, persistence, and notification**, making the system easier to maintain, test, and extend.

---

# 🇻🇳 Tiếng Việt

## 1. Tổng quan dự án

**ApeBond Notify** là hệ thống tự động được xây dựng để giám sát, phân tích, xếp hạng và thông báo các cơ hội Bond từ giao thức **ApeBond**.

Hệ thống hỗ trợ cả **blockchain tương thích EVM** và **Solana**.

### Các chức năng chính

* Đồng bộ danh sách Bond đang hoạt động từ ApeBond.
* Giám sát dữ liệu Bond trên nhiều blockchain.
* Đọc dữ liệu Bond trực tiếp từ blockchain.
* Tính toán các chỉ số tài chính của Bond.
* Lấy giá token từ các nguồn dữ liệu bên ngoài.
* Xếp hạng Bond dựa trên khả năng sinh lợi.
* Lưu lịch sử Bond vào MySQL.
* Gửi các cơ hội đạt điều kiện thông qua Discord Webhook.
* Tự động chạy theo khoảng thời gian được cấu hình.

---

## 2. Các blockchain được hỗ trợ

### EVM

Hệ thống hỗ trợ các blockchain tương thích EVM như:

* Ethereum
* BNB Chain
* Polygon
* Arbitrum
* Base
* Linea
* Sonic
* Berachain

### Solana

Bond trên Solana được xử lý thông qua Solana RPC và dữ liệu account trực tiếp trên blockchain.

---

## 3. Công nghệ sử dụng

| Thành phần         | Công nghệ                  |
| ------------------ | -------------------------- |
| Ngôn ngữ           | Python 3.8+                |
| Cơ sở dữ liệu      | MySQL                      |
| Tương tác EVM      | Web3.py, Multicall V3      |
| Tương tác Solana   | Solana Python SDK, Solders |
| Quản lý môi trường | python-dotenv              |
| Xử lý đồng thời    | ThreadPoolExecutor         |
| Thông báo          | Discord Webhook            |
| Nguồn giá Token    | CoinGecko / DexScreener    |

---

## 4. Cấu trúc dự án

```text
apebond-notify/
│
├── index.py
├── config.py
├── helpers.py
├── execute_data.py
├── process_bond_evm.py
├── process_bond_sol.py
│
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

### Trách nhiệm của các module

| Module                | Chức năng                                           |
| --------------------- | --------------------------------------------------- |
| `index.py`            | Luồng xử lý chính, đồng bộ, xếp hạng và thông báo   |
| `process_bond_evm.py` | Lấy và xử lý dữ liệu Bond trên EVM                  |
| `process_bond_sol.py` | Lấy và xử lý dữ liệu Bond trên Solana               |
| `execute_data.py`     | Thực hiện các thao tác với MySQL                    |
| `helpers.py`          | Các hàm dùng chung, lấy giá token và gửi Discord    |
| `config.py`           | Quản lý biến môi trường, RPC và cấu hình blockchain |

---

## 5. Cài đặt

### Bước 1 — Clone repository

```bash
git clone <your-repository-url>
cd apebond-notify
```

### Bước 2 — Tạo Virtual Environment

#### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

#### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
```

### Bước 3 — Cài đặt thư viện

```bash
pip install -r requirements.txt
```

Nếu chưa có `requirements.txt`:

```bash
pip install python-dotenv requests web3 solana==0.36.0 solders mysql-connector-python
```

---

## 6. Cấu hình

Tạo file `.env` tại thư mục gốc của dự án:

```ini
ENV=local

DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

HELIUS_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_API_KEY

MIN_BONUS_NOTIFY=10.0

LOCAL_DB_HOST=localhost
LOCAL_DB_USER=root
LOCAL_DB_PASS=
LOCAL_DB_NAME=apebond-notify
LOCAL_DB_PORT=3306
```

### Ý nghĩa các biến

| Biến                  | Mô tả                            |
| --------------------- | -------------------------------- |
| `ENV`                 | Môi trường chạy ứng dụng         |
| `DISCORD_WEBHOOK_URL` | Địa chỉ Discord Webhook          |
| `HELIUS_RPC_URL`      | RPC dùng để kết nối Solana       |
| `MIN_BONUS_NOTIFY`    | Bonus tối thiểu để gửi thông báo |
| `LOCAL_DB_HOST`       | Địa chỉ MySQL                    |
| `LOCAL_DB_USER`       | Tài khoản MySQL                  |
| `LOCAL_DB_PASS`       | Mật khẩu MySQL                   |
| `LOCAL_DB_NAME`       | Tên database                     |
| `LOCAL_DB_PORT`       | Port MySQL                       |

> **Bảo mật:** Không được commit file `.env` lên Git vì file này có thể chứa API key, RPC credentials, thông tin database và Discord Webhook.

---

## 7. Cấu hình Database

Tạo database MySQL:

```sql
CREATE DATABASE `apebond-notify`;
```

Ví dụ bảng lưu thông tin Bond:

```sql
CREATE TABLE IF NOT EXISTS `list_bond_contract_notify` (
    `id` INT(11) NOT NULL AUTO_INCREMENT,
    `chain` VARCHAR(20) NOT NULL,
    `contract_address` VARCHAR(100) NOT NULL,
    `token_symbol` VARCHAR(50) NOT NULL,
    `status` VARCHAR(20) DEFAULT 'active',
    `notify_threshold` FLOAT DEFAULT '10',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `contract_address` (`contract_address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 8. Chạy chương trình

Chạy scanner một lần:

```bash
python index.py
```

Để tự động chạy lại sau mỗi 10 phút trên Windows PowerShell:

```powershell
while ($true) {
    python index.py
    Start-Sleep -Seconds 600
}
```

### Luồng xử lý hệ thống

```text
ApeBond API
     │
     ▼
Đồng bộ Bond Contract
     │
     ▼
MySQL
     │
     ▼
Lấy Bond đang hoạt động
     │
     ├───────────────┐
     ▼               ▼
    EVM           Solana
     │               │
     ▼               ▼
Dữ liệu On-chain  Account Data
     │               │
     └───────┬───────┘
             ▼
      Tính giá & chỉ số
             │
             ▼
       Xếp hạng Bonus
             │
             ▼
        Lưu lịch sử
             │
             ▼
      Discord Webhook
```

---

## 9. Logic nghiệp vụ chính

### Điều kiện xử lý Bond

Một Bond chỉ được xử lý khi:

1. Có trạng thái `active`.
2. Lấy được dữ liệu cần thiết từ blockchain.
3. Dữ liệu sau khi parse hợp lệ.
4. Giá các token cần thiết lớn hơn `0`.
5. Bonus đạt ngưỡng `MIN_BONUS_NOTIFY`.

Ví dụ:

```ini
MIN_BONUS_NOTIFY=10.0
```

có nghĩa là hệ thống chỉ xem xét gửi thông báo đối với các Bond có Bonus đạt tối thiểu **10%**.

---

## 10. Các công thức tài chính

### Debt Decay

```text
Debt Decay =
(total_debt × time_since_last_decay) / vesting_term
```

Dùng để xác định phần Debt đã giảm theo thời gian.

### Current Debt

```text
Current Debt =
total_debt - debt_decay
```

Xác định Debt hiện tại của Bond sau khi tính phần Debt đã giảm.

### Bill Price

```text
Bill Price =
(control_variable × debt_ratio × 10^16)
/
(10^principal_decimals × 10^18)
```

Giá trị sau khi tính được giới hạn bởi mức giá tối thiểu của Bond.

### True Bond Price

```text
True Bond Price =
(bill_price × 10^6)
/
(10^6 - fee_in_principal)
```

Dùng để xác định giá Bond thực tế sau khi tính phí.

### Discount

```text
Discount =
((payout_price - bond_price) / payout_price) × 100
```

Xác định mức chiết khấu của Bond so với giá trị payout.

### Net Bonus

```text
Net Bonus =
(
    (1 + (payout_price / bond_price - 1))
    × (1 - (fee_in_payout / 10000) / 100)
    - 1
) × 100
```

Net Bonus là một trong những chỉ số chính được sử dụng để đánh giá và xếp hạng Bond.

---

## 11. So sánh EVM và Solana

| Đặc điểm          | EVM                       | Solana             |
| ----------------- | ------------------------- | ------------------ |
| Nguồn dữ liệu     | Smart Contract            | Solana Account     |
| Phương thức RPC   | `eth_call` / Multicall V3 | `get_account_info` |
| Định dạng dữ liệu | ABI-decoded               | Raw account bytes  |
| Parse dữ liệu     | Web3.py / ABI             | Parse thủ công     |
| Địa chỉ           | `0x...`                   | Base58             |
| RPC               | RPC riêng theo Chain      | Helius RPC         |
| Token Metadata    | Token Contract            | PDA / Metaplex     |

### Luồng EVM

```text
Bond Contract
     ↓
Multicall V3
     ↓
Web3.py
     ↓
Dữ liệu Contract đã Decode
     ↓
Tính toán tài chính
```

### Luồng Solana

```text
Bond Account
     ↓
Solana RPC
     ↓
Raw Account Bytes
     ↓
struct / Solders
     ↓
Tính toán tài chính
```

---

## 12. Lấy giá Token

Giá Token là dữ liệu cần thiết để tính toán hiệu quả của Bond.

Hệ thống sử dụng hàm thống nhất:

```text
get_token_price_unified()
```

Các nguồn giá có thể được sử dụng theo cơ chế fallback:

```text
CoinGecko
    ↓
Fallback
    ↓
DexScreener
```

Nếu không thể lấy được giá Token cần thiết hoặc giá không hợp lệ, Bond sẽ bị loại khỏi quá trình xử lý.

---

## 13. Xếp hạng và thông báo

Sau khi xử lý các Bond hợp lệ, hệ thống sẽ:

1. Tính toán các chỉ số tài chính.
2. Kiểm tra tính hợp lệ của dữ liệu.
3. Xếp hạng Bond theo khả năng sinh lợi.
4. Chọn các cơ hội có thứ hạng cao.
5. Lưu kết quả vào MySQL.
6. Gửi các Bond đạt điều kiện lên Discord.

Luồng xếp hạng và thông báo chính nằm trong:

```text
index.py
```

---

## 14. Lưu trữ Database

Các thao tác với MySQL được tập trung trong:

```text
execute_data.py
```

Module này xử lý các thao tác như:

* `SELECT`
* `INSERT`
* `UPDATE`
* `CREATE`

Việc tách riêng database logic giúp giảm sự phụ thuộc giữa xử lý blockchain, tính toán và lưu trữ dữ liệu.

---

## 15. Discord Notification

Các cơ hội Bond đạt điều kiện sẽ được gửi thông qua Discord Webhook.

Logic gửi thông báo nằm trong:

```text
helpers.py
```

Webhook được cấu hình bằng:

```ini
DISCORD_WEBHOOK_URL=...
```

Chỉ những Bond thỏa mãn các điều kiện đã cấu hình mới được gửi thông báo.

---

## 16. Bảo mật

Không được commit các thông tin sau lên repository:

* API Key
* Helius credentials
* Discord Webhook URL
* Database password
* Private RPC credentials
* Các thông tin bảo mật khác trong `.env`

`.gitignore` nên chứa:

```gitignore
.env
.venv/
__pycache__/
*.pyc
```

Nếu thông tin bảo mật bị lộ, cần **thu hồi và tạo lại credential mới ngay lập tức**.

---

## 17. Tài liệu kỹ thuật

Các tài liệu phân tích bổ sung của dự án:

| File                     | Nội dung                                      |
| ------------------------ | --------------------------------------------- |
| `bond-business-rules.md` | Business rules, công thức và điều kiện xử lý  |
| `bond-data-flow.md`      | Luồng dữ liệu và trình tự xử lý               |
| `bond-dependency-map.md` | Dependency và trách nhiệm của từng module     |
| `bond-target-modules.md` | Chi tiết xử lý EVM/Solana và phân tích rủi ro |

---

## 18. Mục tiêu dự án

Mục tiêu chính của **ApeBond Notify** là xây dựng một pipeline tự động có khả năng giám sát và phát hiện các cơ hội Bond tiềm năng trên ApeBond.

Hệ thống kết hợp:

* Đồng bộ dữ liệu từ API.
* Dữ liệu trực tiếp từ blockchain.
* Dữ liệu giá Token.
* Tính toán các chỉ số tài chính.
* Lưu trữ dữ liệu bằng MySQL.
* Xếp hạng cơ hội theo khả năng sinh lợi.
* Gửi thông báo tự động.

Kiến trúc hệ thống phân tách rõ các nhóm chức năng:

**Data Collection → Blockchain Processing → Calculation → Persistence → Notification**

Điều này giúp hệ thống dễ bảo trì, kiểm thử và mở rộng trong tương lai.

---

# 📌 Summary / Tóm tắt

```text
Fetch
  ↓
Validate
  ↓
Read On-chain Data
  ↓
Calculate
  ↓
Rank
  ↓
Store
  ↓
Notify
```

**ApeBond Notify — Automated Bond Monitoring & Analysis System**

**ApeBond Notify — Hệ thống tự động giám sát và phân tích Bond**
