import logging
from logging.handlers import RotatingFileHandler

def setup_logging(environment, logger_name='discord'):
    # Configure the logger
    logger = logging.getLogger(logger_name)
    # Set the logging level based on the environment
    logger.setLevel(logging.DEBUG if environment == 'development' else logging.WARNING)
    logger.propagate = False

    # Formatter to apply to both console and file handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console handler with a logging level based on the environment
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if environment == 'development' else logging.WARNING)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with a rotating file setup
    file_handler = RotatingFileHandler('discordbot.log', maxBytes=1024*1024*5, backupCount=5)
    file_handler.setLevel(logging.DEBUG if environment == 'development' else logging.WARNING)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
