"""
Goal Builder Service

Handles case integration by posting structured goal data to the Ranom API.
Manages the complete pipeline from VIN/URL input to case creation.
"""

import json
import time
import logging
import requests
from typing import Dict, Any, Optional, Union
from urllib.parse import urljoin, urlparse

from config import config
from models import VehicleData, SearchTrace, ParseResult
from services.vin_search import VINSearchService
from services.dom_fetcher import DOMFetcherService
from parsers.cars_com_parser import CarsComParser
from parsers.generic_parser import GenericParser
from ai.goal_extractor import AIGoalExtractor

logger = logging.getLogger(__name__)


class GoalBuilderService:
    """Service for building goals and creating cases from VIN or URL input"""
    
    def __init__(self):
        self.vin_search = VINSearchService()
        self.dom_fetcher = DOMFetcherService()
        self.cars_parser = CarsComParser()
        self.generic_parser = GenericParser()
        self.ai_extractor = AIGoalExtractor()
        
        # Parser mapping for supported domains
        self.domain_parsers = {
            'cars.com': self.cars_parser,
            # Can add more domain-specific parsers here
        }
    
    def process_input(self, input_value: str, input_type: Optional[str] = None) -> SearchTrace:
        """
        Process VIN or URL input through the complete pipeline
        
        Args:
            input_value: VIN number or URL to process
            input_type: 'vin' or 'url', will be auto-detected if not provided
            
        Returns:
            SearchTrace with complete processing information
        """
        start_time = time.time()
        
        # Auto-detect input type if not provided
        if not input_type:
            input_type = self._detect_input_type(input_value)
        
        # Initialize trace
        trace = SearchTrace(
            input_type=input_type,
            input_value=input_value
        )
        
        try:
            if input_type == 'vin':
                trace = self._process_vin_input(input_value, trace)
            elif input_type == 'url':
                trace = self._process_url_input(input_value, trace)
            else:
                raise ValueError(f"Unsupported input type: {input_type}")
            
            trace.total_time = time.time() - start_time
            logger.info(f"Processing completed in {trace.total_time:.2f}s")
            
            return trace
            
        except Exception as e:
            logger.error(f"Error processing input {input_value}: {e}")
            trace.parse_result = ParseResult(
                success=False,
                error=str(e),
                source_url=input_value if input_type == 'url' else None
            )
            trace.total_time = time.time() - start_time
            return trace
    
    def _detect_input_type(self, input_value: str) -> str:
        """Auto-detect if input is VIN or URL"""
        input_clean = input_value.strip()
        
        # Check if it looks like a URL
        if input_clean.startswith(('http://', 'https://', 'www.')):
            return 'url'
        
        # Check if it looks like a VIN (17 alphanumeric characters)
        if len(input_clean) == 17 and input_clean.replace(' ', '').isalnum():
            return 'vin'
        
        # Try to parse as URL
        try:
            parsed = urlparse(input_clean)
            if parsed.netloc:
                return 'url'
        except Exception:
            pass
        
        # Default to VIN if unclear
        return 'vin'
    
    def _process_vin_input(self, vin: str, trace: SearchTrace) -> SearchTrace:
        """Process VIN input through search and parsing"""
        search_start = time.time()
        
        try:
            # Search for listings using VIN
            logger.info(f"Searching for VIN: {vin}")
            search_results = self.vin_search.search_vin(vin)
            
            trace.search_time = time.time() - search_start
            trace.search_results = [
                {
                    'title': result.title,
                    'href': result.href,
                    'domain': result.domain,
                    'is_supported': result.is_supported
                }
                for result in search_results
            ]
            
            if not search_results:
                trace.parse_result = ParseResult(
                    success=False,
                    error="No search results found for VIN",
                    parser_used="search"
                )
                return trace
            
            # Try to process the best search result
            for result in search_results:
                try:
                    trace.selected_url = result.href
                    logger.info(f"Processing URL: {result.href}")
                    
                    # Fetch and parse the page
                    trace = self._fetch_and_parse(result.href, trace)
                    
                    if trace.parse_result and trace.parse_result.success:
                        break  # Success, no need to try more URLs
                        
                except Exception as e:
                    logger.warning(f"Failed to process {result.href}: {e}")
                    continue
            
            return trace
            
        except Exception as e:
            logger.error(f"Error processing VIN {vin}: {e}")
            trace.parse_result = ParseResult(
                success=False,
                error=str(e),
                parser_used="vin_search"
            )
            return trace
    
    def _process_url_input(self, url: str, trace: SearchTrace) -> SearchTrace:
        """Process URL input directly"""
        trace.selected_url = url
        return self._fetch_and_parse(url, trace)
    
    def _fetch_and_parse(self, url: str, trace: SearchTrace) -> SearchTrace:
        """Fetch DOM and parse using appropriate parser"""
        fetch_start = time.time()
        
        try:
            # Fetch page content
            logger.info(f"Fetching DOM for: {url}")
            fetch_result = self.dom_fetcher.fetch_page(url)
            
            trace.fetch_time = time.time() - fetch_start
            
            if not fetch_result.success:
                trace.fetch_success = False
                trace.fetch_error = fetch_result.error
                trace.parse_result = ParseResult(
                    success=False,
                    error=f"DOM fetch failed: {fetch_result.error}",
                    source_url=url
                )
                return trace
            
            trace.fetch_success = True
            
            # Determine parser to use
            domain = self._extract_domain(url)
            parser_start = time.time()
            
            if domain in self.domain_parsers:
                # Use domain-specific parser
                logger.info(f"Using domain-specific parser for {domain}")
                parser = self.domain_parsers[domain]
                
                try:
                    vehicle_data = parser.parse(fetch_result.html, url)
                    if vehicle_data:
                        trace.parse_result = ParseResult(
                            success=True,
                            vehicle_data=vehicle_data,
                            parser_used=f"domain-{domain}",
                            parse_time=time.time() - parser_start,
                            source_url=url,
                            domain=domain,
                            confidence_score=0.9  # High confidence for domain-specific parsers
                        )
                    else:
                        # Fall back to generic parser
                        trace.parse_result = self._try_generic_and_ai_parsing(
                            fetch_result.html, url, parser_start
                        )
                except Exception as e:
                    logger.warning(f"Domain parser failed for {domain}: {e}")
                    # Fall back to generic parser
                    trace.parse_result = self._try_generic_and_ai_parsing(
                        fetch_result.html, url, parser_start
                    )
            else:
                # Use generic parser
                logger.info(f"Using generic parser for unknown domain: {domain}")
                trace.parse_result = self._try_generic_and_ai_parsing(
                    fetch_result.html, url, parser_start
                )
            
            trace.parse_time = time.time() - parser_start
            
            # Create goal if parsing was successful
            if trace.parse_result and trace.parse_result.success:
                trace.final_goal = trace.parse_result.vehicle_data.to_goal_json()
            
            return trace
            
        except Exception as e:
            logger.error(f"Error fetching and parsing {url}: {e}")
            trace.parse_result = ParseResult(
                success=False,
                error=str(e),
                source_url=url
            )
            return trace
    
    def _try_generic_and_ai_parsing(self, html: str, url: str, start_time: float) -> ParseResult:
        """Try generic parsing, fall back to AI if needed"""
        try:
            # Try generic parser first
            generic_result = self.generic_parser.parse(html, url)
            
            if generic_result.success and generic_result.confidence_score and generic_result.confidence_score >= 0.7:
                # Generic parser was confident enough
                generic_result.parse_time = time.time() - start_time
                return generic_result
            
            # Generic parser wasn't confident, try AI extraction
            logger.info("Generic parser confidence low, trying AI extraction")
            
            existing_data = generic_result.raw_extracted_data if generic_result.raw_extracted_data else {}
            cleaned_html = existing_data.get('cleaned_html', html[:5000])  # Limit HTML size
            
            ai_result = self.ai_extractor.extract_from_html(cleaned_html, url, existing_data)
            
            if ai_result.success:
                return ParseResult(
                    success=True,
                    vehicle_data=ai_result.to_vehicle_data(),
                    parser_used="ai-assisted",
                    parse_time=time.time() - start_time,
                    confidence_score=ai_result.confidence,
                    source_url=url,
                    domain=self._extract_domain(url),
                    raw_extracted_data=ai_result.extracted_data
                )
            else:
                # AI also failed, return generic result even if low confidence
                generic_result.parse_time = time.time() - start_time
                return generic_result
                
        except Exception as e:
            logger.error(f"Error in generic/AI parsing: {e}")
            return ParseResult(
                success=False,
                error=str(e),
                parser_used="generic/ai",
                source_url=url,
                domain=self._extract_domain(url)
            )
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except Exception:
            return None
    
    def create_case(self, goal_data: Dict[str, Any], trace: Optional[SearchTrace] = None) -> Dict[str, Any]:
        """
        Create a case by posting to the Ranom API
        
        Args:
            goal_data: Structured goal data to post
            trace: Optional search trace for metadata
            
        Returns:
            API response data
        """
        try:
            # Prepare API request
            api_url = urljoin(config.BACKEND_URL, config.CASES_ENDPOINT)
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': config.USER_AGENT
            }
            
            # Add API key if available
            if config.API_KEY:
                headers['Authorization'] = f'Bearer {config.API_KEY}'
            
            # Add trace information if available
            request_data = {
                'goal_data': goal_data,
                'source_trace': trace.to_dict() if trace else None,
                'created_by': 'ranomengine',
                'processing_metadata': {
                    'extraction_method': goal_data.get('_metadata', {}).get('extraction_method'),
                    'confidence': goal_data.get('_metadata', {}).get('confidence'),
                    'timestamp': time.time()
                }
            }
            
            logger.info(f"Posting case to API: {api_url}")
            
            # Make API request
            response = requests.post(
                api_url,
                json=request_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info("Case created successfully")
                return {
                    'success': True,
                    'case_data': response.json(),
                    'api_response': response.json()
                }
            else:
                error_msg = f"API request failed with status {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }
                
        except requests.RequestException as e:
            error_msg = f"API request failed: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error creating case: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def process_and_create_case(self, input_value: str, input_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Complete pipeline: process input and create case
        
        Args:
            input_value: VIN or URL to process
            input_type: Input type ('vin' or 'url'), auto-detected if None
            
        Returns:
            Complete result with trace and case creation info
        """
        # Process the input
        trace = self.process_input(input_value, input_type)
        
        result = {
            'input_value': input_value,
            'input_type': trace.input_type,
            'trace': trace.to_dict(),
            'case_creation': None
        }
        
        # Try to create case if we have valid goal data
        if trace.final_goal:
            logger.info("Creating case from extracted goal data")
            case_result = self.create_case(trace.final_goal, trace)
            result['case_creation'] = case_result
        else:
            logger.warning("No valid goal data extracted, cannot create case")
            result['case_creation'] = {
                'success': False,
                'error': 'No valid goal data extracted from input'
            }
        
        return result
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.dom_fetcher.cleanup()
            logger.info("Goal builder cleanup completed")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")


# Convenience functions
def process_vin(vin: str) -> Dict[str, Any]:
    """Convenience function to process VIN and create case"""
    builder = GoalBuilderService()
    try:
        return builder.process_and_create_case(vin, 'vin')
    finally:
        builder.cleanup()


def process_url(url: str) -> Dict[str, Any]:
    """Convenience function to process URL and create case"""
    builder = GoalBuilderService()
    try:
        return builder.process_and_create_case(url, 'url')
    finally:
        builder.cleanup()


def process_input(input_value: str) -> Dict[str, Any]:
    """Convenience function to process input (auto-detect type) and create case"""
    builder = GoalBuilderService()
    try:
        return builder.process_and_create_case(input_value)
    finally:
        builder.cleanup() 