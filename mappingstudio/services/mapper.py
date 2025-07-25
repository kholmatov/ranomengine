#!/usr/bin/env python3
"""
RanomMappingStudio - Studio Mapper Service

Enhanced DOM extraction engine that provides real-time preview capabilities
for the visual mapping studio interface.
"""

import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from bs4 import BeautifulSoup
from lxml import html

from mappers.goal_mapper import GoalMapper, MappingResult
from models import VehicleData

logger = logging.getLogger(__name__)


@dataclass
class PreviewResult:
    """Result of real-time preview extraction"""
    success: bool
    extracted_data: Dict[str, Any]
    field_results: Dict[str, Dict[str, Any]]  # Per-field extraction details
    errors: List[str]
    warnings: List[str]
    processing_time: float
    total_fields: int
    successful_fields: int
    confidence: float


@dataclass
class FieldExtractionResult:
    """Result of extracting a single field"""
    field_name: str
    success: bool
    value: Optional[Any] = None
    selector: Optional[str] = None
    selector_type: Optional[str] = None
    error: Optional[str] = None
    element_html: Optional[str] = None
    element_position: Optional[Dict[str, int]] = None  # For highlighting


class StudioMapper:
    """
    Enhanced DOM mapper for visual mapping studio
    
    Provides real-time preview, field-by-field extraction,
    and detailed error reporting for the studio interface.
    """
    
    def __init__(self):
        """Initialize studio mapper"""
        self.base_mapper = GoalMapper()
    
    def preview_mapping(self, html_content: str, mapping_config: Dict[str, Any], 
                       url: str = "") -> PreviewResult:
        """
        Preview extraction results for visual studio
        
        Args:
            html_content: Raw HTML content
            mapping_config: Mapping configuration with selectors
            url: Source URL for context
            
        Returns:
            PreviewResult with detailed field-by-field results
        """
        start_time = time.time()
        
        try:
            logger.info(f"Studio mapper previewing {len(mapping_config)} field mappings")
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            tree = html.fromstring(html_content)
            
            # Extract each field individually
            field_results = {}
            extracted_data = {}
            errors = []
            warnings = []
            successful_fields = 0
            
            for field_name, field_config in mapping_config.items():
                if field_name.startswith('_'):  # Skip metadata
                    continue
                
                # Extract this field
                field_result = self._extract_single_field(
                    field_name, field_config, soup, tree, html_content
                )
                
                field_results[field_name] = {
                    "success": field_result.success,
                    "value": field_result.value,
                    "selector": field_result.selector,
                    "selector_type": field_result.selector_type,
                    "error": field_result.error,
                    "element_html": field_result.element_html,
                    "element_position": field_result.element_position
                }
                
                if field_result.success and field_result.value is not None:
                    # Handle nested fields (e.g., dealer.name)
                    self._set_nested_value(extracted_data, field_name, field_result.value)
                    successful_fields += 1
                else:
                    if field_result.error:
                        errors.append(f"{field_name}: {field_result.error}")
            
            # Calculate confidence
            total_fields = len([f for f in mapping_config.keys() if not f.startswith('_')])
            confidence = successful_fields / total_fields if total_fields > 0 else 0.0
            
            processing_time = time.time() - start_time
            
            logger.info(f"Studio preview completed: {successful_fields}/{total_fields} fields, "
                       f"confidence {confidence:.1%}, {processing_time:.3f}s")
            
            return PreviewResult(
                success=successful_fields > 0,
                extracted_data=extracted_data,
                field_results=field_results,
                errors=errors,
                warnings=warnings,
                processing_time=processing_time,
                total_fields=total_fields,
                successful_fields=successful_fields,
                confidence=confidence
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Studio preview failed: {e}")
            
            return PreviewResult(
                success=False,
                extracted_data={},
                field_results={},
                errors=[f"Preview failed: {str(e)}"],
                warnings=[],
                processing_time=processing_time,
                total_fields=0,
                successful_fields=0,
                confidence=0.0
            )
    
    def _extract_single_field(self, field_name: str, field_config: Any,
                             soup: BeautifulSoup, tree, 
                             html_content: str) -> FieldExtractionResult:
        """Extract a single field with detailed error reporting"""
        try:
            # Handle static string values
            if isinstance(field_config, str) and not field_config.startswith(('/', '.', '#', '[', '//')):
                return FieldExtractionResult(
                    field_name=field_name,
                    success=True,
                    value=field_config,
                    selector=None,
                    selector_type='static'
                )
            
            # Handle selector-based extraction
            if isinstance(field_config, dict):
                selector = field_config.get('selector', '')
                selector_type = field_config.get('type', 'css')
            else:
                selector = str(field_config)
                # Determine selector type
                if selector.startswith('//') or selector.startswith('/'):
                    selector_type = 'xpath'
                else:
                    selector_type = 'css'
            
            if not selector:
                return FieldExtractionResult(
                    field_name=field_name,
                    success=False,
                    error="No selector provided"
                )
            
            # Extract using appropriate method
            if selector_type == 'xpath':
                return self._extract_xpath_field(field_name, selector, tree, html_content)
            else:
                return self._extract_css_field(field_name, selector, soup, html_content)
                
        except Exception as e:
            return FieldExtractionResult(
                field_name=field_name,
                success=False,
                error=f"Field extraction failed: {str(e)}"
            )
    
    def _extract_css_field(self, field_name: str, selector: str, 
                          soup: BeautifulSoup, html_content: str) -> FieldExtractionResult:
        """Extract field using CSS selector"""
        try:
            elements = soup.select(selector)
            
            if not elements:
                return FieldExtractionResult(
                    field_name=field_name,
                    success=False,
                    selector=selector,
                    selector_type='css',
                    error="No elements found with selector"
                )
            
            element = elements[0]  # Take first match
            
            # Extract value based on element type
            if element.name == 'img':
                value = element.get('src') or element.get('data-src')
            elif element.name == 'a':
                value = element.get('href')
            elif element.get('value'):  # Input elements
                value = element.get('value')
            else:
                value = element.get_text(strip=True)
            
            # Clean the value
            if value:
                value = self._clean_extracted_value(value, field_name)
            
            # Get element position for highlighting
            element_position = self._get_element_position(element, html_content)
            
            # Get element HTML for debugging
            element_html = str(element)[:200] + "..." if len(str(element)) > 200 else str(element)
            
            return FieldExtractionResult(
                field_name=field_name,
                success=True,
                value=value,
                selector=selector,
                selector_type='css',
                element_html=element_html,
                element_position=element_position
            )
            
        except Exception as e:
            return FieldExtractionResult(
                field_name=field_name,
                success=False,
                selector=selector,
                selector_type='css',
                error=f"CSS extraction failed: {str(e)}"
            )
    
    def _extract_xpath_field(self, field_name: str, xpath: str, 
                           tree, html_content: str) -> FieldExtractionResult:
        """Extract field using XPath"""
        try:
            results = tree.xpath(xpath)
            
            if not results:
                return FieldExtractionResult(
                    field_name=field_name,
                    success=False,
                    selector=xpath,
                    selector_type='xpath',
                    error="No elements found with XPath"
                )
            
            # Handle different result types
            if len(results) == 1:
                value = self._clean_extracted_value(str(results[0]), field_name)
            else:
                value = [self._clean_extracted_value(str(item), field_name) for item in results]
            
            return FieldExtractionResult(
                field_name=field_name,
                success=True,
                value=value,
                selector=xpath,
                selector_type='xpath'
            )
            
        except Exception as e:
            return FieldExtractionResult(
                field_name=field_name,
                success=False,
                selector=xpath,
                selector_type='xpath',
                error=f"XPath extraction failed: {str(e)}"
            )
    
    def _clean_extracted_value(self, value: str, field_name: str) -> Any:
        """Clean and convert extracted value based on field type"""
        if not value:
            return None
        
        # Remove HTML tags and normalize whitespace
        from re import sub, MULTILINE
        value = sub(r'<[^>]+>', '', value)
        value = sub(r'\s+', ' ', value, flags=MULTILINE).strip()
        
        # Type-specific cleaning
        if field_name == 'price':
            # Extract numeric price
            import re
            price_match = re.search(r'\$?([\d,]+)', value.replace(',', ''))
            if price_match:
                try:
                    return int(price_match.group(1).replace(',', ''))
                except ValueError:
                    pass
        
        elif field_name == 'mileage':
            # Extract numeric mileage
            import re
            mileage_match = re.search(r'([\d,]+)', value.replace(',', ''))
            if mileage_match:
                try:
                    return int(mileage_match.group(1).replace(',', ''))
                except ValueError:
                    pass
        
        elif field_name == 'year':
            # Extract 4-digit year
            import re
            year_match = re.search(r'(19|20)\d{2}', value)
            if year_match:
                try:
                    return int(year_match.group(0))
                except ValueError:
                    pass
        
        return value
    
    def _get_element_position(self, element, html_content: str) -> Optional[Dict[str, int]]:
        """Get element position in HTML for highlighting"""
        try:
            # Simple approach - find element's position in HTML string
            element_str = str(element)
            position = html_content.find(element_str)
            
            if position >= 0:
                return {
                    "start": position,
                    "end": position + len(element_str),
                    "length": len(element_str)
                }
                
        except Exception as e:
            logger.debug(f"Failed to get element position: {e}")
        
        return None
    
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
    
    def test_selector(self, html_content: str, selector: str, 
                     selector_type: str = 'css') -> Dict[str, Any]:
        """Test a single selector against HTML content"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            if selector_type == 'css':
                elements = soup.select(selector)
            else:  # xpath
                tree = html.fromstring(html_content)
                elements = tree.xpath(selector)
            
            if elements:
                # Extract values from all matching elements
                values = []
                for element in elements[:5]:  # Limit to first 5
                    if hasattr(element, 'get_text'):
                        text = element.get_text(strip=True)
                    else:
                        text = str(element).strip()
                    
                    values.append({
                        "text": text[:100] + "..." if len(text) > 100 else text,
                        "html": str(element)[:200] + "..." if len(str(element)) > 200 else str(element)
                    })
                
                return {
                    "success": True,
                    "matches": len(elements),
                    "values": values,
                    "selector": selector,
                    "selector_type": selector_type
                }
            else:
                return {
                    "success": False,
                    "matches": 0,
                    "error": "No elements found",
                    "selector": selector,
                    "selector_type": selector_type
                }
                
        except Exception as e:
            return {
                "success": False,
                "matches": 0,
                "error": str(e),
                "selector": selector,
                "selector_type": selector_type
            }
    
    def generate_goal_json(self, extracted_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate goal.json from extracted data"""
        try:
            # Convert to VehicleData model
            vehicle_data = self.base_mapper.to_vehicle_data(extracted_data)
            
            if vehicle_data:
                return vehicle_data.to_goal_json()
            
        except Exception as e:
            logger.error(f"Goal JSON generation failed: {e}")
        
        return None
    
    def validate_mapping_config(self, mapping_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a mapping configuration"""
        errors = []
        warnings = []
        
        try:
            # Check for required fields
            required_fields = ['vin', 'goal']
            for field in required_fields:
                if field not in mapping_config:
                    errors.append(f"Missing required field: {field}")
            
            # Validate each field configuration
            for field_name, field_config in mapping_config.items():
                if field_name.startswith('_'):  # Skip metadata
                    continue
                
                if isinstance(field_config, dict):
                    # Structured field config
                    if 'selector' not in field_config:
                        errors.append(f"Field '{field_name}' missing selector")
                    
                    if 'type' in field_config and field_config['type'] not in ['css', 'xpath']:
                        errors.append(f"Field '{field_name}' has invalid type: {field_config['type']}")
                
                elif isinstance(field_config, str):
                    # Simple selector string
                    if not field_config and field_name != 'goal':
                        warnings.append(f"Field '{field_name}' has empty selector")
                
                else:
                    errors.append(f"Field '{field_name}' has invalid configuration type")
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "field_count": len([f for f in mapping_config.keys() if not f.startswith('_')])
            }
            
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Validation failed: {str(e)}"],
                "warnings": [],
                "field_count": 0
            }
    
    def highlight_elements(self, html_content: str, 
                          selectors: List[Tuple[str, str]]) -> str:
        """Add highlighting classes to HTML for visual feedback"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for selector, field_name in selectors:
                try:
                    elements = soup.select(selector)
                    for element in elements:
                        # Add highlighting class
                        existing_classes = element.get('class', [])
                        existing_classes.append(f'ranom-highlight-{field_name}')
                        element['class'] = existing_classes
                        
                        # Add data attribute for field name
                        element['data-ranom-field'] = field_name
                        
                except Exception as e:
                    logger.debug(f"Failed to highlight selector {selector}: {e}")
            
            return str(soup)
            
        except Exception as e:
            logger.error(f"HTML highlighting failed: {e}")
            return html_content 