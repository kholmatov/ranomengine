"""
VIN Search Service

Uses DuckDuckGo search (ddgs) to find vehicle listings from VIN numbers.
Provides privacy-friendly and CAPTCHA-free search functionality.
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse
import validators

from ddgs import DDGS
from config import config

# Set up logging
logger = logging.getLogger(__name__)


class VINSearchResult:
    """Represents a single search result from VIN lookup"""
    
    def __init__(self, title: str, href: str, snippet: str, domain: Optional[str] = None):
        self.title = title
        self.href = href  
        self.snippet = snippet
        self.domain = domain or self._extract_domain(href)
        self.is_supported = self.domain in config.SUPPORTED_DOMAINS
        
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except Exception:
            return None
    
    def __repr__(self) -> str:
        return f"VINSearchResult(domain={self.domain}, title='{self.title[:50]}...', supported={self.is_supported})"


class VINValidator:
    """Validates VIN numbers according to standard format"""
    
    # VIN regex pattern - 17 characters, no I, O, or Q
    VIN_PATTERN = re.compile(r'^[A-HJ-NPR-Z0-9]{17}$', re.IGNORECASE)
    
    @classmethod
    def is_valid_vin(cls, vin: str) -> bool:
        """Validate VIN format"""
        if not vin or not isinstance(vin, str):
            return False
            
        vin = vin.strip().upper()
        return cls.VIN_PATTERN.match(vin) is not None
    
    @classmethod
    def clean_vin(cls, vin: str) -> str:
        """Clean and format VIN"""
        return vin.strip().upper() if vin else ""


class VINSearchService:
    """Service for searching vehicle listings using VIN numbers"""
    
    def __init__(self):
        self.ddgs = DDGS()
        self.search_timeout = config.DDGS_TIMEOUT
        self.max_results = config.DDGS_MAX_RESULTS
        
    def search_vin(self, vin: str, prioritize_supported: bool = True) -> List[VINSearchResult]:
        """
        Search for vehicle listings using VIN number
        
        Args:
            vin: 17-character VIN number
            prioritize_supported: Whether to prioritize known domains
            
        Returns:
            List of VINSearchResult objects, sorted by relevance and domain support
        """
        # Validate VIN
        if not VINValidator.is_valid_vin(vin):
            raise ValueError(f"Invalid VIN format: {vin}")
        
        clean_vin = VINValidator.clean_vin(vin)
        
        # Build search query
        search_query = config.VIN_SEARCH_TEMPLATE.format(vin=clean_vin)
        
        logger.info(f"Searching for VIN: {clean_vin}")
        logger.debug(f"Search query: {search_query}")
        
        try:
            # Perform search using DDGS
            raw_results = list(self.ddgs.text(
                search_query,
                max_results=self.max_results,
                safesearch='moderate'
            ))
            
            logger.info(f"Found {len(raw_results)} raw search results")
            
            # Convert to VINSearchResult objects
            search_results = []
            for result in raw_results:
                try:
                    search_result = VINSearchResult(
                        title=result.get('title', ''),
                        href=result.get('href', ''),
                        snippet=result.get('body', '')
                    )
                    
                    # Validate URL
                    if validators.url(search_result.href):
                        search_results.append(search_result)
                    else:
                        logger.warning(f"Invalid URL found: {search_result.href}")
                        
                except Exception as e:
                    logger.error(f"Error processing search result: {e}")
                    continue
            
            # Sort results (prioritize supported domains if requested)
            if prioritize_supported:
                search_results = self._prioritize_supported_domains(search_results)
                
            logger.info(f"Returning {len(search_results)} valid search results")
            return search_results
            
        except Exception as e:
            logger.error(f"Search failed for VIN {clean_vin}: {e}")
            raise
    
    def _prioritize_supported_domains(self, results: List[VINSearchResult]) -> List[VINSearchResult]:
        """Sort results to prioritize supported domains"""
        # Separate supported and unsupported domains
        supported = [r for r in results if r.is_supported]
        unsupported = [r for r in results if not r.is_supported]
        
        # Sort each group by title relevance (simple approach)
        supported.sort(key=lambda x: x.title.lower())
        unsupported.sort(key=lambda x: x.title.lower())
        
        # Return supported domains first
        return supported + unsupported
    
    def get_top_urls(self, vin: str, limit: int = 5) -> List[str]:
        """
        Get top URLs for a VIN search
        
        Args:
            vin: VIN number to search
            limit: Maximum number of URLs to return
            
        Returns:
            List of URL strings
        """
        results = self.search_vin(vin)
        return [result.href for result in results[:limit]]
    
    def search_with_fallback(self, vin: str, fallback_query: Optional[str] = None) -> List[VINSearchResult]:
        """
        Search with fallback query if main search fails
        
        Args:
            vin: VIN number to search
            fallback_query: Alternative search query to try
            
        Returns:
            List of VINSearchResult objects
        """
        try:
            results = self.search_vin(vin)
            if results:
                return results
        except Exception as e:
            logger.warning(f"Main VIN search failed: {e}")
        
        # Try fallback if provided
        if fallback_query:
            try:
                logger.info(f"Trying fallback search: {fallback_query}")
                raw_results = list(self.ddgs.text(
                    fallback_query,
                    max_results=self.max_results // 2,  # Reduced results for fallback
                    safesearch='moderate'
                ))
                
                return [
                    VINSearchResult(
                        title=result.get('title', ''),
                        href=result.get('href', ''),
                        snippet=result.get('body', '')
                    )
                    for result in raw_results
                    if validators.url(result.get('href', ''))
                ]
                
            except Exception as e:
                logger.error(f"Fallback search also failed: {e}")
        
        return []


# Convenience functions
def search_vin(vin: str) -> List[VINSearchResult]:
    """Convenience function for VIN search"""
    service = VINSearchService()
    return service.search_vin(vin)


def get_vin_urls(vin: str, limit: int = 5) -> List[str]:
    """Convenience function to get VIN URLs"""
    service = VINSearchService()
    return service.get_top_urls(vin, limit) 