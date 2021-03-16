import logging


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s:%(lineno)d %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
