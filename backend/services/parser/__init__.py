"""Parser service package.

Exports ParserService as the single entry point for Tree-sitter parsing
and PCR assembly.
"""

from services.parser.parser_service import ParserService

__all__ = ["ParserService"]
