"""
Database operations for bond notification system.
Handles connection, table creation, bond sync, and history storage.
"""

import mysql.connector
import gc
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import requests
from config import ID_CHAIN_MAP
from logging_setup import log

load_dotenv()


def get_db_config():
    """
    Get database configuration from environment variables.
    
    Returns:
        dict: Database connection parameters
    """
    env = os.getenv("ENV", "local")

    if env == "server":
        db_config = {
            "host": os.getenv("SERVER_DB_HOST"),
            "user": os.getenv("SERVER_DB_USER"),
            "password": os.getenv("SERVER_DB_PASS"),
            "database": os.getenv("SERVER_DB_NAME"),
            "port": int(os.getenv("SERVER_DB_PORT", 3307)),
            "ssl_disabled": os.getenv("SERVER_DB_SSL_DISABLED", "False").lower() == "False"
        }
    else:
        db_config = {
            "host": os.getenv("LOCAL_DB_HOST"),
            "user": os.getenv("LOCAL_DB_USER"),
            "password": os.getenv("LOCAL_DB_PASS"),
            "database": os.getenv("LOCAL_DB_NAME"),
            "port": int(os.getenv("LOCAL_DB_PORT", 3306)),
            "ssl_disabled": os.getenv("LOCAL_DB_SSL_DISABLED", "True").lower() == "True"
        }

    return db_config


def get_connection():
    """
    Establish MySQL database connection.
    
    Returns:
        mysql.connector.connection: Database connection object
    """
    db_config = get_db_config()
    if db_config:
        return mysql.connector.connect(**db_config)
    return None


def create_database_and_table():
    """
    Create database and required tables if they don't exist.
    Tables: bond_history, list_bond_contract_notify, token_info_cache
    """
    db_config = get_db_config()
    temp_config = db_config.copy()
    temp_config.pop("database")

    try:
        connection = mysql.connector.connect(**temp_config)
        cursor = connection.cursor()

        # Create database if not exists
        cursor.execute("SHOW DATABASES")
        databases = [db[0] for db in cursor.fetchall()]

        if db_config['database'] in databases:
            print(f"Database {db_config['database']} already exists.")
        else:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['database']}")
            print(f"Database {db_config['database']} newly created")

        del databases

        connection.database = db_config['database']

        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]

        # Create bond_history table
        if "bond_history" in tables:
            print("Table bond_history already exists.")
        else:
            create_table_query = """
                CREATE TABLE IF NOT EXISTS bond_history(
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    bond_name VARCHAR(255) NOT NULL,
                    bond_chain VARCHAR(50) NOT NULL,
                    contract_address VARCHAR(255) NOT NULL,
                    date_time DATETIME NOT NULL,
                    min_bonus DECIMAL(10, 2) NOT NULL,
                    max_bonus DECIMAL(10, 2) NOT NULL,
                    min_price DECIMAL(18, 2) NOT NULL,
                    max_price DECIMAL(18, 2) NOT NULL,
                    max_buy DECIMAL(18, 2) NOT NULL
                ) ENGINE=InnoDB;
            """
            cursor.execute(create_table_query)
            print("Table bond_history newly created")

        # Create list_bond_contract_notify table
        if "list_bond_contract_notify" in tables:
            print("Table list_bond_contract_notify already exists.")
        else:
            create_table_query = """
                CREATE TABLE IF NOT EXISTS list_bond_contract_notify (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    chain VARCHAR(10) NOT NULL,
                    contract_address VARCHAR(100) NOT NULL UNIQUE,
                    token_symbol VARCHAR(20) NOT NULL,
                    status ENUM('active', 'sold') NOT NULL DEFAULT 'active',
                    notify_threshold DECIMAL(5,2) DEFAULT 10.00
                );
            """
            cursor.execute(create_table_query)
            print("Table list_bond_contract_notify newly created")

        # Create token_info_cache table
        if "token_info_cache" in tables:
            print("Table token_info_cache already exists.")
        else:
            create_token_table = """
                CREATE TABLE IF NOT EXISTS token_info_cache (
                    chain VARCHAR(32) NOT NULL,
                    token_address VARCHAR(42) NOT NULL,
                    decimals INT,
                    symbol VARCHAR(32),
                    updated_at DATETIME,
                    PRIMARY KEY (chain, token_address)
                ) ENGINE=InnoDB;
            """
            cursor.execute(create_token_table)
            print("Table token_info_cache newly created")

        del tables
        connection.commit()

    except mysql.connector.Error as e:
        print(f"Error creating database/table: {e}")

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

    gc.collect()


def fetch_bond_data(chain_name):
    """
    Fetch bond data from database by chain type.
    
    Args:
        chain_name (str): 'SOL' or 'EVM'
    
    Returns:
        list: List of bond records
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        if chain_name == "SOL":
            query = "SELECT * FROM list_bond_contract_notify WHERE chain = %s"
            cursor.execute(query, ("SOL",))

        elif chain_name == "EVM":
            evm_chains = ("BNB", "ETH", "POL", "ARB", "BAS", "UNI", "BER", "SON", "LIN", "HYPER")
            placeholders = ', '.join(['%s'] * len(evm_chains))
            query = f"SELECT * FROM list_bond_contract_notify WHERE chain IN ({placeholders})"
            cursor.execute(query, evm_chains)

        else:
            print(f"Unsupported chain group: {chain_name}")
            return []

        results = cursor.fetchall()
        return results

    except mysql.connector.Error as e:
        print(f"Error fetching bond data: {e}")
        return []

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


def fetch_and_update_bonds():
    url = "https://realtime-api.ape.bond/bonds"
    conn = None
    cursor = None

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        bond_data = response.json()

        bonds_list = bond_data.get('bonds', [])

        conn = get_connection()
        cursor = conn.cursor()

        api_contract_addresses = set()
        supported_chains = set()

        for bond in bonds_list:
            is_active = not bond.get('soldOut', True)
            status = 'active' if is_active else 'sold'

            if status != 'active':
                continue

            # ===== SỬA PHẦN NÀY =====
            # Lấy chainId từ cấu trúc mới
            chain_id = bond.get('chainId')
            
            # Nếu không có chainId, thử lấy từ index hoặc các field khác
            if chain_id is None:
                # Thử lấy từ billAddress (nếu có)
                bill_address = bond.get('billAddress', '')
                # Hoặc có thể hardcode cho SOL
                # SOL chainId là 10143
                pass
            
            chain = ID_CHAIN_MAP.get(chain_id)

            if chain is None:
                # Nếu chain_id không có trong map, thử kiểm tra đặc biệt
                if chain_id == 10143:
                    chain = "SOL"
                else:
                    log.warning(f"Unknown chain ID: {chain_id}")
                    continue

            if chain_id == 10143:
                continue

            supported_chains.add(chain)

            contract_address = bond.get('billAddress')
            token_symbol = bond.get('payoutTokenName', '')

            if not contract_address:
                continue

            contract_address_lower = contract_address.lower()
            api_contract_addresses.add(contract_address_lower)

            query = """
                INSERT INTO list_bond_contract_notify (chain, contract_address, token_symbol, status)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    chain = VALUES(chain),
                    token_symbol = VALUES(token_symbol),
                    status = VALUES(status),
                    updated_at = CURRENT_TIMESTAMP
            """
            value = (chain, contract_address_lower, token_symbol, status)
            cursor.execute(query, value)

        # Mark missing bonds as sold
        if supported_chains:
            placeholders = ', '.join(['%s'] * len(supported_chains))
            query = f"SELECT LOWER(contract_address) FROM list_bond_contract_notify WHERE status = 'active' AND chain IN ({placeholders})"
            cursor.execute(query, list(supported_chains))
            db_bonds = set(row[0] for row in cursor.fetchall())

            missing_bonds = db_bonds - api_contract_addresses
            if missing_bonds:
                log.info(f"Found {len(missing_bonds)} bonds to mark as sold for chains {supported_chains}")
                for old_contract in missing_bonds:
                    cursor.execute("""
                        UPDATE list_bond_contract_notify
                        SET status = 'sold', updated_at = CURRENT_TIMESTAMP
                        WHERE LOWER(contract_address) = %s
                    """, (old_contract,))

        conn.commit()
        log.info("Successfully updated bonds from API.")

    except mysql.connector.Error as e:
        if conn:
            conn.rollback()
        log.error(f"MySQL error in fetch_and_update_bonds: {e}")
    except requests.RequestException as e:
        log.error(f"API request error in fetch_and_update_bonds: {e}")
    except Exception as e:
        if conn:
            conn.rollback()
        log.error(f"Unexpected error in fetch_and_update_bonds: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()