import struct
from solders.pubkey import Pubkey
from solana.rpc.api import Client
import time
from config import DB_CONFIG, HELIUS_RPC_URL
import mysql.connector
from helpers import get_token_price_unified
import concurrent.futures
from logging_setup import log

PERCENTAGE_BASE = 10**6
client = Client(HELIUS_RPC_URL)
PROGRAM_ID = Pubkey.from_string("57GQDhcco4bv4Ngcg7gc6huEYepnGU4PZAGHQCFJmjNW")
METAPLEX_PROGRAM_ID = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")

def parse_pubkey(data: bytes) -> str:
    return str(Pubkey.from_bytes(data))

def parse_bond(data: bytes):
    if len(data) < 96:
        raise ValueError("Dữ liệu quá ngắn cho Bond")

    offset = 8  # Bỏ qua Anchor discriminator

    nft_mint = parse_pubkey(data[offset:offset+32]); offset += 32
    payout = struct.unpack_from("<Q", data, offset)[0]; offset += 8
    payout_claimed = struct.unpack_from("<Q", data, offset)[0]; offset += 8
    vesting_start_timestamp = struct.unpack_from("<Q", data, offset)[0]; offset += 8
    last_claim_timestamp = struct.unpack_from("<Q", data, offset)[0]; offset += 8
    true_price_paid = struct.unpack_from("<Q", data, offset)[0]; offset += 8
    vesting = struct.unpack_from("<Q", data, offset)[0]; offset += 8
    vesting_term = struct.unpack_from("<Q", data, offset)[0]; offset += 8

    return {
        "nftMint": nft_mint,
        "payout": str(payout),
        "payoutClaimed": str(payout_claimed),
        "vestingStartTimestamp": vesting_start_timestamp,
        "lastClaimTimestamp": last_claim_timestamp,
        "truePricePaid": str(true_price_paid),
        "vesting": str(vesting),
        "vestingTerm": vesting_term
    }

def parse_bond_pricing(data: bytes):
    if len(data) < 48:
        raise ValueError("Dữ liệu quá ngắn cho BondPricing")
    
    offset = 8  
    total_debt, total_payout_given, total_principal_billed, last_decay, last_bcv_update_timestamp, min_bcv_update_interval = struct.unpack_from("<6Q", data, offset)
    offset += 8 * 6

    return {
        "total_debt": total_debt,
        "total_payout_given": total_payout_given,
        "total_principal_billed": total_principal_billed,
        "last_decay": last_decay,
        "last_bcv_update_timestamp": last_bcv_update_timestamp,
        "min_bcv_update_interval": min_bcv_update_interval
    }, offset

def parse_bond_term(data: bytes):
    if len(data) < 65:
        raise ValueError("Dữ liệu quá ngắn cho BondTerm")
    
    offset = 8
    control_variable, vesting_end, minimum_price, max_payout, max_debt, max_total_payout, initial_debt, payout_token_initial_supply = struct.unpack_from("<8Q", data, offset)
    offset += 8 * 8
    vesting_strategy = data[offset]; offset += 1
    
    return {
        "control_variable": control_variable,
        "vesting_end": vesting_end,
        "minimum_price": minimum_price,
        "max_payout": max_payout,
        "max_debt": max_debt,
        "max_total_payout": max_total_payout,
        "initial_debt": initial_debt,
        "payout_token_initial_supply": payout_token_initial_supply,
        "vesting_strategy": vesting_strategy
    }, offset
    
def parse_bond_issuance(data: bytes):
    if len(data) < 260:
        raise ValueError("Dữ liệu quá ngắn cho BondIssuance")

    offset = 8
    issuance_counter = struct.unpack_from("<I", data, offset)[0]; offset += 4
    bond_counter = struct.unpack_from("<I", data, offset)[0]; offset += 4

    payout_mint = parse_pubkey(data[offset:offset+32]); offset += 32
    principal_mint = parse_pubkey(data[offset:offset+32]); offset += 32

    principal_mint_decimals = data[offset]; offset += 1
    payout_mint_decimals = data[offset]; offset += 1

    treasury_ata = parse_pubkey(data[offset:offset+32]); offset += 32

    # Status: Enum-like, assume 1 byte tag
    status_tag = data[offset]; offset += 1
    status_map = {0: "paused", 1: "active", 2: "closed"}
    status = {status_map.get(status_tag, "unknown"): {}}

    fee_in_principal, = struct.unpack_from("<Q", data, offset); offset += 8
    fee_principal_recipient = parse_pubkey(data[offset:offset+32]); offset += 32

    fee_in_payout, = struct.unpack_from("<Q", data, offset); offset += 8
    fee_payout_recipient = parse_pubkey(data[offset:offset+32]); offset += 32

    partner_principal_recipient = parse_pubkey(data[offset:offset+32]); offset += 32
    collection = parse_pubkey(data[offset:offset+32]); offset += 32

    bump = data[offset]; offset += 1

    return {
        "issuanceCounter": issuance_counter,
        "bondCounter": bond_counter,
        "payoutMint": payout_mint,
        "principalMint": principal_mint,
        "principalMintDecimals": principal_mint_decimals,
        "payoutMintDecimals": payout_mint_decimals,
        "treasuryAta": treasury_ata,
        "status": status,
        "feeInPrincipal": str(fee_in_principal),
        "feePrincipalRecipient": fee_principal_recipient,
        "feeInPayout": str(fee_in_payout),
        "feePayoutRecipient": fee_payout_recipient,
        "partnerPrincipalRecipient": partner_principal_recipient,
        "collection": collection,
        "bump": bump,
    }

def decode_metaplex_metadata(data: bytes) -> dict:
    if len(data) < 500:
        return {"error": "Dữ liệu quá ngắn cho Metadata"}

    offset = 65

    # Đọc name
    name_len = struct.unpack_from("<I", data, offset)[0]; offset += 4
    name = data[offset:offset + name_len].decode("utf-8"); offset += name_len

    # Symbol
    symbol_len = struct.unpack_from("<I", data, offset)[0]; offset += 4
    symbol = data[offset:offset + symbol_len].decode("utf-8"); offset += symbol_len

    # URI
    uri_len = struct.unpack_from("<I", data, offset)[0]; offset += 4
    uri = data[offset:offset + uri_len].decode("utf-8"); offset += uri_len

    # Seller Fee BPS (u16)
    seller_fee_basis_points = struct.unpack_from("<H", data, offset)[0]

    return {
        "name": name,
        "symbol": symbol,
        "uri": uri,
        "seller_fee_basis_points": seller_fee_basis_points
    }

def get_bond_term_pubkey(bond_issuance_pubkey: Pubkey, program_id: Pubkey) -> Pubkey:
    seeds = [
        b"bond_term",
        bytes(bond_issuance_pubkey)
    ]
    bond_term_pubkey, _ = Pubkey.find_program_address(seeds, program_id)
    return bond_term_pubkey

def get_bond_pricing_pubkey(bond_issuance_pubkey: Pubkey, program_id: Pubkey) -> Pubkey:
    seeds = [
        b"bond_pricing",
        bytes(bond_issuance_pubkey)
    ]
    bond_pricing_pubkey, _ = Pubkey.find_program_address(seeds, program_id)
    return bond_pricing_pubkey

def get_bond_pubkey(bond_issuance_pubkey: Pubkey, program_id: Pubkey, bond_index: int) -> Pubkey:
    seeds = [
        b"bond",
        bytes(bond_issuance_pubkey), 
        bond_index.to_bytes(4, "little")
    ]
    bond_pricing_pubkey, _ = Pubkey.find_program_address(seeds, program_id)
    return bond_pricing_pubkey

def get_metadata_account(mint: str, METAPLEX_PROGRAM_ID: Pubkey) -> Pubkey:
    seed = [
        b"metadata",
        bytes(METAPLEX_PROGRAM_ID),
        bytes(Pubkey.from_string(mint)),
    ]
    metadata_pubkey, _ = Pubkey.find_program_address(seed, METAPLEX_PROGRAM_ID)
    return metadata_pubkey

def calc_debt_decay(total_debt, last_decay_timestamp, current_timestamp, vesting_term):
    if vesting_term == 0:
        return total_debt
    
    timestamp_since_last = current_timestamp - last_decay_timestamp
    debt_decay = (total_debt * timestamp_since_last) / vesting_term
    if debt_decay > total_debt:
        return total_debt
    else:
        return debt_decay

def calc_current_debt(total_debt, debt_decay):
    return total_debt - debt_decay

def calc_debt_ratio(current_debt, payout_token_decimals, payout_token_initial_supply):
    return (current_debt * 10 ** payout_token_decimals * (10**18)) / payout_token_initial_supply

def calc_bill_price(principal_token_decimals, control_variable, debt_ratio, minimum_price):
    bill_price = (control_variable * debt_ratio * (10**16)) / 10**principal_token_decimals / 10**18
    
    if bill_price < minimum_price:
        bill_price = minimum_price
        return bill_price
    else:
        return bill_price

def calc_true_bond_price(bill_price, fee_in_principal):
    return (bill_price * PERCENTAGE_BASE) / (PERCENTAGE_BASE - fee_in_principal) 

def calc_bond_discount_bonus(payout_token_price, principal_token_price, true_bond_price):
    bond_price = principal_token_price * (true_bond_price / 10**18)
    
    if bond_price > 0:
        discount = (payout_token_price - bond_price) / payout_token_price * 100
        bonus = (payout_token_price / bond_price - 1) * 100
        return discount, bonus
    return 0, 0

def calc_bonus_with_fee(bonus, fee_in_payout):
    if fee_in_payout == 0:
        return bonus
    return ((1 + bonus / 100) * (1 - (fee_in_payout/10000) / 100) - 1) * 100

def process_single_bond_sol(bond):
    log.info(f"✅ Processing bond: {bond.get('chain')} - {bond.get('contract_address')} - {bond.get('token_symbol')}")
    chain_name = bond.get("chain")
    bond_address = bond.get("contract_address")
    bond_name = bond.get("token_symbol")
    status = bond.get("status")
    
    if status != "active":
        return None
        
    try:
        BOND_INSSUANCE_ACCOUNT = Pubkey.from_string(bond_address)
        
        resp = client.get_account_info(BOND_INSSUANCE_ACCOUNT).value
        raw_data = resp.data

        if raw_data is None:
            raise Exception("Không lấy được dữ liệu account")

        parsed_issuance = parse_bond_issuance(raw_data)

        # print("\n📌 Bond Issuance:")
        # print(parsed_issuance)

        bond_term_pubkey = get_bond_term_pubkey(BOND_INSSUANCE_ACCOUNT, PROGRAM_ID)
        bond_pricing_pubkey = get_bond_pricing_pubkey(BOND_INSSUANCE_ACCOUNT, PROGRAM_ID)

        bond_pricing_resp = client.get_account_info(bond_pricing_pubkey).value
        if bond_pricing_resp is None:
            raise Exception("Không lấy được dữ liệu Bond Pricing")
        bond_pricing_data = bond_pricing_resp.data
        parsed_bond_pricing, _ = parse_bond_pricing(bond_pricing_data)
        
        bond_term_resp = client.get_account_info(bond_term_pubkey).value
        if bond_term_resp is None:
            raise Exception("Không lấy được dữ liệu Bond Term") 
        bond_term_data = bond_term_resp.data
        parsed_bond_term, _ = parse_bond_term(bond_term_data)
        
        bond_counter = parsed_issuance["bondCounter"] - 1
        bond_pubkey = get_bond_pubkey(BOND_INSSUANCE_ACCOUNT, PROGRAM_ID, bond_counter)
        
        metadata_account = get_metadata_account(parsed_issuance["payoutMint"], METAPLEX_PROGRAM_ID)
        resp = client.get_account_info(metadata_account).value
        if resp:
            metadata_account_data = resp.data
            result = decode_metaplex_metadata(metadata_account_data)
            
            if "error" in result:
                log.warning(f"⚠️ Decode Metadata lỗi cho bond {bond_name}: {result['error']}")
            else:
                # Lấy tên token từ metadata nếu cần (hiện tại chưa dùng cho kết quả cuối)
                # bond_name_sol = result["name"]
                pass
        else:
            log.warning(f"⚠️ Không tìm thấy Metadata Account cho bond {bond_name} trên SOL. Bỏ qua.")
            
        total_debt = parsed_bond_pricing["total_debt"]
        last_decay_timestamp = parsed_bond_pricing["last_decay"]
        vesting_term = parsed_bond_term["vesting_end"]
        current_timestamp = int(time.time())
        payout_token_decimals = parsed_issuance["payoutMintDecimals"]
        principal_token_decimals = parsed_issuance["principalMintDecimals"]
        payout_token_initial_supply = parsed_bond_term["payout_token_initial_supply"]
        control_variable = parsed_bond_term["control_variable"]
        minimum_price = parsed_bond_term["minimum_price"]
        max_payout = parsed_bond_term["max_payout"]
        max_total_payout = parsed_bond_term["max_total_payout"]
        fee_in_principal = parsed_issuance["feeInPrincipal"]
        fee_in_payout = parsed_issuance["feeInPayout"]
        payout_token = parsed_issuance["payoutMint"]
        principal_token = parsed_issuance["principalMint"]
        
        debt_decay = calc_debt_decay(total_debt, last_decay_timestamp, current_timestamp, vesting_term)
        current_debt = calc_current_debt(total_debt, debt_decay)
        debt_ratio = calc_debt_ratio(current_debt, payout_token_decimals, payout_token_initial_supply)
        bill_price = calc_bill_price(principal_token_decimals, control_variable, debt_ratio, minimum_price)
        
        true_bond_price = calc_true_bond_price(bill_price, int(fee_in_principal))
        
        payout_token_price = get_token_price_unified("SOL", str(payout_token))
        principal_token_price = get_token_price_unified("SOL", str(principal_token))
        
        log.info(f"📌 Payout Token Price: {payout_token_price}")
        log.info(f"📌 Principal Token Price: {principal_token_price}")
        
        bonus_with_fee = 0
        if payout_token_price and principal_token_price and payout_token_price != 0 and principal_token_price != 0:
            discount, bonus = calc_bond_discount_bonus(payout_token_price, principal_token_price, true_bond_price)
            bonus_with_fee = calc_bonus_with_fee(bonus, int(fee_in_payout))
            log.info(f"📌 Discount: {discount} %")
            log.info(f"📌 Bonus: {bonus_with_fee} %")
    
        date_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        min_price = minimum_price / 10**(principal_token_decimals)
        max_buy = max_payout / 10**payout_token_decimals
        max_price = max_total_payout / 10**payout_token_decimals
        min_bonus = max_bonus = bonus_with_fee
        
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
            "notify_threshold": bond.get("notify_threshold", 10.0)
        }
        
    except Exception as inner_e:
        log.error(f"⚠️ Error while processing bond {bond_name} on {chain_name}: {inner_e}")
        return None

def process_bond_sol(bond_datas):
    bond_results = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_bond = {executor.submit(process_single_bond_sol, bond): bond for bond in bond_datas}
            for future in concurrent.futures.as_completed(future_to_bond):
                try:
                    result = future.result()
                    if result:
                        bond_results.append(result)
                except Exception as exc:
                    log.warning(f"⚠️ Thread error in SOL processing: {exc}")
        return bond_results
    except Exception as e:
        error_message = f"⚠️ *Error happened in process_bond:* {str(e)}"
        log.info(error_message)
        return bond_results

