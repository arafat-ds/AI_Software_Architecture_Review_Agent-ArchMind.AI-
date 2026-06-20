"""Security Agent service package.

Exports SecurityService as the single entry point for rule-engine
signal classification and LLM-generated narrative production.
"""

from services.security_agent.security_service import SecurityService

__all__ = ["SecurityService"]
