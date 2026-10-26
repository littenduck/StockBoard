import logging

from stockboard_backend import run_log

# The tests exercise fetch code that writes timing lines; keep them out of the real data/logs/stockboard.log.
for handler in list(run_log.run_logger.handlers):
    if isinstance(handler, logging.FileHandler):
        run_log.run_logger.removeHandler(handler)
