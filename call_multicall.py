from web3 import Web3
from eth_abi import decode

API_KEY_INFURA = "afb06acf1c3542aca75c89203c9f9a28"
rpc_url = f"https://arbitrum-mainnet.infura.io/v3/{API_KEY_INFURA}"
bond_contract_address = "0x80da818929b3c22577408cbe7a662b08a21f073f"
multicall_v3_address = "0xcA11bde05977b3631167028862bE2a173976CA11"

w3 = Web3(Web3.HTTPProvider(rpc_url))
bond_contract = Web3.to_checksum_address(bond_contract_address)
multicall_contract = Web3.to_checksum_address(multicall_v3_address)

def decode_address(data_bytes):
    return Web3.to_checksum_address("0x" + data_bytes.hex()[-40:])

def decode_uint256(data_bytes):
    return int.from_bytes(data_bytes, byteorder="big")

def decode_bool(data_bytes):
    return bool(int.from_bytes(data_bytes[-1:], byteorder="big"))

def decode_terms(data_bytes):
    values = [int.from_bytes(data_bytes[i:i+32], byteorder="big") for i in range(0, 32*7, 32)]
    keys = [
        "controlVariable", "vestingTerm", "minimumPrice", "maxPayout",
        "maxDebt", "maxTotalPayout", "initialDebt"
    ]
    return dict(zip(keys, values))

def decode_true_bond_prices(data_bytes):
    prices = []
    offset = int.from_bytes(data_bytes[0:32], "big")  # offset to start of array
    length = int.from_bytes(data_bytes[offset:offset+32], "big")  # number of tuples
    cursor = offset + 32

    for _ in range(length):
        price = int.from_bytes(data_bytes[cursor:cursor+32], "big")
        min_amt = int.from_bytes(data_bytes[cursor+32:cursor+64], "big")
        max_amt = int.from_bytes(data_bytes[cursor+64:cursor+96], "big")
        prices.append([price, min_amt, max_amt])
        cursor += 96

    return prices

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