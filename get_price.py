"""
Token price fetching with multi-source fallback.
Sources: ApeBond API, CoinGecko, DexScreener.
"""

import requests
import time
from functools import lru_cache
from config import APEBOND_PRICE_API
from logging_setup import log


@lru_cache(maxsize=1000)
def get_token_price(chain, token_address):
    """
    Get token price with fallback mechanism.
    
    Priority: ApeBond API -> DexScreener -> CoinGecko
    
    Args:
        chain (str): Blockchain name (ETH, BNB, SOL, etc.)
        token_address (str): Token contract address
    
    Returns:
        float: Token price in USD, or 0.0 if all sources fail
    """
    # Special case for SOL native token
    if token_address.lower() == 'so11111111111111111111111111111111111111112':
        log.debug("SOL native token detected, using SOL/USD price")
        return get_sol_price()

    # Try ApeBond API
    try:
        from helpers import get_token_price_from_apebond_api, get_pair_token_price_dexscreener
        from config import CHAIN_IDS

        chain_id = CHAIN_IDS.get(chain)
        if chain_id:
            price = get_token_price_from_apebond_api(chain_id, token_address)
            if price and price > 0:
                log.debug(f"Price from ApeBond: {token_address} = ${price}")
                return price

            price = get_pair_token_price_dexscreener(token_address, chain)
            if price and price > 0:
                log.debug(f"Price from DexScreener: {token_address} = ${price}")
                return price
    except Exception as e:
        log.warning(f"Helper price fetch failed: {e}")

    # Fallback to CoinGecko
    try:
        chain_map = {
            'ETH': 'ethereum',
            'BNB': 'binance-smart-chain',
            'POL': 'polygon-pos',
            'ARB': 'arbitrum-one',
            'BAS': 'base',
            'SOL': 'solana'
        }

        platform = chain_map.get(chain, chain.lower())

        if token_address.lower() == 'so11111111111111111111111111111111111111112':
            params = {'ids': 'solana', 'vs_currencies': 'usd'}
            url = "https://api.coingecko.com/api/v3/simple/price"
        else:
            params = {
                'contract_addresses': token_address,
                'vs_currencies': 'usd',
                'asset_platform': platform
            }
            url = "https://api.coingecko.com/api/v3/simple/token_price"

        time.sleep(0.1)  # Rate limiting

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if token_address.lower() == 'so11111111111111111111111111111111111111112':
                price = data.get('solana', {}).get('usd', 0)
            else:
                price = data.get(token_address.lower(), {}).get('usd', 0)

            if price > 0:
                log.debug(f"Price from CoinGecko: {token_address} = ${price}")
                return float(price)
    except Exception as e:
        log.warning(f"CoinGecko failed for {token_address}: {e}")

    # Fallback for SOL
    if token_address.lower() == 'so11111111111111111111111111111111111111112':
        log.warning("Using fallback SOL price $140")
        return 140.0

    log.error(f"All price sources failed for {token_address} on {chain}")
    return 0.0


def get_sol_price():
    """
    Get SOL price from CoinGecko.
    
    Returns:
        float: SOL price in USD, or fallback value
    """
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {'ids': 'solana', 'vs_currencies': 'usd'}
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            price = data.get('solana', {}).get('usd', 0)
            if price > 0:
                return float(price)
    except Exception:
        pass

    return 140.0  # Fallback SOL price