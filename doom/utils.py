import sys
import logging
import multiprocessing as mp
from logging.handlers import QueueHandler, QueueListener

def logger_init(level=logging.DEBUG):
    # https://stackoverflow.com/questions/641420/how-should-i-log-while-using-multiprocessing-in-python
    q = mp.Queue()
    # this is the handler for all log records
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(levelname)s: %(asctime)s - %(process)s - %(message)s")
    )

    # ql gets records from the queue and sends them to the handler
    ql = QueueListener(q, handler)
    ql.start()

    logger = logging.getLogger()
    logger.setLevel(level)
    # add the handler to the logger so records from this process are handled
    logger.addHandler(handler)

    return ql, q

def worker_init(q):
    # all records from worker processes go to qh and then into q
    qh = QueueHandler(q)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(qh)
