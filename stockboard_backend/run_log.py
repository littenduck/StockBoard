"""A plain log for the person running the app: one line per fetch with its time, and one summary per refresh.

Every line starts with the date and time to the millisecond in the time zone of the machine (the first line of a run says which). Every run appends to data/logs/stockboard.log (2 MB a file, 3 old files kept) and also prints to the console.
Read it with: grep fetch data/logs/stockboard.log | sort -k5 -n -r | head
"""
import logging
import logging.handlers
import os
import time

LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "logs", "stockboard.log")

run_logger = logging.getLogger("stockboard")
if not run_logger.handlers:
    run_logger.setLevel(logging.INFO)
    run_logger.propagate = False
    formatter = logging.Formatter("%(asctime)s.%(msecs)03d %(message)s", "%Y-%m-%d %H:%M:%S")
    try:
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(LOG_FILE_PATH, maxBytes=2_000_000, backupCount=3, encoding="utf8")
        file_handler.setFormatter(formatter)
        run_logger.addHandler(file_handler)
    except OSError:  # a read-only disk must not stop the app; the console line is still there
        pass
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    run_logger.addHandler(console_handler)


run_logger.info("run start pid {} time zone {} {}".format(os.getpid(), time.strftime("%Z"), time.strftime("%z")))


def run_log_write(message: str) -> None:
    run_logger.info(message)
