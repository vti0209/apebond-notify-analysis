import logging 
import os
import sys
from logging.handlers import TimedRotatingFileHandler

def setup_logger(name, log_file, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.hasHandlers():
        return logger

    # Ensure logs directory exists (go up one level from bond_notify to project root if needed)
    # The current working directory when running this is usually the project root or bond_notify.
    # We will use an absolute or relative path to the project root's logs directory.
    # To be safe, we'll try to put it in the project root's logs folder.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(project_root, os.path.dirname(log_file))
    os.makedirs(log_dir, exist_ok=True)
    
    full_log_path = os.path.join(project_root, log_file)

    # File handler
    file_handler = TimedRotatingFileHandler(full_log_path, when='midnight', interval=1, backupCount=3, encoding='utf-8')
    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    file_handler.setFormatter(formatter)
    
    # Console handler (to keep output visible in terminal/cron output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False 
    return logger

# --- Tạo logger chung cho bond_notify ---
log = setup_logger("BOND_NOTIFY", "logs/bond_notify.log")
