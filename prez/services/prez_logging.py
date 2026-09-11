import logging
import sys
from datetime import datetime
from pathlib import Path

from prez.services.timing_csv import ensure_timing_csv_header


def setup_logger(settings):
    # create logger
    logger = logging.getLogger("prez")
    logger.setLevel(settings.log_level)

    # create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # create console handler and set level to debug
    handlers = []
    if settings.log_output == "file" or settings.log_output == "both":
        logfile = Path(
            f"../logs/{datetime.now().replace(microsecond=0).isoformat()}.log"
        )
        logfile.parent.mkdir(parents=True, exist_ok=True)
        logfile.touch(exist_ok=True)
        file_handler = logging.FileHandler(filename=logfile)
        file_handler.setLevel(5)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    if settings.log_output == "stdout" or settings.log_output == "both":
        stdout_handler = logging.StreamHandler(stream=sys.stdout)
        stdout_handler.setLevel(5)
        stdout_handler.setFormatter(formatter)
        handlers.append(stdout_handler)

    # add ch to logger
    logger.handlers = handlers

    timing_logger = logging.getLogger("prez.timing")
    timing_logger.setLevel(logging.INFO)
    timing_logger.propagate = False
    timing_logger.handlers = []
    if settings.timing_csv_enabled:
        ensure_timing_csv_header(settings.timing_csv_path)
        timing_handler = logging.FileHandler(filename=settings.timing_csv_path)
        timing_handler.setLevel(logging.INFO)
        timing_handler.setFormatter(logging.Formatter("%(message)s"))
        timing_logger.handlers = [timing_handler]
