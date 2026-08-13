"""
Discord notification module.
Sends bond alerts via Discord webhook with formatted embed messages.
"""

import requests
from datetime import datetime
from config import DISCORD_WEBHOOK_URL
from logging_setup import log


def send_discord_notification(bond_data):
    """
    Send bond notification to Discord via webhook.
    
    Args:
        bond_data (dict): Bond data containing name, bonus, price, etc.
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    if not DISCORD_WEBHOOK_URL:
        log.warning("Discord webhook URL not configured")
        return False

    try:
        embed = {
            "title": f"Bond Alert: {bond_data.get('name', 'Unknown')}",
            "color": 0x00ff00 if bond_data.get('bonus', 0) > 30 else 0xffa500,
            "fields": [
                {
                    "name": "Bonus",
                    "value": f"{bond_data.get('bonus', 0):.2f}%",
                    "inline": True
                },
                {
                    "name": "Bond Price",
                    "value": f"${bond_data.get('bond_price_usd', 0):.4f}",
                    "inline": True
                },
                {
                    "name": "Max Buy",
                    "value": f"${bond_data.get('max_buy', 0):.2f}",
                    "inline": True
                },
                {
                    "name": "Chain",
                    "value": bond_data.get('chain', 'N/A'),
                    "inline": True
                },
                {
                    "name": "Symbol",
                    "value": bond_data.get('symbol', 'N/A'),
                    "inline": True
                },
                {
                    "name": "Contract",
                    "value": f"`{bond_data.get('contract_address', 'N/A')[:10]}...`",
                    "inline": False
                },
                {
                    "name": "Updated",
                    "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "inline": False
                }
            ],
            "footer": {
                "text": "ApeBond Notify"
            },
            "timestamp": datetime.now().isoformat()
        }

        # Add explorer link if available
        explorer_url = get_explorer_url(bond_data.get('chain'), bond_data.get('contract_address'))
        if explorer_url:
            embed["fields"].append({
                "name": "View on Explorer",
                "value": f"[Click here]({explorer_url})",
                "inline": False
            })

        response = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)

        if response.status_code == 204:
            log.info(f"Discord notification sent for {bond_data.get('name')}")
            return True

        log.error(f"Discord webhook failed: {response.status_code} - {response.text}")
        return False

    except Exception as e:
        log.error(f"Failed to send Discord notification: {e}")
        return False


def get_explorer_url(chain, contract_address):
    """
    Generate blockchain explorer URL for a contract address.
    
    Args:
        chain (str): Blockchain name
        contract_address (str): Contract address
    
    Returns:
        str: Explorer URL or empty string if not supported
    """
    explorers = {
        'ETH': f'https://etherscan.io/address/{contract_address}',
        'BNB': f'https://bscscan.com/address/{contract_address}',
        'POL': f'https://polygonscan.com/address/{contract_address}',
        'ARB': f'https://arbiscan.io/address/{contract_address}',
        'BAS': f'https://basescan.org/address/{contract_address}',
        'SOL': f'https://solscan.io/account/{contract_address}',
        'LIN': f'https://lineascan.build/address/{contract_address}',
    }
    return explorers.get(chain, '')


def send_test_notification():
    """
    Send a test notification to verify Discord webhook configuration.
    
    Returns:
        bool: True if sent successfully
    """
    test_data = {
        'name': 'Test Bond',
        'symbol': 'TEST',
        'chain': 'SOL',
        'bonus': 25.50,
        'bond_price_usd': 1.2345,
        'max_buy': 5000.00,
        'contract_address': '0x1234567890abcdef1234567890abcdef12345678'
    }
    return send_discord_notification(test_data)