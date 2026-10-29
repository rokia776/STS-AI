"""
Central logging configuration for the assignment.
"""
import logging

def configure_logging() -> None:
    """Configure timestamped logging to application.log."""
    logging.basicConfig(
        filename="application.log",
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        encoding="utf-8",
        force=True,
    )
