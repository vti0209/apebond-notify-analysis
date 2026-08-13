import requests
import json
import mysql.connector
from datetime import time
import time
import os
import tempfile
from web3 import Web3
from config import RPC_URLS, API_KEYS, DB_CONFIG, MULTICALL_V3_ADDRESS, CHAIN_IDS
from call_multicall import MULTICALL_V3_ABI, decode_address, decode_uint256, decode_terms, decode_true_bond_prices
from helpers import get_token_price_unified, get_pair_token_price_dexscreener
import concurrent.futures
from logging_setup import log

ABI_CACHE_DIR = "abi_cache"
def get_abi(chain, bond_address):
    os.makedirs(ABI_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(ABI_CACHE_DIR, f"{chain.lower()}_{bond_address.lower()}.json")

    # Nếu file cache ABI đã có -> load lên
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            # print("✅ Đọc ABI từ file cache")
            return json.load(f)

    # Nếu chưa có, gọi API
    if chain not in API_URLS or chain not in API_KEYS:
        log.error(f"❌ No API URL or API Key for {chain}")
        return None

    etherscan_url = API_URLS[chain]
    params = {
        "module": "contract",
        "action": "getabi",
        "address": bond_address,
        "apikey": API_KEYS[chain]
    }

    try:
        response = requests.get(etherscan_url, params=params, timeout=10)
        response_json = response.json()

        if response.status_code == 200 and response_json["status"] == "1":
            try:
                abi = json.loads(response_json["result"])
                
                # Ghi ra file tạm
                with tempfile.NamedTemporaryFile("w", delete=False, dir=ABI_CACHE_DIR, suffix=".tmp") as tmp_file:
                    json.dump(abi, tmp_file)
                    temp_name = tmp_file.name

                # Đổi tên thành file chính thức (atomic operation)
                os.replace(temp_name, cache_file)
                log.info(f"✅ ABI cached to: {cache_file}")

                return abi

            except json.JSONDecodeError:
                log.error("❌ Error while decoding JSON ABI")
                return None
        else:
            log.error(f"❌ Don't get ABI: {response_json['result']}")
            return None

    except requests.exceptions.RequestException as e:
        log.error(f"❌ Error retrieving contract ABI: {e}")
        return None

def get_target_token_address(web3: Web3, token_address: str) -> str:
    token_address = web3.to_checksum_address(token_address)

    # EIP-1967
    try:
        slot = web3.keccak(text="eip1967.proxy.implementation")
        impl_slot = int.from_bytes(slot, byteorder='big') - 1
        raw = web3.eth.get_storage_at(token_address, impl_slot)
        if raw and len(raw) == 32 and int(raw.hex(), 16) != 0:
            impl_address = web3.to_checksum_address('0x' + raw.hex()[-40:])
            return impl_address
    except: pass

    # EIP-897
    try:
        selector = web3.keccak(text='implementation()')[:4]
        result = web3.eth.call({'to': token_address, 'data': selector.hex()})
        if result and len(result) == 32:
            impl_address = web3.to_checksum_address('0x' + result.hex()[-40:])
            return impl_address
    except: pass

    # EIP-1167 minimal proxy
    try:
        bytecode = web3.eth.get_code(token_address).hex()
        if bytecode.startswith('0x363d3d373d3d3d363d73') and bytecode.endswith('5af43d82803e903d91602b57fd5bf3'):
            impl_address = '0x' + bytecode[22:62]
            impl_address = web3.to_checksum_address(impl_address)
            return impl_address
    except: pass

    # Nếu không phải proxy, trả về token gốc
    return token_address

# Connect to web3
def get_web3_connection(chain_name):
    provider_url = RPC_URLS.get(chain_name)
    if not provider_url:
        raise Exception(f"❌ No RPC URL for {chain_name}")
    return Web3(Web3.HTTPProvider(provider_url))

# Create Instance contract
def get_contract(web3, contract_address, abi):
    contract = web3.eth.contract(address=contract_address, abi=abi)
    return contract

def load_abi(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def get_data_bond_contract(chain, bond_address, multicall_v3_address=MULTICALL_V3_ADDRESS):
    web3 = get_web3_connection(chain)
    cs_bond_address = Web3.to_checksum_address(bond_address)
    
    # Tạo callData cho các hàm
    payout_sig = web3.keccak(text="payoutToken()")[:4]
    principal_sig = web3.keccak(text="principalToken()")[:4]
    true_bill_price_sig = web3.keccak(text="trueBillPrice()")[:4]
    terms_sig = web3.keccak(text="terms()")[:4]
    fee_in_payout_sig = web3.keccak(text="feeInPayout()")[:4]
    true_bond_price_tier_sig = web3.keccak(text="trueBondPrices()")[:4]

    calls = [
        {"target": cs_bond_address, "callData": payout_sig},
        {"target": cs_bond_address, "callData": principal_sig},
        {"target": cs_bond_address, "callData": true_bill_price_sig},
        {"target": cs_bond_address, "callData": terms_sig},
        {"target": cs_bond_address, "callData": fee_in_payout_sig},
        {"target": cs_bond_address, "callData": true_bond_price_tier_sig},
    ]
    
    contract = get_contract(web3, Web3.to_checksum_address(multicall_v3_address), abi=MULTICALL_V3_ABI)
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
        
    return payout_token, principal_token, true_bill_price, true_bond_price_tier, terms, fee_in_payout

def get_token_decimals_and_symbol(chain, token_address, resolve_proxy=False):
    web3 = get_web3_connection(chain)
    token_address = Web3.to_checksum_address(token_address)

    target_token_address = None  # <- fix lỗi UnboundLocalError

    if resolve_proxy:
        target_token_address = get_target_token_address(web3, token_address)
        log.info(f"Resolved proxy token address: {target_token_address}")

    try:
        abi_address = target_token_address if target_token_address else token_address
        contract = get_contract(web3, token_address, abi=get_abi(chain, abi_address))
        decimals = contract.functions.decimals().call()
        symbol = contract.functions.symbol().call()
    except Exception as e:
        log.error(f"[ERROR] Failed to get token info: {e}")
        decimals = None
        symbol = None

    return decimals, symbol

def get_token_info_cached(chain, token_address, db_conn, resolve_proxy=False):
    token_address = Web3.to_checksum_address(token_address)
    cursor = db_conn.cursor()

    # 1. Check cache trong MySQL
    sql_select = """
        SELECT decimals, symbol FROM token_info_cache
        WHERE chain = %s AND token_address = %s
    """
    cursor.execute(sql_select, (chain, token_address))
    result = cursor.fetchone()

    if result and all(result):
        return result[0], result[1]  # decimals, symbol

    # 2. Nếu chưa có cache → gọi chain
    decimals, symbol = get_token_decimals_and_symbol(chain, token_address, resolve_proxy=resolve_proxy)

    # 3. Ghi vào cache nếu gọi thành công
    if decimals is not None and symbol is not None:
        sql_insert = """
            INSERT INTO token_info_cache (chain, token_address, decimals, symbol, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE decimals = VALUES(decimals), symbol = VALUES(symbol), updated_at = NOW()
        """
        cursor.execute(sql_insert, (chain, token_address, decimals, symbol))
        db_conn.commit()

    return decimals, symbol

def get_data_principal_token(chain, principal_token_address, db_conn):
    web3 = get_web3_connection(chain)
    cs_principal_token_address = Web3.to_checksum_address(principal_token_address)
    
    if cs_principal_token_address.lower() == "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48".lower():
        target_token = "0x43506849d7c04f9138d1a2050bbf3a0c054402dd"
    else:
        target_token = get_target_token_address(web3, cs_principal_token_address)
    
    contract = get_contract(web3, cs_principal_token_address, abi=get_abi(chain, target_token))

    try:
        # Ưu tiên thử gọi getReserves()
        reserves = contract.functions.getReserves().call()
        token0 = contract.functions.token0().call()
        token1 = contract.functions.token1().call()
        total_supply = contract.functions.totalSupply().call()
        decimals = contract.functions.decimals().call()
        symbol = contract.functions.symbol().call()
        target_token0 = get_target_token_address(web3, Web3.to_checksum_address(token0))
        target_token1 = get_target_token_address(web3, Web3.to_checksum_address(token1))
        token0_decimal, token0_symbol = get_token_info_cached(chain, Web3.to_checksum_address(target_token0), db_conn=db_conn)
        token1_decimal, token1_symbol = get_token_info_cached(chain, Web3.to_checksum_address(target_token1), db_conn=db_conn)
        
        # tokens_pair_price = get_pair_token_price_dexscreener(principal_token_address, chain)
        # # Kiểm tra và lấy giá của token0 và token1, nếu không có thì gọi API
        # token0_price = tokens_pair_price.get(token0.lower()) if tokens_pair_price else None
        # token1_price = tokens_pair_price.get(token1.lower()) if tokens_pair_price else None
        token0_price = get_token_price_unified(chain, token0)
        token1_price = get_token_price_unified(chain, token1)
        
        log.info(f"[{chain}] 💰 Token0: {token0} ({token0_symbol}) - Price: {token0_price} - Decimal: {token0_decimal} USD")
        log.info(f"[{chain}] 💰 Token1: {token1} ({token1_symbol}) - Price: {token1_price} - Decimal: {token1_decimal} USD")

        reserves0 = reserves[0] / 10**token0_decimal
        reserves1 = reserves[1] / 10**token1_decimal
        value_usd = reserves0 * token0_price + reserves1 * token1_price
        principal_token_price = value_usd / (total_supply / (10 ** decimals))
        
        return {
            "type": "lp",
            "principal_token_address": principal_token_address,
            "principal_token_symbol": symbol,
            "principal_token_decimal": decimals,
            "principal_token_price": principal_token_price
        }

    except Exception as e_reserves:
        # print(f"[WARNING] getReserves() failed: {str(e_reserves)}")
        try:
            # Fallback: sử dụng getTotalAmount()
            total0, total1 = contract.functions.getTotalAmounts().call()
            token0 = contract.functions.token0().call()
            token1 = contract.functions.token1().call()
            total_supply = contract.functions.totalSupply().call()
            decimals = contract.functions.decimals().call()
            symbol = contract.functions.symbol().call()
            target_token0 = get_target_token_address(web3, Web3.to_checksum_address(token0))
            target_token1 = get_target_token_address(web3, Web3.to_checksum_address(token1))
            token0_decimal, token0_symbol = get_token_info_cached(chain, Web3.to_checksum_address(target_token0), db_conn=db_conn)
            token1_decimal, token1_symbol = get_token_info_cached(chain, Web3.to_checksum_address(target_token1), db_conn=db_conn)
            tokens_pair_price = get_pair_token_price_dexscreener(principal_token_address, chain)
            # Kiểm tra và lấy giá của token0 và token1, nếu không có thì gọi API
            token0_price = tokens_pair_price.get(token0.lower()) if tokens_pair_price else None
            token1_price = tokens_pair_price.get(token1.lower()) if tokens_pair_price else None

            # Nếu không có giá từ Dexscreener, tiếp tục gọi API khác
            if not token0_price:
                token0_price = get_token_price_unified(chain, token0)

            if not token1_price:
                token1_price = get_token_price_unified(chain, token1)

            log.info(f"[{chain}] Token0: {token0} ({token0_symbol}) - Price: {token0_price} USD")
            log.info(f"[{chain}] Token1: {token1} ({token1_symbol}) - Price: {token1_price} USD")
            
            amount0 = total0 / 10**token0_decimal
            amount1 = total1 / 10**token1_decimal
            value_usd = amount0 * token0_price + amount1 * token1_price
            principal_token_price = value_usd / (total_supply / (10 ** decimals))

            return {
                "type": "lp_totalAmount",
                "principal_token_address": principal_token_address,
                "principal_token_symbol": symbol,
                "principal_token_decimal": decimals,
                "principal_token_price": principal_token_price
            }

        except Exception as e_total:
            # print(f"[WARNING] getTotalAmounts() failed: {str(e_total)}")
            try:
                # Nếu không phải LP thì coi như token thường
                token_address = Web3.to_checksum_address(principal_token_address)
                token_decimal = contract.functions.decimals().call()
                token_symbol = contract.functions.symbol().call()
                return {
                    "type": "token",
                    "token_address": token_address,
                    "decimals": token_decimal,
                    "symbol": token_symbol
                }
            except Exception as e:
                return {
                    "type": "unknown",
                    "error": f"getReserves error: {str(e_reserves)}; getTotalAmount error: {str(e_total)}; final: {str(e)}"
                }

def calc_bonus_with_fee(bonus, fee_in_payout):
    if fee_in_payout == 0:
        return bonus
    return ((1 + bonus / 100) * (1 - (fee_in_payout/10000) / 100) - 1) * 100

def process_single_bond_evm(bond):
    log.info(f"Processing bond: {bond.get('chain')} - {bond.get('contract_address')} - {bond.get('token_symbol')}")
    chain_name = bond.get("chain")
    bond_address = bond.get("contract_address")
    bond_name = bond.get("token_symbol")
    status = bond.get("status")

    if status != "active":
        return None
    skip_addresses = [
        '0x4075b614e75cb4aed6c8de4b0180e3d2bede4308',  # BG
        '0x3b4e1a2d575fb77fc10fefe182b8e4b01d3563f6',  # AST
        '0xc22760166957e94fac54a8b354c909d6d5eb18d1',  # oABOND
        '0x6e0155343c079ee06cef2209b12bee2cc8ec785b',  # SUSDT
        '0x0b62bd499cd80552b1f55c97fb27ac9e13bacc9a',  # EV
        '0xcf177f0c6629b5cdad23a31a750821fea0e7c439',  # ETAN
        '0xba80c4bd8d297aaadf0cf3dbe65944ab0d24c258',  # GGBR
        '0x373f3a5d300f61cd299036ba434b6d3a130a7847'   # MASQ
    ]
    if bond_address.lower() in [addr.lower() for addr in skip_addresses]:
        log.info(f"Skipping known problematic bond: {bond_name}")
        return None
    
    connection = mysql.connector.connect(**DB_CONFIG)
    
    try:
        cs_bond_address = Web3.to_checksum_address(bond_address)
        payout_token, principal_token, true_bill_price, true_bond_price_tier, terms, fee_in_payout = get_data_bond_contract(chain_name, cs_bond_address)
        payout_token_decimal, payout_token_symbol = get_token_info_cached(chain_name, Web3.to_checksum_address(payout_token), db_conn=connection, resolve_proxy=True) 
        principal_token_data = get_data_principal_token(chain_name, Web3.to_checksum_address(principal_token), db_conn=connection)

        principal_token_price = 0
        principal_token_decimal = 0
        
        if principal_token_data["type"] in ["lp", "lp_totalAmount"]:
            principal_token_address = principal_token_data["principal_token_address"]
            principal_token_symbol = principal_token_data["principal_token_symbol"]
            principal_token_price = principal_token_data.get("principal_token_price", 0)
            principal_token_decimal = principal_token_data.get("principal_token_decimal", 18)
            if not principal_token_price:
                principal_token_price = get_token_price_unified(chain_name, principal_token_data["principal_token_address"])
            log.info(f"+ principal_token_address: {principal_token_address} ({principal_token_symbol}) - principal_token_price: {principal_token_price}, principal_token_decimal: {principal_token_decimal}")
        elif principal_token_data["type"] == "token":
            principal_token_address = principal_token_data["token_address"]
            principal_token_symbol = principal_token_data["symbol"]
            principal_token_price = get_token_price_unified(chain_name, principal_token_data["token_address"])
            principal_token_decimal = principal_token_data.get("decimals", 18)
            log.info(f"+ principal_token_address: {principal_token_address} ({principal_token_symbol}) principal_token_price: {principal_token_price}, principal_token_decimal: {principal_token_decimal}")
        else:
            return None  
        
        # Fallback giá token nếu chưa có
        if not principal_token_price or principal_token_price == 0:
            return None
        
        payout_token_price = get_token_price_unified(chain_name, payout_token)
        if not payout_token_price or payout_token_price == 0:
            return None
        log.info(f"+ payout_token_address: {payout_token} ({payout_token_symbol}) - payout_token_price: {payout_token_price}, payout_token_decimal: {payout_token_decimal}")
        
        # Xác định ngưỡng nhỏ cho bond price, tránh trường hợp bond_price quá nhỏ
        MIN_BOND_PRICE_THRESHOLD = max(1e-12, payout_token_price / 1000)
        
        # Tính bonus
        if true_bond_price_tier:
            true_bond_prices, _, _ = zip(*true_bond_price_tier)
            bonuses = []
            for true_bond_price in true_bond_prices:
                bond_price = principal_token_price * (true_bond_price / (10 ** 18))
                
                if bond_price <= 0 or bond_price < MIN_BOND_PRICE_THRESHOLD:
                    log.warning(f"⚠️ Invalid bond_price detected: {bond_price}. Skipping this tier.")
                    continue
                    
                discount = (payout_token_price - bond_price) / payout_token_price * 100
                bonus = (payout_token_price / bond_price - 1) * 100
                bonuses.append(bonus)
                log.info(f"+ true_bond_price: {true_bond_price}, bond_price: {bond_price}, discount: {discount}, bonus: {bonus}")
                
            if bonuses:
                min_bonus = calc_bonus_with_fee(min(bonuses), fee_in_payout)
                max_bonus = calc_bonus_with_fee(max(bonuses), fee_in_payout)
                log.info(f"+ min_bonus: {min_bonus}, max_bonus: {max_bonus}")
            else:
                min_bonus = max_bonus = 0
        else:
            # Tính bonus từ true_bill_price
            bond_price = principal_token_price * (true_bill_price / (10 ** 18))
            
            if bond_price <= 0 or bond_price < MIN_BOND_PRICE_THRESHOLD:
                log.warning(f"⚠️ Invalid bond_price detected: {bond_price}. Skipping bonus calculation.")
                min_bonus = max_bonus = 0
            else: 
                discount = (payout_token_price - bond_price) / payout_token_price * 100
                bonus = (payout_token_price / bond_price - 1) * 100
                min_bonus = max_bonus = calc_bonus_with_fee(bonus, fee_in_payout)
                log.info(f"+ true_bill_price: {true_bill_price}, bond_price: {bond_price}, discount: {discount}, bonus: {bonus}, min_bonus: {min_bonus}, max_bonus: {max_bonus}")
        
        min_bonus = max(min_bonus, 0)
        max_bonus = max(max_bonus, 0)

        date_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        min_price = terms.get('minimumPrice') / (10 ** principal_token_decimal)
        max_price = terms.get('maxTotalPayout') / (10 ** payout_token_decimal)
        max_buy = terms.get('maxPayout') / (10 ** payout_token_decimal)
        log.info(f"+ min_price: {min_price}, max_price: {max_price}, max_buy: {max_buy}, fee_in_payout: {fee_in_payout}")
        
        # Lưu kết quả
        return {
            "chain": chain_name,
            "bond_name": bond_name,
            "bond_address": bond_address,
            "date_time": date_time,
            "min_bonus": min_bonus,
            "max_bonus": max_bonus,
            "min_price": min_price,
            "max_price": max_price,
            "max_buy": max_buy,
            "notify_threshold": bond.get("notify_threshold", 20.0)
        }
        
    except Exception as inner_e:
        log.error(f"⚠️ Error while processing bond {bond_name} on {chain_name}: {inner_e}")
        return None
    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()

def process_bonds(bond_datas):
    bond_results = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_bond = {executor.submit(process_single_bond_evm, bond): bond for bond in bond_datas}
            for future in concurrent.futures.as_completed(future_to_bond):
                try:
                    result = future.result()
                    if result:
                        bond_results.append(result)
                except Exception as exc:
                    log.warning(f"⚠️ Thread error in EVM processing: {exc}")
        return bond_results
    except Exception as e:
        error_message = f"⚠️ *Error happened in process_bond:* {str(e)}"
        log.info(error_message)
        return bond_results