from config import (
    COINGECKO_CHAIN_ID, DEXSCREENER_CHAIN_ID, DISCORD_WEBHOOK_URL, CHANNEL_ID, CHAIN_IDS
)
import requests
import statistics
import discord  
from datetime import datetime, time as dt_time, timedelta, timezone
import gc
from logging_setup import log

# In-memory cache for token prices during a single execution run
price_cache = {}
_apebond_api_fetched = False

# Khởi tạo client cho bot
client = discord.Client(intents=discord.Intents.default())

# Send Discord message function
async def send_discord_message(message: str):
    await client.wait_until_ready() 
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(message)
    else:
        log.error("❌ Không tìm thấy channel Discord.")
        
def send_discord_webhook_message(content):
    payload = {
        "content": content
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        log.error(f"❌ Failed to send Discord webhook message: {e}")

# VN Timezone
VN_TZ = timezone(timedelta(hours=7))

# Bebtime setting
bedtime_start = dt_time(23, 30)
bedtime_end = dt_time(6, 30)

# Check if it's bedtime
def set_bedtime():
    now = datetime.now(VN_TZ).time()
    if bedtime_start < bedtime_end:
        return bedtime_start <= now < bedtime_end
    else:
        return now >= bedtime_start or now < bedtime_end

# Sleep to wake up time
def sleep_until_wakeup():
    now = datetime.now(VN_TZ)
    wakeup_time = datetime.combine(now.date(), bedtime_end).replace(tzinfo=VN_TZ)

    if now.time() >= bedtime_end:
        wakeup_time += timedelta(days=1)

    sleep_seconds = (wakeup_time - now).total_seconds()

    sleep_message = f"💤🤖 Bot is sleeping. Sleep {str(timedelta(seconds=int(sleep_seconds)))} seconds."
    log.info(sleep_message)
    # send_discord_webhook_message(sleep_message)
    
    del sleep_message
    gc.collect()


def get_token_price_api(token_address, chain):
    chain_id = COINGECKO_CHAIN_ID.get(chain)
    if not chain_id:
        log.error(f"[{chain}] ❌ Invalid chain id.")
        return None

    token_address_lower = token_address.lower()
    url = f"https://api.coingecko.com/api/v3/simple/token_price/{chain_id}?contract_addresses={token_address_lower}&vs_currencies=usd"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            log.error(f"[{chain}] ❌ HTTP error {r.status_code}: {r.text}")
            return None

        data = r.json()
        price = data.get(token_address_lower, {}).get("usd")
        if price:
            # print(f"[{chain}] ✅ Price from API: {price} USD")
            return price
        else:
            log.error(f"[{chain}] ❌ Token not found in response: {data}")
    except Exception as e:
        log.error(f"[{chain}] ❌ API error: {e}")
    return None

def get_token_price_dexscreener(token_address, preferred_quote=["USDC", "USDT", "WBNB", "WETH"], chain=None):
    chain_id = DEXSCREENER_CHAIN_ID.get(chain)
    if chain_id is None:
        log.error(f"[{chain}] ❌ Invalid chain id.")
        return None

    try:
        url = f"https://api.dexscreener.com/latest/dex/search?q={token_address}"
        r = requests.get(url, timeout=10)
        data = r.json()
        pairs = data.get("pairs", [])

        token_address = token_address.lower()
        preferred_quote_set = set(q.upper() for q in preferred_quote)

        valid_candidates = []

        for pair in pairs:
            if pair.get("chainId") != chain_id:
                continue

            base = pair.get("baseToken", {})
            quote = pair.get("quoteToken", {})
            base_addr = base.get("address", "").lower()
            quote_addr = quote.get("address", "").lower()
            base_symbol = base.get("symbol", "").upper()
            quote_symbol = quote.get("symbol", "").upper()
            price_usd = pair.get("priceUsd")
            price_native = pair.get("priceNative")
            liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0))

            if not price_usd or liquidity_usd == 0:
                continue

            price = None
            if base_addr == token_address:
                price = float(price_usd)
                quote_sym = quote_symbol
            elif quote_addr == token_address and price_native:
                try:
                    price = 1 / float(price_native) * float(price_usd)
                    quote_sym = base_symbol
                except ZeroDivisionError:
                    continue
            else:
                continue

            valid_candidates.append({
                "price": price,
                "liquidity": liquidity_usd,
                "quote_symbol": quote_sym,
                "is_preferred": quote_sym in preferred_quote_set,
                "pair_url": pair.get("url"),
            })

        if not valid_candidates:
            log.warning(f"⚠️ Không tìm được cặp phù hợp cho token {token_address} trên {chain}")
            return None

        # Ưu tiên chỉ dùng cặp quote preferred nếu có
        prioritized = [c for c in valid_candidates if c["is_preferred"]]
        candidates = prioritized if prioritized else valid_candidates

        prices = [c["price"] for c in candidates]
        mean_price = statistics.mean(prices)
        std_price = statistics.stdev(prices) if len(prices) > 1 else 0

        # Lọc outliers theo Z-score > 2
        filtered = []
        for c in candidates:
            z = abs((c["price"] - mean_price) / std_price) if std_price > 0 else 0
            if z <= 2:
                filtered.append(c)

        if not filtered:
            log.warning("⚠️ Tất cả các giá đều bị loại vì lệch chuẩn quá lớn.")
            return None

        # Tính giá trung bình có trọng số theo thanh khoản
        total_liquidity = sum(c["liquidity"] for c in filtered)
        weighted_price = sum(c["price"] * c["liquidity"] for c in filtered) / total_liquidity

        # print(f"+ Giá trung bình (weighted) từ {len(filtered)} cặp: {weighted_price:.6f}")
        # for c in filtered:
        #     print(f"  - {c['quote_symbol']:>5} @ {c['price']:.6f} (liq: {c['liquidity']:.0f}) | {c['pair_url']}")

        return weighted_price

    except Exception as e:
        log.info(f"DexScreener error: {e}")
        return None

def get_token_price_from_apebond_api(chain_id, token_address):
    url = "https://realtime-api.ape.bond/bonds"
    token_address = token_address.lower()

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        response_json = response.json()

        bonds = response_json.get("bonds", [])
        log.info(f"✅ Got {len(bonds)} bonds from ApeBond API")

        for bond in bonds:
            if (
                bond.get("chainId") == chain_id and
                bond.get("payoutToken", "").lower() == token_address
            ):
                price_str = bond.get("payoutTokenPrice")
                if price_str:
                    try:
                        price = float(price_str)
                        log.info(f"✅ Found token price: {price:.6f} USD")
                        return price
                    except ValueError:
                        log.warning(f"⚠️ Invalid price value: {price_str}")
                        return None

        log.warning(f"⚠️ Token {token_address} on chain {chain_id} not found in ApeBond bonds")
        return None

    except requests.RequestException as e:
        log.info(f"[ERROR] Request failed: {e}")
        return None

def get_pair_token_price_dexscreener(token_address, chain):
    chain_id = DEXSCREENER_CHAIN_ID.get(chain)
    if not chain_id:
        log.error(f"[{chain}] ❌ Invalid chain id.")
        return None
    
    token_address_lower = token_address.lower()
    url = f"https://api.dexscreener.com/latest/dex/pairs/{chain_id}/{token_address_lower}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            raise Exception(f"API request failed with status code {response.status_code}")
    
        data = response.json()
        base = data["pair"]["baseToken"]
        quote = data["pair"]["quoteToken"]
        price_usd = float(data["pair"]["priceUsd"])
        price_native = float(data["pair"]["priceNative"])

        if price_native == 0:
            raise ValueError("priceNative is 0, cannot divide")

        quote_price_usd = (1 / price_native) * price_usd

        return {
            base["address"]: price_usd,
            quote["address"]: quote_price_usd
        }
    except Exception as e:
        log.error(f"[{chain}] ❌ API error dexscreener: {e}")
    return None

def get_price_tokens_coingecko(chain_id, token_address):
    PLATFORM_MAP = {
        56: "binance-smart-chain",
        1: "ethereum",
        137: "polygon-pos",
        42161: "arbitrum-one",
        59144: "linea",
        8453: "base",
        7565164: "solana"
    }

    platform = PLATFORM_MAP.get(int(chain_id))
    if not platform:
        log.error(f"❌ Unsupported chain_id for CoinGecko: {chain_id}")
        return 0

    url = f"https://api.coingecko.com/api/v3/simple/token_price/{platform}?contract_addresses={token_address}&vs_currencies=usd"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        price = data.get(token_address, {}).get("usd", 0)
        log.info(f"💰 CoinGecko price for {token_address}: {price}")
        return price
    except Exception as e:
        log.error(f"❌ CoinGecko Error: {e}")
        return 0

def get_token_price_by_apebond_api(chain_id, token_address):
    global _apebond_api_fetched
    url = "https://price-api.ape.bond/realtime/prices"
    
    # Map chain_id back to chain_name for price_cache keys
    id_to_name = {v: k for k, v in CHAIN_IDS.items()}
    id_to_name[7565164] = "SOL"
    id_to_name[10143] = "SOL"

    if not _apebond_api_fetched:
        try:
            # We call the API once and populate the global price_cache for all tokens
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for cid_str, tokens in data.items():
                    cid = int(cid_str)
                    name = id_to_name.get(cid)
                    if not name:
                        if cid in (7565164, 10143):
                            name = "SOL"
                        else:
                            continue
                    
                    for t in tokens:
                        addr = t.get("tokenAddress", "").lower()
                        price = t.get("price")
                        if addr and price:
                            price_cache[f"{name}_{addr}"] = float(price)
                            if cid in (7565164, 10143):
                                price_cache[f"SOL_{addr}"] = float(price)
                
                _apebond_api_fetched = True
                log.info(f"✅ ApeBond Price API: Cached prices for all supported chains.")
            else:
                log.warning(f"⚠️ ApeBond Price API returned status {resp.status_code}")
        except Exception as e:
            log.error(f"❌ Error fetching from ApeBond Price API: {e}")
            # Mark as fetched to avoid repeated failed calls in the same run
            _apebond_api_fetched = True

    # Look up the specific token in the newly populated cache
    name = id_to_name.get(chain_id)
    if name:
        res = price_cache.get(f"{name}_{token_address.lower()}")
        if res:
            return res

    return price_cache.get(f"SOL_{token_address.lower()}")

def get_token_price_unified(chain_name, token_address):
    """
    Unified function to get token price with in-memory caching.
    Tries ApeBond API -> CoinGecko -> Dexscreener.
    """
    token_address = token_address.lower()
    cache_key = f"{chain_name}_{token_address}"
    
    if cache_key in price_cache:
        # print(f"✅ Price retrieved from cache for {token_address} on {chain_name}")
        return price_cache[cache_key]
        
    chain_id = CHAIN_IDS.get(chain_name)
    if chain_name == "SOL":
        chain_id = 7565164
    
    price = None
    
    # 1. Try ApeBond API
    if chain_id:
        price = get_token_price_by_apebond_api(chain_id, token_address)
        
    # 2. Try CoinGecko API if ApeBond fails
    if not price or price == 0:
        if chain_name == "SOL":
            price = get_price_tokens_coingecko(7565164, token_address)
        else:
            price = get_token_price_api(token_address, chain=chain_name)
            
    # 3. Try Dexscreener API if CoinGecko fails
    if not price or price == 0:
        price = get_token_price_dexscreener(token_address, chain=chain_name)
        
    if price and price > 0:
        price_cache[cache_key] = price
        return price
        
    return 0
