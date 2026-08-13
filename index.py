"""
Entry point for ApeBond notification system.
Fetches bonds, processes EVM and Solana bonds, saves to database, and sends Discord notifications.
"""

import sys
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from process_bond_evm import process_bonds
from process_bond_sol import process_bond_sol
from execute_data import create_database_and_table, fetch_bond_data, fetch_and_update_bonds
from config import MIN_BONUS_NOTIFY
import gc
from helpers import sleep_until_wakeup, set_bedtime, send_discord_webhook_message
from logging_setup import log


def save_and_notify_top_bonds_by_bonus(bonds_evm, bonds_sol):
    """
    Save top bonds to database and send Discord notification.
    
    Args:
        bonds_evm (list): Processed EVM bonds
        bonds_sol (list): Processed Solana bonds
    """
    create_database_and_table()

    try:
        connection = get_connection()
        cursor = connection.cursor()
        bond_results = bonds_evm + bonds_sol

        log.info(f"Total bonds to process: EVM={len(bonds_evm)}, SOL={len(bonds_sol)}, Total={len(bond_results)}")

        if not bond_results:
            log.warning("No bonds to save. Check process_bonds and process_bond_sol.")
            return

        # Sort by max_bonus descending and get top 10
        top_bonds = sorted(bond_results, key=lambda x: x["max_bonus"], reverse=True)[:10]
        log.info(f"Top {len(top_bonds)} bonds: {[b.get('bond_name') for b in top_bonds]}")

        bonds_info_tele = ""
        saved_count = 0

        for idx, bond in enumerate(top_bonds, 1):
            threshold = bond.get('notify_threshold', MIN_BONUS_NOTIFY)

            if bond['min_bonus'] >= float(threshold):
                bonds_info_tele += f"{idx}. {bond['chain']} {bond['bond_name']} {bond['min_bonus']:.2f}% ~ {bond['max_bonus']:.2f}%\n"

            log.info(f"Saving: {bond['bond_name']} | Bonus: {bond['min_bonus']:.2f}% | Address: {bond['bond_address']}")

            insert_query = """
                INSERT INTO bond_history (
                    bond_name, bond_chain, contract_address, date_time,
                    min_bonus, max_bonus, min_price, max_price, max_buy
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            try:
                data = (
                    bond['bond_name'],
                    bond['chain'],
                    bond['bond_address'],
                    bond['date_time'],
                    bond['min_bonus'],
                    bond['max_bonus'],
                    bond['min_price'],
                    bond['max_price'],
                    bond['max_buy']
                )
                cursor.execute(insert_query, data)
                saved_count += 1
                log.info(f"Inserted: {bond['bond_name']}")

            except Exception as e:
                log.error(f"Insert error for {bond.get('bond_name', 'Unknown')}: {e}")

        if bonds_info_tele:
            send_discord_webhook_message(bonds_info_tele)

        connection.commit()
        log.info(f"Successfully saved {saved_count}/{len(top_bonds)} bonds to history")

    except Exception as e:
        log.error(f"Error in save_and_notify_top_bonds_by_bonus: {e}")
        import traceback
        log.error(traceback.format_exc())

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()
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
        error_message = f"Fatal error: {e}"
        send_discord_webhook_message(error_message)
        log.error(error_message)