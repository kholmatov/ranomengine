"""
RanomMappingStudio - Visual DOM-to-Goal AI Assistant

Provides visual AI-powered tools for creating and managing DOM mapping configurations.
Users can visually select DOM elements, get AI suggestions, and create reusable mappings.
"""

from .services.ai_suggester import AISuggester
from .services.mapper import StudioMapper
from .services.comparator import ResultComparator

__version__ = "1.0.0"
__all__ = ["AISuggester", "StudioMapper", "ResultComparator"] 