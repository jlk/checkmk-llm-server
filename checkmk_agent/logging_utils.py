import logging


def setup_logging(log_level: str = "INFO"):
    """
    Set up logging for the application.
    Args:
        log_level (str): Logging level as a string (e.g., 'DEBUG', 'INFO').
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
