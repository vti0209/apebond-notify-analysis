import mysql.connector
import gc
from datetime import datetime,timedelta
import os
from dotenv import load_dotenv
import requests
from config import ID_CHAIN_MAP
from logging_setup import log

load_dotenv()

def get_db_config():
    env = os.getenv("ENV")

    if env == "local":
        DB_CONFIG = {
            "host": os.getenv("SERVER_DB_HOST"),
            "user": os.getenv("SERVER_DB_USER"),
            "password": os.getenv("SERVER_DB_PASS"),
            "database": os.getenv("SERVER_DB_NAME"),
            "port": int(os.getenv("SERVER_DB_PORT", 3307)),
            "ssl_disabled": os.getenv("SERVER_DB_SSL_DISABLED", "False").lower() == "False"
        }
    else:
        DB_CONFIG = {
            "host": os.getenv("LOCAL_DB_HOST"),
            "user": os.getenv("LOCAL_DB_USER"),
            "password": os.getenv("LOCAL_DB_PASS"),
            "database": os.getenv("LOCAL_DB_NAME"),
            "port": int(os.getenv("LOCAL_DB_PORT", 3306)),
            "ssl_disabled": os.getenv("LOCAL_DB_SSL_DISABLED", "False").lower() == "False"
        }
        
    return DB_CONFIG

# Connect to MySQL database
def get_connection():
    DB_CONFIG = get_db_config()
    if DB_CONFIG:
        return mysql.connector.connect(**DB_CONFIG)

DB_CONFIG = get_db_config()

# Create database and table if not exist
def create_database_and_table():
    temp_config = DB_CONFIG.copy()
    temp_config.pop("database")

    try:
        connection = mysql.connector.connect(**temp_config)
        cursor = connection.cursor()

        cursor.execute("SHOW DATABASES")
        databases = [db[0] for db in cursor.fetchall()]

        if DB_CONFIG['database'] in databases:
            print(f"Database {DB_CONFIG['database']} already exists.")
        else:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
            print(f"Database {DB_CONFIG['database']} newly created")
        
        # Clear database list after use
        del databases  

        connection.database = DB_CONFIG['database']

        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]

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
        
        # Clear table list after use
        del tables 

        connection.commit()

    except mysql.connector.Error as e:
        error_message_sql = f"Error creating database/table: {e}"
        print(error_message_sql)
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()
    
    gc.collect()

def fetch_bond_data(chain_name):
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

            # Chỉ xử lý bond active
            if status != 'active':
                continue
            
            chain_id = bond.get('chainId')
            chain = ID_CHAIN_MAP.get(chain_id)
            
            if chain is None:
                continue
            
            # Skip specific chain if needed (like 10143 if it's meant to be skipped)
            if chain_id == 10143:
                continue
                
            supported_chains.add(chain)
            
            contract_address = bond.get('billAddress')
            token_symbol = bond.get('payoutTokenName', '')
            
            if not contract_address:
                continue 
            
            # Add to set to track
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

        if supported_chains:
            # Lấy danh sách các bond hiện có trong DB thuộc các chain đã xử lý
            placeholders = ', '.join(['%s'] * len(supported_chains))
            query = f"SELECT LOWER(contract_address) FROM list_bond_contract_notify WHERE status = 'active' AND chain IN ({placeholders})"
            cursor.execute(query, list(supported_chains))
            db_bonds = set(row[0] for row in cursor.fetchall())

            # Tìm các bond không còn trong API → cập nhật trạng thái thành 'sold'
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
        log.info(f"Successfully updated bonds from API.")
    
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