from web3 import Web3
from eth_abi import decode

API_KEY_INFURA = "afb06acf1c3542aca75c89203c9f9a28"
rpc_url = f"https://arbitrum-mainnet.infura.io/v3/{API_KEY_INFURA}"
bond_contract_address = "0x80da818929b3c22577408cbe7a662b08a21f073f"
multicall_v3_address = "0xcA11bde05977b3631167028862bE2a173976CA11"

w3 = Web3(Web3.HTTPProvider(rpc_url))
bond_contract = Web3.to_checksum_address(bond_contract_address)
multicall_contract = Web3.to_checksum_address(multicall_v3_address)

# def decode_address(data_bytes):
#     return Web3.to_checksum_address("0x" + data_bytes.hex()[-40:])

# def decode_uint256(data_bytes):
#     return int.from_bytes(data_bytes, byteorder="big")

# def decode_bool(data_bytes):
#     return bool(int.from_bytes(data_bytes[-1:], byteorder="big"))

# def decode_terms(data_bytes):
#     values = [int.from_bytes(data_bytes[i:i+32], byteorder="big") for i in range(0, 32*7, 32)]
#     keys = [
#         "controlVariable", "vestingTerm", "minimumPrice", "maxPayout",
#         "maxDebt", "maxTotalPayout", "initialDebt"
#     ]
#     return dict(zip(keys, values))

# def decode_true_bond_prices(data_bytes):
#     prices = []
#     offset = int.from_bytes(data_bytes[0:32], "big")  # offset to start of array
#     length = int.from_bytes(data_bytes[offset:offset+32], "big")  # number of tuples
#     cursor = offset + 32

#     for _ in range(length):
#         price = int.from_bytes(data_bytes[cursor:cursor+32], "big")
#         min_amt = int.from_bytes(data_bytes[cursor+32:cursor+64], "big")
#         max_amt = int.from_bytes(data_bytes[cursor+64:cursor+96], "big")
#         prices.append([price, min_amt, max_amt])
#         cursor += 96

#     return prices
def decode_address(data):
    """
    Decode address from dict, bytes, string, or tuple/list.
    Returns checksummed 0x address string or None.
    """
    try:
        if data is None:
            return None
        if isinstance(data, dict):
            for key in ['address', 'target', 'payoutToken', 'principalToken', 'token']:
                if key in data and data[key]:
                    return decode_address(data[key])
            if data:
                return decode_address(list(data.values())[0])
            return None
        if isinstance(data, (tuple, list)):
            if data:
                return decode_address(data[0])
            return None
        if isinstance(data, (bytes, bytearray)):
            if len(data) == 0:
                return None
            hex_str = data.hex()
            if len(hex_str) >= 40:
                return Web3.to_checksum_address("0x" + hex_str[-40:])
            return None
        if isinstance(data, str):
            s = data.strip()
            if s.startswith("0x") or s.startswith("0X"):
                s = s[2:]
            if len(s) >= 40:
                return Web3.to_checksum_address("0x" + s[-40:])
            return None
        return Web3.to_checksum_address(str(data))
    except Exception:
        return None

def decode_uint256(data):
    """
    Decode uint256 from dict, bytes, string, int, float, or tuple/list.
    Returns integer value or 0.
    """
    try:
        if data is None:
            return 0
        if isinstance(data, int):
            return data
        if isinstance(data, float):
            return int(data)
        if isinstance(data, dict):
            if data:
                return decode_uint256(list(data.values())[0])
            return 0
        if isinstance(data, (tuple, list)):
            if data:
                return decode_uint256(data[0])
            return 0
        if isinstance(data, (bytes, bytearray)):
            if len(data) == 0:
                return 0
            return int.from_bytes(data, byteorder="big")
        if isinstance(data, str):
            s = data.strip()
            if not s:
                return 0
            if s.startswith("0x") or s.startswith("0X"):
                return int(s, 16)
            return int(s)
        return int(data)
    except Exception:
        return 0

def decode_terms(data):
    """
    Decode terms struct from dict, bytes, string, or tuple/list.
    Returns dictionary with all 7 terms keys.
    """
    keys = [
        "controlVariable", "vestingTerm", "minimumPrice", "maxPayout",
        "maxDebt", "maxTotalPayout", "initialDebt"
    ]
    default_terms = {k: 0 for k in keys}

    try:
        if data is None:
            return default_terms

        # 1. Handle Dict
        if isinstance(data, dict):
            lower_dict = {str(k).lower(): v for k, v in data.items()}
            result = {}
            for k in keys:
                lk = k.lower()
                alt_lk = lk.replace("variable", "_variable").replace("term", "_term").replace("price", "_price").replace("payout", "_payout").replace("debt", "_debt")
                if lk in lower_dict:
                    result[k] = decode_uint256(lower_dict[lk])
                elif alt_lk in lower_dict:
                    result[k] = decode_uint256(lower_dict[alt_lk])
                else:
                    result[k] = 0
            if all(result[k] == 0 for k in keys) and len(data) >= 7:
                vals = list(data.values())
                for idx, k in enumerate(keys):
                    result[k] = decode_uint256(vals[idx])
            return result

        # 2. Handle String (Hex)
        if isinstance(data, str):
            s = data.strip()
            if s.startswith("0x") or s.startswith("0X"):
                s = s[2:]
            try:
                data = bytes.fromhex(s)
            except ValueError:
                return default_terms

        # 3. Handle Bytes / Bytearray
        if isinstance(data, (bytes, bytearray)):
            if len(data) < 32:
                return default_terms
            values = []
            for i in range(0, min(len(data), 32 * 7), 32):
                chunk = data[i:i+32]
                if len(chunk) < 32:
                    chunk = chunk.rjust(32, b'\x00')
                values.append(int.from_bytes(chunk, byteorder="big"))
            while len(values) < 7:
                values.append(0)
            return dict(zip(keys, values[:7]))

        # 4. Handle Tuple / List
        if isinstance(data, (tuple, list)):
            values = [decode_uint256(x) for x in data[:7]]
            while len(values) < 7:
                values.append(0)
            return dict(zip(keys, values))

        return default_terms
    except Exception:
        return default_terms

def decode_true_bond_prices(data):
    """
    Decode true bond price tiers from dict, bytes, string, or tuple/list.
    Returns list of tier price tuples [[price, minAmount, maxAmount], ...] or None.
    """
    try:
        if data is None:
            return None

        # 1. Handle Dict
        if isinstance(data, dict):
            if 'prices' in data and isinstance(data['prices'], (list, tuple)):
                return decode_true_bond_prices(data['prices'])
            if 'trueBondPrices' in data:
                return decode_true_bond_prices(data['trueBondPrices'])
            vals = list(data.values())
            if vals:
                return decode_true_bond_prices(vals)
            return None

        # 2. Handle List / Tuple
        if isinstance(data, (list, tuple)):
            res = []
            for item in data:
                if isinstance(item, (list, tuple)):
                    p = decode_uint256(item[0]) if len(item) > 0 else 0
                    mi = decode_uint256(item[1]) if len(item) > 1 else 0
                    ma = decode_uint256(item[2]) if len(item) > 2 else 0
                    res.append([p, mi, ma])
                elif isinstance(item, dict):
                    p = decode_uint256(item.get('price', item.get('trueBondPrice', 0)))
                    mi = decode_uint256(item.get('minAmount', item.get('min_amt', 0)))
                    ma = decode_uint256(item.get('maxAmount', item.get('max_amt', 0)))
                    res.append([p, mi, ma])
                else:
                    res.append([decode_uint256(item), 0, 0])
            return res if res else None

        # 3. Handle String (Hex)
        if isinstance(data, str):
            s = data.strip()
            if s.startswith("0x") or s.startswith("0X"):
                s = s[2:]
            try:
                data = bytes.fromhex(s)
            except ValueError:
                return None

        # 4. Handle Bytes / Bytearray
        if isinstance(data, (bytes, bytearray)):
            if len(data) < 32:
                return None

            # Standard ABI array decoding (Offset + Length + Elements)
            try:
                offset = int.from_bytes(data[0:32], "big")
                if offset + 32 <= len(data):
                    length = int.from_bytes(data[offset:offset+32], "big")
                    cursor = offset + 32
                    prices = []
                    for _ in range(length):
                        if cursor + 96 <= len(data):
                            p = int.from_bytes(data[cursor:cursor+32], "big")
                            mi = int.from_bytes(data[cursor+32:cursor+64], "big")
                            ma = int.from_bytes(data[cursor+64:cursor+96], "big")
                            prices.append([p, mi, ma])
                            cursor += 96
                    if prices:
                        return prices
            except Exception:
                pass

            # Direct chunks decoding (if no offset prefix)
            prices = []
            cursor = 0
            while cursor + 96 <= len(data):
                p = int.from_bytes(data[cursor:cursor+32], "big")
                mi = int.from_bytes(data[cursor+32:cursor+64], "big")
                ma = int.from_bytes(data[cursor+64:cursor+96], "big")
                prices.append([p, mi, ma])
                cursor += 96
            
            if not prices and len(data) >= 32:
                prices.append([int.from_bytes(data[:32], "big"), 0, 0])

            return prices if prices else None

        return None
    except Exception:
        return None
def decode_string(data_bytes):
    length = int.from_bytes(data_bytes[0:32], "big")
    return data_bytes[32:32+length].decode("utf-8")

def decode_get_reserves(data_bytes):
    values = [int.from_bytes(data_bytes[i:i+32], byteorder="big") for i in range(0, 32*3, 32)]
    keys = ["reserve0", "reserve1", "blockTimestampLast"]
    return dict(zip(keys, values))

def decode_get_total_amounts(data_bytes):
    values = [int.from_bytes(data_bytes[i:i+32], byteorder="big") for i in range(0, 32*2, 32)]
    keys = ["total0", "total1"]
    return dict(zip(keys, values))

# === ABI Multicall V3 (tryAggregate) ===
MULTICALL_V3_ABI = [
    {
        "inputs": [
            {"internalType": "bool", "name": "requireSuccess", "type": "bool"},
            {
                "components": [
                    {"internalType": "address", "name": "target", "type": "address"},
                    {"internalType": "bytes", "name": "callData", "type": "bytes"}
                ],
                "internalType": "struct Multicall3.Call[]",
                "name": "calls",
                "type": "tuple[]"
            }
        ],
        "name": "tryAggregate",
        "outputs": [
            {
                "components": [
                    {"internalType": "bool", "name": "success", "type": "bool"},
                    {"internalType": "bytes", "name": "returnData", "type": "bytes"}
                ],
                "internalType": "struct Multicall3.Result[]",
                "name": "returnData",
                "type": "tuple[]"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

# Tạo callData cho các hàm
payout_sig = w3.keccak(text="payoutToken()")[:4]
principal_sig = w3.keccak(text="principalToken()")[:4]
true_bill_price_sig = w3.keccak(text="trueBillPrice()")[:4]
terms_sig = w3.keccak(text="terms()")[:4]
fee_in_payout_sig = w3.keccak(text="feeInPayout()")[:4]
true_bond_price_tier_sig = w3.keccak(text="trueBondPrices()")[:4]

calls = [
    {"target": bond_contract, "callData": payout_sig},
    {"target": bond_contract, "callData": principal_sig},
    {"target": bond_contract, "callData": true_bill_price_sig},
    {"target": bond_contract, "callData": terms_sig},
    {"target": bond_contract, "callData": fee_in_payout_sig},
    {"target": bond_contract, "callData": true_bond_price_tier_sig},
]

# Gọi multicall v3
contract = w3.eth.contract(address=multicall_contract, abi=MULTICALL_V3_ABI)
results = contract.functions.tryAggregate(False, calls).call()

# Decode kết quả (giải mã địa chỉ ERC20 từ 32 byte returnData)
payout_token = decode_address(results[0][1])
principal_token = decode_address(results[1][1])
true_bill_price = decode_uint256(results[2][1])
terms = decode_terms(results[3][1])
fee_in_payout = decode_uint256(results[4][1])
try:
    true_bond_price_tier = decode_true_bond_prices(results[5][1])
except:
    true_bond_price_tier = None  # fallback nếu fail

# In kết quả
# print(f"🏦 Payout Token: {payout_token}")
# print(f"💰 Principal Token: {principal_token}")
# print(f"💰 True Bill Price: {true_bill_price}")
# print(f"💰 Terms: {terms}")
# print(f"💰 Fee in Payout: {fee_in_payout}")
# print(f"💰 True Bond Price Tier: {true_bond_price_tier}")