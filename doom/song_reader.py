import gzip
import orjson

from .utils import logger_init, worker_init

def read_file(path):
    """
    a generator for processing line-delimited json
    one line at a time
    """
    logging.info("opening %s" % path)
    with gzip.open(path, 'rb') as f:
        for line in f:
            yield orjson.loads(line)
