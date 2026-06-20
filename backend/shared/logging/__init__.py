"""Structured logging package.

Exposes the get_logger factory and configure_logging initialiser.
All application modules use get_logger(__name__) to obtain their logger.

Dependency rule: shared/logging imports only from config/ and stdlib.
"""

from shared.logging.logger import configure_logging, get_logger

__all__ = ["configure_logging", "get_logger"]
