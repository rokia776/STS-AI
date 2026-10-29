"""
Demonstration of all five standard Python logging levels.
Run with: python main.py
"""
import logging
from logging_config import configure_logging

def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)

    logger.debug("Debug message: checking the application's internal state.")
    logger.info("Info message: application started successfully.")
    logger.warning("Warning message: configuration value missing; using default.")
    logger.error("Error message: failed to load the optional input file.")
    logger.critical("Critical message: required service is unavailable.")

    print("Logging demo complete. Check application.log for the recorded entries.")

if __name__ == "__main__":
    main()
