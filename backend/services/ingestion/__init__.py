"""Ingestion service package.

Exports IngestionService as the single entry point for repository cloning
and manifest construction.
"""

from services.ingestion.ingestion_service import IngestionService

__all__ = ["IngestionService"]
