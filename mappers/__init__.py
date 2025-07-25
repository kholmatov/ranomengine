"""
RanomGoalMap - Universal DOM-to-Goal Mapping Engine

Provides declarative DOM mapping for precise goal.json extraction
from car listing pages using CSS selectors and XPath expressions.
"""

from .goal_mapper import GoalMapper, MappingResult

__version__ = "1.0.0"
__all__ = ["GoalMapper", "MappingResult"] 