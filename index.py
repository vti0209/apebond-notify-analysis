import sys
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from process_bond_evm import process_bonds
from process_bond_sol import process_bond_sol
from execute_data import create_database_and_table, fetch_bond_data, get_connection, fetch_and_update_bonds
from config import MIN_BONUS_NOTIFY
import gc
import mysql.connector
from helpers import sleep_until_wakeup, set_bedtime, send_discord_webhook_message
from logging_setup import log

def save_and_notify_top_bonds_by_bonus(bonds_evm, bonds_sol):
    create_database_and_table()
    # Sắp xếp theo max_bonus giảm dần và lấy top 10
    try:
        connnection = get_connection()
        cursor = connnection.cursor()
        bond_results = bonds_evm + bonds_sol
        top_bonds = sorted(bond_results, key=lambda x: x["max_bonus"], reverse=True)[:10]

        bonds_info_tele = ""
        for idx, bond in enumerate(top_bonds, 1):
            threshold = bond.get('notify_threshold', MIN_BONUS_NOTIFY)
            if bond['min_bonus'] >= float(threshold):
                bonds_info_tele += f"{idx}. {bond['chain']} {bond['bond_name']} {bond['min_bonus']:.2f}% ~ {bond['max_bonus']:.2f}%\n"
            # print(f"{idx}. [{bond['chain']}] {bond['bond_name']} | Bonus: {bond['min_bonus']:.2f}% ~ {bond['max_bonus']:.2f}%")

            insert_query = """
                INSERT INTO bond_history (bond_name, bond_chain, contract_address, date_time, min_bonus, max_bonus, min_price, max_price, max_buy)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            try:
                data = (bond['bond_name'], bond['chain'], bond['bond_address'], bond['date_time'], bond['min_bonus'], bond['max_bonus'], bond['min_price'], bond['max_price'], bond['max_buy'])
                cursor.execute(insert_query, data)
            except Exception as e:
                error_message = f"⚠️ *Error happened in save_and_notify_top_bonds_by_bonus:* {str(e)}"
                log.error(error_message)
                
        if bonds_info_tele != "":
            send_discord_webhook_message(bonds_info_tele)
            
        connnection.commit()

    except Exception as e:
        error_message = f"⚠️ *Error happened in save_and_notify_top_bonds_by_bonus:* {str(e)}"
        log.error(error_message.encode('utf-8', 'ignore').decode('utf-8'))

    finally:
        # Close connection database
        if 'cursor' in locals():
            cursor.close()
        if 'connnection' in locals() and connnection.is_connected():
            connnection.close()
            
        for var in ['bond_results', 'top_bonds', 'bonds_info_tele', 'data']:
            if var in locals():
                del locals()[var]
        gc.collect()

if __name__ == "__main__":
    try:
        if set_bedtime():
            sleep_until_wakeup()
        else:
            log.info("Update list bonds to db by api apebond.")
            fetch_and_update_bonds()

            bond_datas_evm = fetch_bond_data("EVM")
            bond_datas_sol = fetch_bond_data("SOL")
            
            bonds_evm = process_bonds(bond_datas_evm)
            bonds_sol = process_bond_sol(bond_datas_sol)
            
            if bonds_evm or bonds_sol:
                save_and_notify_top_bonds_by_bonus(bonds_evm, bonds_sol)
            
    except Exception as e:
        error_message = f"❗ *Fatal error happened:* {str(e)}"
        send_discord_webhook_message(error_message)
        log.error(error_message.encode('utf-8', 'ignore').decode('utf-8'))

