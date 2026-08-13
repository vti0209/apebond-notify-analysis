# ApeBond Notify

Tool tự động lấy danh sách bond từ ApeBond, tính bonus trên EVM/Solana, lưu kết quả vào MySQL và gửi các bond đạt ngưỡng qua Discord Webhook.

## Tính năng chính

- Tự đồng bộ bond đang hoạt động từ ApeBond API.
- Hỗ trợ EVM: `BNB`, `ETH`, `POL`, `ARB`, `BAS`, `UNI`, `BER`, `SON`, `LIN`, `HYPER`.
- Hỗ trợ Solana: `SOL`.
- Xử lý nhiều bond song song, tối đa 10 luồng.
- Lấy giá lần lượt từ ApeBond Price API, CoinGecko và DexScreener.
- Cache giá và ABI để giảm số lần gọi API.
- Lưu lịch sử vào MySQL và gửi top bond qua Discord.
- Ghi log hằng ngày, giữ ba bản log gần nhất.

## 1. Yêu cầu

- Python 3.10 trở lên; khuyến nghị Python 3.11 hoặc 3.12.
- MySQL 8.x.
- Infura API key và explorer API key cho các chain EVM.
- Solana RPC URL, ví dụ Helius.
- Discord Webhook URL.

## 2. Cài đặt

```bash
git clone <URL_REPOSITORY>
cd apebond-notify
python -m venv .venv
```

Kích hoạt môi trường ảo:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# Linux/macOS
source .venv/bin/activate
```

Cài dependency:

```bash
python -m pip install --upgrade pip
python -m pip install requests python-dotenv discord.py mysql-connector-python web3 eth-abi solana solders
```

## 3. Lưu ý về code hiện tại

Trước khi chạy, cần kiểm tra hai điểm sau.

### Nhánh cấu hình database đang bị đảo

Trong `execute_data.py`, code hiện tại có dạng:

```python
if env == "local":
    # lại đọc SERVER_DB_*
else:
    # lại đọc LOCAL_DB_*
```

Nên sửa điều kiện thành:

```python
if env == "server":
```

Sau khi sửa, `ENV=local` sẽ đọc `LOCAL_DB_*`, còn `ENV=server` sẽ đọc `SERVER_DB_*` như mong đợi.

### Bảng bond đang thiếu `updated_at`

Hàm đồng bộ cập nhật cột `updated_at`, nhưng câu lệnh tạo bảng hiện chưa có cột này. Phần khởi tạo database bên dưới có lệnh bổ sung cột.

## 4. Cấu hình MySQL

Tạo file `.env` cạnh `index.py`.

Chạy local:

```dotenv
ENV=local
LOCAL_DB_HOST=127.0.0.1
LOCAL_DB_USER=apebond
LOCAL_DB_PASS=YOUR_MYSQL_PASSWORD
LOCAL_DB_NAME=apebond_notify
LOCAL_DB_PORT=3306
```

Chạy server:

```dotenv
ENV=server
SERVER_DB_HOST=127.0.0.1
SERVER_DB_USER=apebond
SERVER_DB_PASS=YOUR_MYSQL_PASSWORD
SERVER_DB_NAME=apebond_notify
SERVER_DB_PORT=3306
```

`process_bond_evm.py` vẫn đọc `DB_CONFIG` từ `config.py`, vì vậy cấu hình này phải trỏ tới cùng database:

```python
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "apebond",
    "password": "YOUR_MYSQL_PASSWORD",
    "database": "apebond_notify",
}
```

## 5. Cấu hình API trong `config.py`

Không thay đổi các mapping chain có sẵn nếu chưa hiểu rõ. Người dùng mới chủ yếu cần thay các giá trị sau:

```python
API_KEY_INFURA = "YOUR_INFURA_API_KEY"

API_KEYS = {
    "ETH": "YOUR_EXPLORER_KEY",
    "BAS": "YOUR_EXPLORER_KEY",
    "POL": "YOUR_EXPLORER_KEY",
    "BNB": "YOUR_EXPLORER_KEY",
    "ARB": "YOUR_EXPLORER_KEY",
    "LIN": "YOUR_EXPLORER_KEY",
    "SON": "YOUR_EXPLORER_KEY",
    "UNI": "YOUR_EXPLORER_KEY",
    "BER": "YOUR_BERASCAN_KEY",
    "HYPER": "YOUR_EXPLORER_KEY",
}

DISCORD_WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL"
CHANNEL_ID = 0
HELIUS_RPC_URL = "YOUR_SOLANA_RPC_URL"
MIN_BONUS_NOTIFY = 10.0
```

- `API_KEYS` dùng để lấy ABI từ explorer.
- `DISCORD_WEBHOOK_URL` dùng để gửi thông báo.
- `HELIUS_RPC_URL` bắt buộc phải tồn tại vì Solana client được tạo ngay khi khởi động.
- `MIN_BONUS_NOTIFY` là ngưỡng dự phòng; ngưỡng riêng trong MySQL được ưu tiên.

## 6. Lấy Infura RPC

1. Đăng ký tại [Infura Dashboard](https://app.infura.io/) và xác nhận email.
2. Chọn `My First Key` hoặc tạo key riêng cho tool.
3. Chọn `Configure` → `All Endpoints`.
4. Sao chép **API key**, không phải API key secret.
5. Bật các mạng: Ethereum, BNB Smart Chain, Polygon, Arbitrum, Base và Linea.
6. Gán key vào `API_KEY_INFURA` trong `config.py`.

RPC mặc định:

```python
RPC_URLS = {
    "ETH": f"https://mainnet.infura.io/v3/{API_KEY_INFURA}",
    "BNB": f"https://bsc-mainnet.infura.io/v3/{API_KEY_INFURA}",
    "POL": f"https://polygon-mainnet.infura.io/v3/{API_KEY_INFURA}",
    "ARB": f"https://arbitrum-mainnet.infura.io/v3/{API_KEY_INFURA}",
    "BAS": f"https://base-mainnet.infura.io/v3/{API_KEY_INFURA}",
    "LIN": f"https://linea-mainnet.infura.io/v3/{API_KEY_INFURA}",
    "SON": "https://rpc.soniclabs.com",
    "BER": "https://rpc.berachain.com",
    "UNI": "https://mainnet.unichain.org",
    "HYPER": "https://rpc.hyperliquid.xyz/evm",
}
```

Kiểm tra kết nối mà không in API key:

```bash
python -c "from web3 import Web3; from config import RPC_URLS; print({c: Web3(Web3.HTTPProvider(u)).is_connected() for c, u in RPC_URLS.items()})"
```

Kết quả mong đợi là `True`. Xem thêm [danh sách endpoint Infura](https://docs.infura.io/get-started/endpoints/).

## 7. Khởi tạo database

Chạy MySQL, sau đó tạo database và bảng:

```bash
python -c "from execute_data import create_database_and_table; create_database_and_table()"
```

Kiểm tra cột `updated_at`:

```sql
SHOW COLUMNS FROM list_bond_contract_notify LIKE 'updated_at';
```

Nếu chưa có, chạy:

```sql
ALTER TABLE list_bond_contract_notify
ADD COLUMN updated_at DATETIME NULL;
```

Tool sẽ tự đồng bộ bond vào bảng này. Không cần thêm bond thủ công.

Muốn đổi ngưỡng thông báo cho một bond:

```sql
UPDATE list_bond_contract_notify
SET notify_threshold = 15.00
WHERE contract_address = '0xYOUR_BOND_CONTRACT';
```

## 8. Chạy tool

Kiểm tra cấu hình:

```bash
python -c "import config; print('config.py: OK')"
python -c "from execute_data import get_connection; c=get_connection(); print('MySQL:', c.is_connected()); c.close()"
```

Chạy một lượt:

```bash
python index.py
```

Mỗi lần chạy, tool sẽ tự đồng bộ bond, xử lý dữ liệu, ghi MySQL, gửi Discord rồi kết thúc. Muốn chạy liên tục, hãy dùng Task Scheduler hoặc cron.

Tool tạm nghỉ từ `23:30` đến `06:30` theo giờ Việt Nam (`UTC+7`). Trong khoảng này lệnh vẫn kết thúc ngay, không tự chờ tới sáng.

Log nằm tại `../logs/bond_notify.log` tính từ thư mục repository.

Ví dụ cron chạy mỗi 5 phút:

```cron
*/5 * * * * cd /duong-dan/apebond-notify && .venv/bin/python index.py >> cron.log 2>&1
```

## 9. Lỗi thường gặp

| Lỗi | Cách kiểm tra |
| --- | --- |
| Không kết nối được MySQL | Kiểm tra `ENV`, nhóm biến DB trong `.env` và `DB_CONFIG`. |
| `Unknown column 'updated_at'` | Chạy lệnh `ALTER TABLE` ở bước 7. |
| RPC trả `False`, `401` hoặc `403` | Kiểm tra Infura key và network đã bật. |
| Không lấy được ABI | Kiểm tra chain có trong cả `API_URLS` và `API_KEYS`. |
| Không gửi Discord | Kiểm tra webhook và `min_bonus >= notify_threshold`. |
| Bond có trong API nhưng không xử lý | Kiểm tra `ID_CHAIN_MAP` và cấu hình của chain tương ứng. |

Lưu ý mapping hiện tại chưa đồng nhất hoàn toàn: `UNI=130` chưa có trong `ID_CHAIN_MAP`, `10143` đang được bỏ qua và `MON` chưa có đủ cấu hình. Cần sửa mapping nếu sử dụng các chain này.

## 10. Bảo mật

- Không commit `config.py`, `.env`, API key, webhook hoặc mật khẩu.
- Thêm `config.py`, `.env`, `abi_cache/` và `logs/` vào `.gitignore`.
- `call_multicall.py` phải dùng `RPC_URLS["ARB"]`, không hard-code Infura key riêng.
- Nếu key từng được commit hoặc chia sẻ, hãy revoke/rotate key.
- Trước khi push, luôn kiểm tra `git status`.
