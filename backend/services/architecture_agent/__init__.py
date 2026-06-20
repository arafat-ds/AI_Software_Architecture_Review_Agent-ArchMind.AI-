"""Architecture Agent service package.

Exports ArchitectureService as the single entry point for rule-engine
classification and LLM-generated narrative production.
"""

from services.architecture_agent.architecture_service import ArchitectureService

__all__ = ["ArchitectureService"]
