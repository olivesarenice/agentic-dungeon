"""
Logging configuration for the game using loguru.
Replaces print statements with proper logging.
"""

from loguru import logger

# Configure loguru with custom format
logger.remove()  # Remove default handler
logger.add(
    sink=lambda msg: print(msg, end=""),  # Print to stdout
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
)

# Export logger for use throughout the application
__all__ = ["logger"]
