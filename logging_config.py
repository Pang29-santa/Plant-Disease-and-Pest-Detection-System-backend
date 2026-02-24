import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler

# ANSI Colors
RESET  = "\033[0m"
BOLD   = "\033[1m"
COLORS = {
    "DEBUG":    "\033[36m",   # Cyan
    "INFO":     "\033[32m",   # Green
    "WARNING":  "\033[33m",   # Yellow
    "ERROR":    "\033[31m",   # Red
    "CRITICAL": "\033[35m",   # Magenta
}


class ColorFormatter(logging.Formatter):
    def format(self, record):
        color = COLORS.get(record.levelname, RESET)
        record.levelname = f"{color}{BOLD}{record.levelname:<8}{RESET}"
        return super().format(record)


def setup_logging():
    """Terminal + Daily File logging with colors"""
    # 1. Console Handler (for terminal logs)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColorFormatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    ))

    # 2. File Handler (Rotating log file every midnight)
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "app.log")

    file_handler = TimedRotatingFileHandler(
        filename=log_file_path,
        when="midnight",    # Rotate at midnight
        interval=1,         # Every 1 day
        backupCount=30,     # Keep max 30 days of logs
        encoding="utf-8"
    )
    # The file formatter doesn't need terminal color codes
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)

    # 3. Apply handlers to root logger
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # Uvicorn ใช้ handlers เดียวกัน
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.addHandler(console_handler)
        lg.addHandler(file_handler)
        lg.propagate = False

    # ปิด noisy loggers
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
