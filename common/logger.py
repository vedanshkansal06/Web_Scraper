import logging
import sys
from pathlib import Path

Path("logs").mkdir(exist_ok=True)

logger = logging.getLogger("hsn_scraper")
logger.setLevel(logging.INFO)

formatter = logging.Formatter(fmt = "[%(asctime)s] - [%(levelname)s] - [%(filename)s] - [%(message)s]", datefmt = "%Y-%m-%d %H:%M:%S")

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler("logs/scraper.log")
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.WARNING)

logger.addHandler(console_handler)
logger.addHandler(file_handler)