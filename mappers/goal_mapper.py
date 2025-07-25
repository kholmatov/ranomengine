#!/usr/bin/env python3
"""
RanomGoalMap - Core DOM Mapping Engine

Provides deterministic extraction of goal.json data from car listing pages
using declarative CSS selector and XPath mappings.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass

from bs4 import BeautifulSoup
from lxml import html, etree
import parsel

from models import VehicleData

logger = logging.getLogger(__name__)


@dataclass
class MappingResult:
    """Result of DOM mapping operation"""
    success: bool
    extracted_data: Dict[str, Any]
    mapping_used: str
    fields_mapped: int
    fields_total: int
    confidence: float
    errors: List[str]
    fallback_needed: bool


class GoalMapper:
    """
    Universal DOM-to-Goal mapping engine
    
    Uses declarative JSON configurations to extract structured data
    from car listing pages via CSS selectors and XPath expressions.
    """
    
    def __init__(self, mappings_dir: Optional[str] = None):
        """Initialize mapper with mappings directory"""
        if mappings_dir is None:
            mappings_dir = Path(__file__).parent / "mappings"
        
        self.mappings_dir = Path(mappings_dir)
        self.loaded_mappings = {}
        self._load_all_mappings()
    
    def _load_all_mappings(self):
        """Load all mapping configurations from directory"""
        if not self.mappings_dir.exists():
            logger.warning(f"Mappings directory not found: {self.mappings_dir}")
            return
        
        for mapping_file in self.mappings_dir.glob("*.json"):
            site_id = mapping_file.stem
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    mapping_config = json.load(f)
                    self.loaded_mappings[site_id] = mapping_config
                    logger.debug(f"Loaded mapping for site: {site_id}")
            except Exception as e:
                logger.error(f"Failed to load mapping {mapping_file}: {e}")
    
    def get_available_sites(self) -> List[str]:
        """Get list of available site mappings"""
        return list(self.loaded_mappings.keys())
    
    def validate_mapping(self, site_id: str) -> Dict[str, Any]:
        """
        Validate a mapping configuration
        
        Returns validation result with any issues found
        """
        if site_id not in self.loaded_mappings:
            return {
                "valid": False,
                "errors": [f"Mapping not found for site: {site_id}"]
            }
        
        mapping = self.loaded_mappings[site_id]
        errors = []
        warnings = []
        
        # Check required fields
        required_fields = ["vin", "goal"]
        for field in required_fields:
            if field not in mapping:
                errors.append(f"Missing required field: {field}")
        
        # Validate selector syntax
        for field, selector_rule in mapping.items():
            if field.startswith('_'):  # Skip metadata fields
                continue
                
            # Handle both single selectors and lists of selectors
            selectors = selector_rule if isinstance(selector_rule, list) else [selector_rule]
            
            for selector in selectors:
                if isinstance(selector, str) and selector.startswith(('/', '.', '#', '[', '//')):
                    try:
                        if selector.startswith('//') or selector.startswith('/'):
                            # XPath validation
                            etree.XPath(selector)
                        else:
                            # CSS selector validation - basic validation
                            if not selector.replace('.', '').replace('#', '').replace('[', '').replace(']', '').replace(' ', '').replace('>', '').replace('~', '').replace('+', ''):
                                continue  # Skip empty selectors after cleanup
                    except Exception as e:
                        errors.append(f"Invalid selector for {field}: {selector} - {e}")
        
        # Check for common issues
        if "price" in mapping:
            price_rule = mapping["price"]
            price_selectors = price_rule if isinstance(price_rule, list) else [price_rule]
            
            price_has_keyword = False
            for selector in price_selectors:
                if isinstance(selector, str) and any(keyword in selector.lower() for keyword in ["price", "cost", "msrp"]):
                    price_has_keyword = True
                    break
            
            if not price_has_keyword:
                warnings.append("Price selector might not target price element")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "fields_count": len(mapping)
        }
    
    def extract_from_html(self, html_content: str, site_id: str, url: str = "") -> MappingResult:
        """
        Extract goal data from HTML using mapping configuration
        
        Args:
            html_content: Raw HTML content
            site_id: Site identifier for mapping selection
            url: Original URL (for context)
            
        Returns:
            MappingResult with extracted data and metadata
        """
        if site_id not in self.loaded_mappings:
            return MappingResult(
                success=False,
                extracted_data={},
                mapping_used=site_id,
                fields_mapped=0,
                fields_total=0,
                confidence=0.0,
                errors=[f"No mapping found for site: {site_id}"],
                fallback_needed=True
            )
        
        mapping = self.loaded_mappings[site_id]
        extracted_data = {}
        errors = []
        fields_mapped = 0
        
        try:
            # Parse HTML with multiple parsers for flexibility
            soup = BeautifulSoup(html_content, 'html.parser')
            tree = html.fromstring(html_content)
            selector = parsel.Selector(text=html_content)
            
            # Process each mapping field
            for field, rule in mapping.items():
                try:
                    value = self._extract_field_value(rule, soup, tree, selector, field)
                    if value is not None:
                        # Handle nested fields (e.g., "dealer.name")
                        self._set_nested_value(extracted_data, field, value)
                        fields_mapped += 1
                        logger.debug(f"Mapped {field}: {value}")
                except Exception as e:
                    error_msg = f"Failed to extract {field}: {e}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
            
            # Calculate confidence based on successful mappings
            fields_total = len(mapping)
            confidence = fields_mapped / fields_total if fields_total > 0 else 0.0
            
            # Determine if fallback is needed
            fallback_needed = confidence < 0.7 or fields_mapped < 3
            
            return MappingResult(
                success=fields_mapped > 0,
                extracted_data=extracted_data,
                mapping_used=site_id,
                fields_mapped=fields_mapped,
                fields_total=fields_total,
                confidence=confidence,
                errors=errors,
                fallback_needed=fallback_needed
            )
            
        except Exception as e:
            return MappingResult(
                success=False,
                extracted_data={},
                mapping_used=site_id,
                fields_mapped=0,
                fields_total=len(mapping),
                confidence=0.0,
                errors=[f"HTML parsing failed: {e}"],
                fallback_needed=True
            )
    
    def _extract_field_value(self, rule: Union[str, Dict], soup: BeautifulSoup, 
                           tree, selector: parsel.Selector, field: str) -> Any:
        """Extract value using the mapping rule"""
        
        # Handle static string values
        if isinstance(rule, str) and not rule.startswith(('/', '.', '#', '[', '//')):
            return rule
        
        # Handle complex rules (future enhancement)
        if isinstance(rule, dict):
            return self._extract_complex_rule(rule, soup, tree, selector, field)
        
        # Handle selector rules
        selector_rule = rule
        
        try:
            # Try XPath first
            if selector_rule.startswith('//') or selector_rule.startswith('/'):
                result = self._extract_xpath(selector_rule, tree)
                if result:
                    return result
            
            # Try CSS selector
            result = self._extract_css(selector_rule, selector)
            if result:
                return result
            
            # Try BeautifulSoup as fallback
            result = self._extract_soup(selector_rule, soup)
            if result:
                return result
                
        except Exception as e:
            logger.debug(f"Extraction failed for {field} with rule {selector_rule}: {e}")
        
        return None
    
    def _extract_xpath(self, xpath: str, tree) -> Optional[Union[str, List[str]]]:
        """Extract using XPath"""
        try:
            result = tree.xpath(xpath)
            
            if not result:
                return None
            
            # Handle different result types
            if len(result) == 1:
                return self._clean_text(str(result[0]))
            else:
                return [self._clean_text(str(item)) for item in result]
                
        except Exception:
            return None
    
    def _extract_css(self, css_selector: str, selector: parsel.Selector) -> Optional[Union[str, List[str]]]:
        """Extract using CSS selector"""
        try:
            result = selector.css(css_selector).getall()
            
            if not result:
                return None
            
            if len(result) == 1:
                return self._clean_text(result[0])
            else:
                return [self._clean_text(item) for item in result]
                
        except Exception:
            return None
    
    def _extract_soup(self, selector_rule: str, soup: BeautifulSoup) -> Optional[str]:
        """Extract using BeautifulSoup (fallback)"""
        try:
            # Simple CSS selector support
            if selector_rule.startswith('.'):
                element = soup.find(class_=selector_rule[1:])
            elif selector_rule.startswith('#'):
                element = soup.find(id=selector_rule[1:])
            else:
                element = soup.select_one(selector_rule)
            
            if element:
                return self._clean_text(element.get_text(strip=True))
                
        except Exception:
            pass
        
        return None
    
    def _extract_complex_rule(self, rule: Dict, soup: BeautifulSoup, 
                            tree, selector: parsel.Selector, field: str) -> Any:
        """Handle complex extraction rules (future enhancement)"""
        # Placeholder for advanced rule processing
        # Could support: transformations, regex, multiple selectors, etc.
        return None
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        if not text:
            return ""
        
        # Remove HTML tags if present
        text = re.sub(r'<[^>]+>', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Handle price formatting
        if '$' in text or 'price' in text.lower():
            # Extract numeric price
            price_match = re.search(r'\$?([\d,]+)', text.replace(',', ''))
            if price_match:
                try:
                    return int(price_match.group(1).replace(',', ''))
                except ValueError:
                    pass
        
        return text
    
    def _set_nested_value(self, data: Dict, key: str, value: Any):
        """Set nested dictionary value (e.g., 'dealer.name' -> data['dealer']['name'])"""
        if '.' not in key:
            data[key] = value
            return
        
        parts = key.split('.')
        current = data
        
        # Navigate to parent object
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Set final value
        current[parts[-1]] = value
    
    def to_vehicle_data(self, extracted_data: Dict[str, Any]) -> Optional[VehicleData]:
        """Convert extracted data to VehicleData model"""
        try:
            # Create VehicleData with available fields
            vehicle_data = VehicleData(
                vin=extracted_data.get('vin'),
                year=extracted_data.get('year'),
                make=extracted_data.get('make'),
                model=extracted_data.get('model'),
                trim=extracted_data.get('trim'),
                color=extracted_data.get('color'),
                price=extracted_data.get('price'),
                mileage=extracted_data.get('mileage'),
                dealer_name=extracted_data.get('dealer', {}).get('name') if 'dealer' in extracted_data else extracted_data.get('dealer_name'),
                dealer_phone=extracted_data.get('dealer', {}).get('phone') if 'dealer' in extracted_data else extracted_data.get('dealer_phone'),
                features=extracted_data.get('features', []),
                images=extracted_data.get('images', []),
                description=extracted_data.get('description'),
                url=extracted_data.get('url')
            )
            
            return vehicle_data
            
        except Exception as e:
            logger.error(f"Failed to convert to VehicleData: {e}")
            return None
    
    def get_mapping_info(self, site_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific mapping"""
        if site_id not in self.loaded_mappings:
            return None
        
        mapping = self.loaded_mappings[site_id]
        validation = self.validate_mapping(site_id)
        
        return {
            "site_id": site_id,
            "fields": list(mapping.keys()),
            "field_count": len(mapping),
            "validation": validation,
            "sample_selectors": {k: v for k, v in list(mapping.items())[:3]}
        } 