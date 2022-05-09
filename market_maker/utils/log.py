import logging
from market_maker.settings import settings

loggers = {}


def setup_custom_logger(name, log_level=settings.LOG_LEVEL):
    if loggers.get(name):
        return loggers[name]

    logger = logging.getLogger(name)
    loggers[name] = logger

    formatter = logging.Formatter(fmt='%(asctime)s - %(message)s')
    formatter_log = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.setLevel(log_level)
    logger.addHandler(handler)

    fh = logging.FileHandler('LOG.log')
    fh.setFormatter(formatter_log)
    fh.setLevel(settings.LOG_LEVEL)
    logger.addHandler(fh)
    return logger
