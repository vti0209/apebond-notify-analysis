# bond-business-rules.md

## 1. Nguồn dữ liệu Bond
- **Dữ liệu gốc:** Lấy từ API chính thức của ApeBond (`APEBOND_API_URL` trong config).
- **Cập nhật:** Được gọi qua hàm `fetch_and_update_bonds()` để đồng bộ vào bảng `list_bond_contract_notify`.
- **Danh sách chạy:** Không chạy tất cả, mà chỉ chạy các Bond có `status = 'active'` trong Database.

## 2. Điều kiện Bond hợp lệ (Để đưa vào Top ranking)
- Bond phải có `status = 'active'` (lấy từ trường `status` trong DB).
- Dữ liệu Contract/Account phải đọc thành công (không bị lỗi `Data too short`).
- Giá Token Payout và Principal phải khác 0 (để tránh lỗi chia cho 0).
- **Điều kiện lọc cuối cùng:** Chỉ những Bond có `min_bonus` vượt quá ngưỡng `MIN_BONUS_NOTIFY` (mặc định 10.0, config trong `.env`) mới được gửi lên Discord.

## 3. Công thức tính toán
| Tên biến | Công thức / Logic | Đơn vị |
| :--- | :--- | :--- |
| **Debt Decay** | `(total_debt * (current_timestamp - last_decay_timestamp)) / vesting_term` | Raw units |
| **Current Debt** | `total_debt - debt_decay` | Raw units |
| **Debt Ratio** | `(current_debt * 10**payout_decimals * 10**18) / payout_token_initial_supply` | Wei (10^18) |
| **Bill Price** | `(control_variable * debt_ratio * 10**16) / (10**principal_decimals * 10**18)` (Giá trị tối thiểu là `minimum_price`) | Raw units |
| **True Bond Price** | `(bill_price * 10**6) / (10**6 - fee_in_principal)` | Raw units (Scale 1e6) |
| **Bonus** | `((payout_token_price / (principal_token_price * true_bond_price / 10**18)) - 1) * 100` | % (Phần trăm) |
| **Bonus có Fee** | `((1 + bonus/100) * (1 - (fee_in_payout/10000)/100) - 1) * 100` | % (Phần trăm) |

## 4. Xếp hạng (Ranking)
- Số lượng lấy: **Top 10**.
- Tiêu chí sắp xếp: Dựa trên **`max_bonus` giảm dần** (hàm `sorted(..., reverse=True)`).

## 5. Quy tắc Discord Notification
- Nội dung gửi: Danh sách Top 10 Bond đã lọc theo ngưỡng.
- Webhook URL được lấy từ biến môi trường `DISCORD_WEBHOOK_URL`.