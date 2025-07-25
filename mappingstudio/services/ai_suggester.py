#!/usr/bin/env python3
"""
RanomMappingStudio - AI Suggester Service

AI-powered service that analyzes HTML content and suggests CSS selectors
and XPath expressions for extracting goal.json fields from car listing pages.
"""

import json
import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from bs4 import BeautifulSoup
from lxml import html

from config import config
from ai.goal_extractor import AIGoalExtractor

logger = logging.getLogger(__name__)


@dataclass
class SelectorSuggestion:
    """AI suggestion for a field selector"""
    field_name: str
    selector: str
    selector_type: str  # 'css' or 'xpath'
    confidence: float
    extracted_value: Optional[str] = None
    reasoning: Optional[str] = None
    alternatives: List[Dict[str, Any]] = None


@dataclass
class SuggestionResult:
    """Result of AI suggestion analysis"""
    success: bool
    suggestions: List[SelectorSuggestion]
    coverage: float  # Percentage of fields with suggestions
    processing_time: float
    error: Optional[str] = None
    ai_analysis: Optional[Dict[str, Any]] = None


class AISuggester:
    """
    AI-powered DOM selector suggestion service
    
    Analyzes HTML content and suggests CSS/XPath selectors for
    extracting structured vehicle data fields.
    """
    
    def __init__(self):
        """Initialize AI suggester with goal field definitions"""
        self.ai_extractor = AIGoalExtractor()
        
        # Define the target goal.json schema fields
        self.goal_fields = {
            # Core vehicle info
            "vin": {
                "description": "Vehicle Identification Number (17 characters)",
                "type": "string",
                "pattern": r"[A-HJ-NPR-Z0-9]{17}",
                "keywords": ["vin", "vehicle identification"]
            },
            "year": {
                "description": "Vehicle year (4 digits)",
                "type": "integer",
                "pattern": r"(19|20)\d{2}",
                "keywords": ["year", "model year"]
            },
            "make": {
                "description": "Vehicle manufacturer",
                "type": "string",
                "keywords": ["make", "brand", "manufacturer"]
            },
            "model": {
                "description": "Vehicle model name",
                "type": "string", 
                "keywords": ["model", "series"]
            },
            "trim": {
                "description": "Vehicle trim level",
                "type": "string",
                "keywords": ["trim", "package", "edition"]
            },
            
            # Pricing & details
            "price": {
                "description": "Vehicle price in dollars",
                "type": "integer",
                "pattern": r"\$?[\d,]+",
                "keywords": ["price", "cost", "msrp", "asking"]
            },
            "mileage": {
                "description": "Vehicle mileage in miles",
                "type": "integer",
                "pattern": r"[\d,]+\s*mi",
                "keywords": ["mileage", "miles", "odometer"]
            },
            "color": {
                "description": "Vehicle exterior color",
                "type": "string",
                "keywords": ["color", "exterior", "paint"]
            },
            
            # Dealer information
            "dealer_name": {
                "description": "Dealership or seller name",
                "type": "string",
                "keywords": ["dealer", "dealership", "seller"]
            },
            "dealer_phone": {
                "description": "Dealer contact phone number",
                "type": "string",
                "pattern": r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
                "keywords": ["phone", "contact", "call"]
            },
            
            # Additional details
            "features": {
                "description": "List of vehicle features",
                "type": "array",
                "keywords": ["features", "options", "equipment"]
            },
            "images": {
                "description": "Vehicle image URLs",
                "type": "array",
                "keywords": ["image", "photo", "picture"]
            },
            "description": {
                "description": "Vehicle description text",
                "type": "string",
                "keywords": ["description", "details", "summary"]
            }
        }
    
    def suggest_selectors(self, html_content: str, url: str = "", 
                         priority_fields: Optional[List[str]] = None) -> SuggestionResult:
        """
        Analyze HTML and suggest selectors for goal.json fields
        
        Args:
            html_content: Raw HTML content to analyze
            url: Source URL for context
            priority_fields: Specific fields to focus on (optional)
            
        Returns:
            SuggestionResult with AI-generated selector suggestions
        """
        import time
        start_time = time.time()
        
        try:
            logger.info(f"AI suggester analyzing HTML ({len(html_content)} chars)")
            
            # Parse HTML for DOM analysis
            soup = BeautifulSoup(html_content, 'html.parser')
            tree = html.fromstring(html_content)
            
            # Determine fields to analyze
            target_fields = priority_fields or list(self.goal_fields.keys())
            
            # Get AI analysis of the page
            ai_analysis = self._get_ai_analysis(html_content, url, target_fields)
            
            # Generate selector suggestions
            suggestions = []
            
            for field_name in target_fields:
                field_info = self.goal_fields.get(field_name, {})
                
                # Get suggestions for this field
                field_suggestions = self._suggest_field_selectors(
                    field_name, field_info, soup, tree, ai_analysis
                )
                
                if field_suggestions:
                    suggestions.extend(field_suggestions)
            
            # Calculate coverage
            suggested_fields = set(s.field_name for s in suggestions)
            coverage = len(suggested_fields) / len(target_fields) if target_fields else 0.0
            
            processing_time = time.time() - start_time
            
            logger.info(f"AI suggester completed: {len(suggestions)} suggestions, "
                       f"{coverage:.1%} coverage, {processing_time:.2f}s")
            
            return SuggestionResult(
                success=True,
                suggestions=suggestions,
                coverage=coverage,
                processing_time=processing_time,
                ai_analysis=ai_analysis
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"AI suggester failed: {e}")
            
            return SuggestionResult(
                success=False,
                suggestions=[],
                coverage=0.0,
                processing_time=processing_time,
                error=str(e)
            )
    
    def _get_ai_analysis(self, html_content: str, url: str, 
                        target_fields: List[str]) -> Optional[Dict[str, Any]]:
        """Get AI analysis of the HTML content"""
        try:
            # Create a focused prompt for selector suggestion
            prompt = self._build_analysis_prompt(html_content, target_fields)
            
            # Use existing AI extractor but with custom prompt
            result = self.ai_extractor.extract_from_html(html_content, url)
            
            if result.success:
                return {
                    "extracted_data": result.extracted_data,
                    "confidence": result.confidence,
                    "ai_suggestions": result.raw_response if hasattr(result, 'raw_response') else None
                }
            
        except Exception as e:
            logger.warning(f"AI analysis failed: {e}")
        
        return None
    
    def _suggest_field_selectors(self, field_name: str, field_info: Dict[str, Any],
                               soup: BeautifulSoup, tree, 
                               ai_analysis: Optional[Dict[str, Any]]) -> List[SelectorSuggestion]:
        """Generate selector suggestions for a specific field"""
        suggestions = []
        
        try:
            # Strategy 1: Pattern-based suggestions
            pattern_suggestions = self._pattern_based_suggestions(
                field_name, field_info, soup, tree
            )
            suggestions.extend(pattern_suggestions)
            
            # Strategy 2: AI-guided suggestions
            if ai_analysis and ai_analysis.get('extracted_data'):
                ai_suggestions = self._ai_guided_suggestions(
                    field_name, field_info, soup, tree, ai_analysis
                )
                suggestions.extend(ai_suggestions)
            
            # Strategy 3: Keyword-based suggestions
            keyword_suggestions = self._keyword_based_suggestions(
                field_name, field_info, soup, tree
            )
            suggestions.extend(keyword_suggestions)
            
            # Remove duplicates and rank by confidence
            suggestions = self._dedupe_and_rank_suggestions(suggestions)
            
            # Limit to top 3 suggestions per field
            return suggestions[:3]
            
        except Exception as e:
            logger.warning(f"Failed to suggest selectors for {field_name}: {e}")
            return []
    
    def _pattern_based_suggestions(self, field_name: str, field_info: Dict[str, Any],
                                 soup: BeautifulSoup, tree) -> List[SelectorSuggestion]:
        """Generate suggestions based on data patterns"""
        suggestions = []
        pattern = field_info.get('pattern')
        
        if not pattern:
            return suggestions
        
        try:
            # Find elements with text matching the pattern
            regex = re.compile(pattern, re.IGNORECASE)
            
            # Search in text content
            for element in soup.find_all(text=regex):
                parent = element.parent
                if parent:
                    # Generate CSS selector
                    css_selector = self._generate_css_selector(parent)
                    if css_selector:
                        suggestions.append(SelectorSuggestion(
                            field_name=field_name,
                            selector=css_selector,
                            selector_type='css',
                            confidence=0.8,
                            extracted_value=element.strip(),
                            reasoning=f"Pattern match for {pattern}"
                        ))
            
        except Exception as e:
            logger.debug(f"Pattern-based suggestion failed for {field_name}: {e}")
        
        return suggestions
    
    def _keyword_based_suggestions(self, field_name: str, field_info: Dict[str, Any],
                                 soup: BeautifulSoup, tree) -> List[SelectorSuggestion]:
        """Generate suggestions based on keywords in element attributes"""
        suggestions = []
        keywords = field_info.get('keywords', [])
        
        if not keywords:
            return suggestions
        
        try:
            for keyword in keywords:
                # Search in class names
                elements = soup.find_all(class_=re.compile(keyword, re.IGNORECASE))
                for element in elements[:2]:  # Limit results
                    css_selector = self._generate_css_selector(element)
                    if css_selector:
                        extracted_value = element.get_text(strip=True)
                        suggestions.append(SelectorSuggestion(
                            field_name=field_name,
                            selector=css_selector,
                            selector_type='css',
                            confidence=0.6,
                            extracted_value=extracted_value[:100] if extracted_value else None,
                            reasoning=f"Keyword '{keyword}' found in class name"
                        ))
                
                # Search in IDs
                elements = soup.find_all(id=re.compile(keyword, re.IGNORECASE))
                for element in elements[:2]:  # Limit results
                    css_selector = f"#{element.get('id')}"
                    extracted_value = element.get_text(strip=True)
                    suggestions.append(SelectorSuggestion(
                        field_name=field_name,
                        selector=css_selector,
                        selector_type='css',
                        confidence=0.7,
                        extracted_value=extracted_value[:100] if extracted_value else None,
                        reasoning=f"Keyword '{keyword}' found in ID"
                    ))
                
                # Search in data attributes
                elements = soup.find_all(attrs={re.compile(f'data.*{keyword}', re.IGNORECASE): True})
                for element in elements[:2]:  # Limit results
                    css_selector = self._generate_css_selector(element)
                    if css_selector:
                        extracted_value = element.get_text(strip=True)
                        suggestions.append(SelectorSuggestion(
                            field_name=field_name,
                            selector=css_selector,
                            selector_type='css',
                            confidence=0.8,
                            extracted_value=extracted_value[:100] if extracted_value else None,
                            reasoning=f"Keyword '{keyword}' found in data attribute"
                        ))
            
        except Exception as e:
            logger.debug(f"Keyword-based suggestion failed for {field_name}: {e}")
        
        return suggestions
    
    def _ai_guided_suggestions(self, field_name: str, field_info: Dict[str, Any],
                             soup: BeautifulSoup, tree, 
                             ai_analysis: Dict[str, Any]) -> List[SelectorSuggestion]:
        """Generate suggestions based on AI analysis results"""
        suggestions = []
        
        try:
            ai_data = ai_analysis.get('extracted_data', {})
            
            # If AI found this field, try to locate the element
            if field_name in ai_data:
                ai_value = str(ai_data[field_name])
                
                # Find elements containing this value
                elements = soup.find_all(text=re.compile(re.escape(ai_value), re.IGNORECASE))
                
                for element in elements[:2]:  # Limit results
                    parent = element.parent
                    if parent:
                        css_selector = self._generate_css_selector(parent)
                        if css_selector:
                            suggestions.append(SelectorSuggestion(
                                field_name=field_name,
                                selector=css_selector,
                                selector_type='css',
                                confidence=0.9,
                                extracted_value=ai_value,
                                reasoning=f"AI identified this value: {ai_value[:50]}"
                            ))
            
        except Exception as e:
            logger.debug(f"AI-guided suggestion failed for {field_name}: {e}")
        
        return suggestions
    
    def _generate_css_selector(self, element) -> Optional[str]:
        """Generate a CSS selector for a BeautifulSoup element"""
        try:
            # Try ID first
            if element.get('id'):
                return f"#{element['id']}"
            
            # Try class names
            if element.get('class'):
                classes = ' '.join([cls for cls in element['class'] if cls])
                if classes:
                    return f".{classes.replace(' ', '.')}"
            
            # Build a path-based selector
            path_parts = []
            current = element
            
            while current and current.name:
                # Get element name
                part = current.name
                
                # Add class if available
                if current.get('class'):
                    classes = '.'.join([cls for cls in current['class'] if cls])
                    if classes:
                        part += f".{classes}"
                
                path_parts.append(part)
                current = current.parent
                
                # Limit depth
                if len(path_parts) >= 4:
                    break
            
            if path_parts:
                return ' > '.join(reversed(path_parts))
                
        except Exception as e:
            logger.debug(f"CSS selector generation failed: {e}")
        
        return None
    
    def _dedupe_and_rank_suggestions(self, suggestions: List[SelectorSuggestion]) -> List[SelectorSuggestion]:
        """Remove duplicates and rank suggestions by confidence"""
        # Remove duplicates based on selector
        seen_selectors = set()
        unique_suggestions = []
        
        for suggestion in suggestions:
            selector_key = f"{suggestion.selector}:{suggestion.selector_type}"
            if selector_key not in seen_selectors:
                seen_selectors.add(selector_key)
                unique_suggestions.append(suggestion)
        
        # Sort by confidence (highest first)
        unique_suggestions.sort(key=lambda s: s.confidence, reverse=True)
        
        return unique_suggestions
    
    def _build_analysis_prompt(self, html_content: str, target_fields: List[str]) -> str:
        """Build AI prompt for HTML analysis"""
        # Truncate HTML for prompt (AI models have token limits)
        max_html_length = 5000
        truncated_html = html_content[:max_html_length] + "..." if len(html_content) > max_html_length else html_content
        
        field_descriptions = {field: self.goal_fields[field]['description'] 
                            for field in target_fields if field in self.goal_fields}
        
        return f"""
Analyze this HTML content from a car listing page and identify potential DOM selectors for these fields:

Fields to find:
{json.dumps(field_descriptions, indent=2)}

HTML Content:
{truncated_html}

Please identify the most likely CSS selectors or XPath expressions that would extract each field.
Focus on finding reliable, specific selectors that won't break easily.
"""
    
    def validate_suggestion(self, suggestion: SelectorSuggestion, html_content: str) -> Tuple[bool, Optional[str]]:
        """Validate a suggestion by testing it against HTML content"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            if suggestion.selector_type == 'css':
                elements = soup.select(suggestion.selector)
            else:  # xpath
                tree = html.fromstring(html_content)
                elements = tree.xpath(suggestion.selector)
            
            if elements:
                # Extract text content
                if hasattr(elements[0], 'get_text'):
                    extracted_value = elements[0].get_text(strip=True)
                else:
                    extracted_value = str(elements[0]).strip()
                
                return True, extracted_value
            else:
                return False, None
                
        except Exception as e:
            logger.debug(f"Suggestion validation failed: {e}")
            return False, None
    
    def get_field_schema(self) -> Dict[str, Any]:
        """Get the complete goal.json field schema"""
        return self.goal_fields.copy()
    
    def suggest_for_url(self, url: str, priority_fields: Optional[List[str]] = None) -> SuggestionResult:
        """Convenience method to fetch URL and generate suggestions"""
        try:
            from services.dom_fetcher import DOMFetcherService
            
            with DOMFetcherService() as fetcher:
                fetch_result = fetcher.fetch_page(url)
                
                if not fetch_result.success:
                    return SuggestionResult(
                        success=False,
                        suggestions=[],
                        coverage=0.0,
                        processing_time=0.0,
                        error=f"Failed to fetch URL: {fetch_result.error}"
                    )
                
                return self.suggest_selectors(fetch_result.html, url, priority_fields)
                
        except Exception as e:
            return SuggestionResult(
                success=False,
                suggestions=[],
                coverage=0.0,
                processing_time=0.0,
                error=f"URL processing failed: {str(e)}"
            ) 