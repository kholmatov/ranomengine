#!/usr/bin/env python3
"""
RanomMappingStudio - Result Comparator Service

Compares DOM mapping results with AI extraction results to provide
side-by-side analysis and help users improve their mappings.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher

from ai.goal_extractor import AIGoalExtractor
from mappingstudio.services.mapper import StudioMapper

logger = logging.getLogger(__name__)


@dataclass
class FieldComparison:
    """Comparison result for a single field"""
    field_name: str
    mapping_value: Optional[Any]
    ai_value: Optional[Any]
    match: bool
    similarity: float  # 0.0 to 1.0
    difference_type: str  # 'missing', 'extra', 'different', 'match'
    suggestion: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class ComparisonResult:
    """Complete comparison between mapping and AI results"""
    success: bool
    overall_similarity: float
    field_comparisons: List[FieldComparison]
    mapping_coverage: float  # Fields found by mapping
    ai_coverage: float  # Fields found by AI
    recommendations: List[str]
    processing_time: float
    error: Optional[str] = None


class ResultComparator:
    """
    Compares mapping extraction results with AI extraction results
    
    Provides detailed field-by-field comparison and suggests improvements
    to mapping configurations based on AI analysis.
    """
    
    def __init__(self):
        """Initialize result comparator"""
        self.ai_extractor = AIGoalExtractor()
        self.studio_mapper = StudioMapper()
    
    def compare_results(self, html_content: str, mapping_config: Dict[str, Any],
                       url: str = "") -> ComparisonResult:
        """
        Compare mapping results with AI extraction
        
        Args:
            html_content: Raw HTML content
            mapping_config: DOM mapping configuration
            url: Source URL for context
            
        Returns:
            ComparisonResult with detailed field-by-field comparison
        """
        import time
        start_time = time.time()
        
        try:
            logger.info("Starting mapping vs AI comparison")
            
            # Get mapping results
            mapping_result = self.studio_mapper.preview_mapping(
                html_content, mapping_config, url
            )
            
            # Get AI results
            ai_result = self.ai_extractor.extract_from_html(html_content, url)
            
            if not ai_result.success:
                return ComparisonResult(
                    success=False,
                    overall_similarity=0.0,
                    field_comparisons=[],
                    mapping_coverage=0.0,
                    ai_coverage=0.0,
                    recommendations=[],
                    processing_time=time.time() - start_time,
                    error=f"AI extraction failed: {ai_result.error}"
                )
            
            # Perform field-by-field comparison
            field_comparisons = self._compare_fields(
                mapping_result.extracted_data,
                ai_result.extracted_data,
                mapping_result.field_results
            )
            
            # Calculate overall metrics
            overall_similarity = self._calculate_overall_similarity(field_comparisons)
            mapping_coverage = self._calculate_coverage(mapping_result.extracted_data)
            ai_coverage = self._calculate_coverage(ai_result.extracted_data)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                field_comparisons, mapping_result, ai_result
            )
            
            processing_time = time.time() - start_time
            
            logger.info(f"Comparison completed: {overall_similarity:.1%} similarity, "
                       f"{len(field_comparisons)} fields, {processing_time:.2f}s")
            
            return ComparisonResult(
                success=True,
                overall_similarity=overall_similarity,
                field_comparisons=field_comparisons,
                mapping_coverage=mapping_coverage,
                ai_coverage=ai_coverage,
                recommendations=recommendations,
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Comparison failed: {e}")
            
            return ComparisonResult(
                success=False,
                overall_similarity=0.0,
                field_comparisons=[],
                mapping_coverage=0.0,
                ai_coverage=0.0,
                recommendations=[],
                processing_time=processing_time,
                error=str(e)
            )
    
    def _compare_fields(self, mapping_data: Dict[str, Any], 
                       ai_data: Dict[str, Any],
                       mapping_field_results: Dict[str, Dict[str, Any]]) -> List[FieldComparison]:
        """Compare individual fields between mapping and AI results"""
        comparisons = []
        
        # Get all unique field names from both results
        all_fields = set(mapping_data.keys()) | set(ai_data.keys())
        
        for field_name in all_fields:
            mapping_value = mapping_data.get(field_name)
            ai_value = ai_data.get(field_name)
            
            # Determine comparison type and similarity
            if mapping_value is None and ai_value is None:
                # Both missing
                continue
            elif mapping_value is None:
                # Missing from mapping
                comparison = FieldComparison(
                    field_name=field_name,
                    mapping_value=None,
                    ai_value=ai_value,
                    match=False,
                    similarity=0.0,
                    difference_type='missing',
                    suggestion=f"Consider adding mapping for '{field_name}': {str(ai_value)[:100]}"
                )
            elif ai_value is None:
                # Missing from AI (mapping found extra field)
                comparison = FieldComparison(
                    field_name=field_name,
                    mapping_value=mapping_value,
                    ai_value=None,
                    match=False,
                    similarity=0.5,  # Partial credit for finding something
                    difference_type='extra',
                    suggestion=f"Mapping found '{field_name}' but AI didn't - verify accuracy"
                )
            else:
                # Both have values - compare them
                similarity = self._calculate_field_similarity(mapping_value, ai_value)
                match = similarity >= 0.9  # 90% similarity threshold
                
                if match:
                    difference_type = 'match'
                    suggestion = None
                else:
                    difference_type = 'different'
                    suggestion = f"Values differ - Mapping: '{str(mapping_value)[:50]}' vs AI: '{str(ai_value)[:50]}'"
                
                comparison = FieldComparison(
                    field_name=field_name,
                    mapping_value=mapping_value,
                    ai_value=ai_value,
                    match=match,
                    similarity=similarity,
                    difference_type=difference_type,
                    suggestion=suggestion
                )
            
            # Add confidence from mapping field results
            if field_name in mapping_field_results:
                field_result = mapping_field_results[field_name]
                if field_result.get('success'):
                    comparison.confidence = 0.8  # Mapping confidence
                else:
                    comparison.confidence = 0.0
            
            comparisons.append(comparison)
        
        # Sort by field importance (VIN, price, etc. first)
        important_fields = ['vin', 'price', 'year', 'make', 'model', 'mileage']
        comparisons.sort(key=lambda c: (
            important_fields.index(c.field_name) if c.field_name in important_fields else 999,
            c.field_name
        ))
        
        return comparisons
    
    def _calculate_field_similarity(self, value1: Any, value2: Any) -> float:
        """Calculate similarity between two field values"""
        try:
            # Handle None values
            if value1 is None and value2 is None:
                return 1.0
            if value1 is None or value2 is None:
                return 0.0
            
            # Convert to strings for comparison
            str1 = str(value1).strip().lower()
            str2 = str(value2).strip().lower()
            
            # Exact match
            if str1 == str2:
                return 1.0
            
            # Handle numeric values
            if self._is_numeric(str1) and self._is_numeric(str2):
                try:
                    num1 = float(str1.replace(',', ''))
                    num2 = float(str2.replace(',', ''))
                    
                    # Calculate percentage difference
                    if num1 == num2:
                        return 1.0
                    elif num1 == 0 or num2 == 0:
                        return 0.0
                    else:
                        diff = abs(num1 - num2) / max(num1, num2)
                        return max(0.0, 1.0 - diff)
                except ValueError:
                    pass
            
            # String similarity using SequenceMatcher
            return SequenceMatcher(None, str1, str2).ratio()
            
        except Exception as e:
            logger.debug(f"Field similarity comparison failed: {e}")
            return 0.0
    
    def _is_numeric(self, value: str) -> bool:
        """Check if a string represents a numeric value"""
        try:
            float(value.replace(',', '').replace('$', ''))
            return True
        except ValueError:
            return False
    
    def _calculate_overall_similarity(self, comparisons: List[FieldComparison]) -> float:
        """Calculate weighted overall similarity score"""
        if not comparisons:
            return 0.0
        
        # Weight important fields more heavily
        field_weights = {
            'vin': 3.0,
            'price': 2.5,
            'year': 2.0,
            'make': 2.0,
            'model': 2.0,
            'mileage': 1.5,
            'color': 1.0,
            'dealer_name': 1.0,
            'dealer_phone': 1.0
        }
        
        total_weighted_score = 0.0
        total_weight = 0.0
        
        for comparison in comparisons:
            weight = field_weights.get(comparison.field_name, 1.0)
            total_weighted_score += comparison.similarity * weight
            total_weight += weight
        
        return total_weighted_score / total_weight if total_weight > 0 else 0.0
    
    def _calculate_coverage(self, data: Dict[str, Any]) -> float:
        """Calculate field coverage percentage"""
        if not data:
            return 0.0
        
        # Define expected fields
        expected_fields = [
            'vin', 'year', 'make', 'model', 'price', 'mileage', 'color',
            'dealer_name', 'dealer_phone', 'features', 'images', 'description'
        ]
        
        found_fields = 0
        for field in expected_fields:
            if field in data and data[field] is not None:
                # Check if it's a meaningful value (not empty string/list)
                value = data[field]
                if isinstance(value, str) and value.strip():
                    found_fields += 1
                elif isinstance(value, (list, dict)) and value:
                    found_fields += 1
                elif isinstance(value, (int, float)) and value != 0:
                    found_fields += 1
        
        return found_fields / len(expected_fields)
    
    def _generate_recommendations(self, comparisons: List[FieldComparison],
                                mapping_result, ai_result) -> List[str]:
        """Generate improvement recommendations based on comparison"""
        recommendations = []
        
        # Analyze missing fields
        missing_fields = [c for c in comparisons if c.difference_type == 'missing']
        if missing_fields:
            recommendations.append(
                f"Consider adding mappings for {len(missing_fields)} missing fields: " +
                ", ".join([f.field_name for f in missing_fields[:5]])
            )
        
        # Analyze mismatched fields
        mismatched_fields = [c for c in comparisons if c.difference_type == 'different']
        if mismatched_fields:
            recommendations.append(
                f"Review {len(mismatched_fields)} fields with different values - " +
                "selectors may need refinement"
            )
        
        # Check mapping errors
        if hasattr(mapping_result, 'errors') and mapping_result.errors:
            recommendations.append(
                f"Fix {len(mapping_result.errors)} mapping errors for better accuracy"
            )
        
        # Performance recommendations
        if mapping_result.confidence < 0.5:
            recommendations.append(
                "Low mapping confidence - consider using AI-suggested selectors"
            )
        
        # Field-specific recommendations
        important_misses = [c for c in missing_fields if c.field_name in ['vin', 'price', 'year', 'make', 'model']]
        if important_misses:
            recommendations.append(
                f"Priority: Add mappings for critical fields: " +
                ", ".join([f.field_name for f in important_misses])
            )
        
        return recommendations[:10]  # Limit to top 10 recommendations
    
    def suggest_improvements(self, comparison_result: ComparisonResult,
                           html_content: str) -> Dict[str, Any]:
        """Generate specific improvement suggestions based on comparison"""
        suggestions = []
        
        try:
            from mappingstudio.services.ai_suggester import AISuggester
            ai_suggester = AISuggester()
            
            # Get AI suggestions for missing/mismatched fields
            problematic_fields = [
                c.field_name for c in comparison_result.field_comparisons
                if c.difference_type in ['missing', 'different'] and c.similarity < 0.7
            ]
            
            if problematic_fields:
                suggestion_result = ai_suggester.suggest_selectors(
                    html_content, priority_fields=problematic_fields
                )
                
                if suggestion_result.success:
                    for suggestion in suggestion_result.suggestions:
                        suggestions.append({
                            "field_name": suggestion.field_name,
                            "current_issue": next(
                                (c.suggestion for c in comparison_result.field_comparisons 
                                 if c.field_name == suggestion.field_name), 
                                "Field needs improvement"
                            ),
                            "suggested_selector": suggestion.selector,
                            "selector_type": suggestion.selector_type,
                            "confidence": suggestion.confidence,
                            "reasoning": suggestion.reasoning,
                            "extracted_preview": suggestion.extracted_value[:100] if suggestion.extracted_value else None
                        })
            
            return {
                "success": True,
                "suggestions": suggestions,
                "total_improvements": len(suggestions)
            }
            
        except Exception as e:
            logger.error(f"Failed to generate improvement suggestions: {e}")
            return {
                "success": False,
                "error": str(e),
                "suggestions": []
            }
    
    def compare_with_ai_only(self, html_content: str, url: str = "") -> Dict[str, Any]:
        """Get AI-only extraction for comparison baseline"""
        try:
            ai_result = self.ai_extractor.extract_from_html(html_content, url)
            
            if ai_result.success:
                return {
                    "success": True,
                    "extracted_data": ai_result.extracted_data,
                    "confidence": ai_result.confidence,
                    "field_count": len(ai_result.extracted_data),
                    "processing_time": getattr(ai_result, 'processing_time', 0.0)
                }
            else:
                return {
                    "success": False,
                    "error": ai_result.error
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            } 