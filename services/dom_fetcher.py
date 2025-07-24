"""
DOM Fetcher Service

Uses Selenium with headless Chromium to render JavaScript-heavy pages
and extract full DOM source with error detection and validation.
"""

import logging
import time
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse
import validators

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    WebDriverException, 
    NoSuchElementException
)

from config import config

# Set up logging
logger = logging.getLogger(__name__)


class DOMFetchResult:
    """Result object for DOM fetching operations"""
    
    def __init__(self, 
                 url: str, 
                 html: str, 
                 success: bool = True, 
                 error: Optional[str] = None,
                 status_code: Optional[int] = None,
                 final_url: Optional[str] = None,
                 load_time: Optional[float] = None):
        self.url = url
        self.html = html
        self.success = success
        self.error = error
        self.status_code = status_code
        self.final_url = final_url or url
        self.load_time = load_time
        self.is_valid = self._validate_content()
        
    def _validate_content(self) -> bool:
        """Validate if the fetched content appears to be a valid page"""
        if not self.html or not self.success:
            return False
            
        # Check for common error indicators
        error_indicators = [
            '404 not found',
            'page not found', 
            'error 404',
            'access denied',
            'forbidden',
            'internal server error',
            '500 error'
        ]
        
        html_lower = self.html.lower()
        if any(indicator in html_lower for indicator in error_indicators):
            return False
            
        # Check for minimal HTML structure
        if not ('<html' in html_lower or '<body' in html_lower):
            return False
            
        return True
    
    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"DOMFetchResult({status}, url='{self.url}', size={len(self.html)} chars)"


class WebDriverManager:
    """Manages WebDriver lifecycle and configuration"""
    
    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self._setup_options()
    
    def _setup_options(self) -> Options:
        """Configure Chrome WebDriver options"""
        options = Options()
        
        # Add all configured options
        for option in config.selenium_options:
            options.add_argument(option)
        
        # Additional performance optimizations
        options.add_argument('--disable-logging')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-zygote')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-features=TranslateUI')
        
        # Disable images and CSS for faster loading (optional)
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_settings.popups": 0
        }
        options.add_experimental_option("prefs", prefs)
        
        self.options = options
        return options
    
    def create_driver(self) -> webdriver.Chrome:
        """Create and configure a new WebDriver instance"""
        try:
            driver = webdriver.Chrome(options=self.options)
            driver.implicitly_wait(config.WEBDRIVER_IMPLICITLY_WAIT)
            driver.set_page_load_timeout(config.WEBDRIVER_TIMEOUT)
            return driver
        except Exception as e:
            logger.error(f"Failed to create WebDriver: {e}")
            raise
    
    def get_driver(self) -> webdriver.Chrome:
        """Get existing driver or create new one"""
        if not self.driver:
            self.driver = self.create_driver()
        return self.driver
    
    def quit_driver(self):
        """Safely quit the WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error quitting driver: {e}")
            finally:
                self.driver = None


class DOMFetcherService:
    """Service for fetching DOM content from web pages"""
    
    def __init__(self):
        self.driver_manager = WebDriverManager()
        self.timeout = config.WEBDRIVER_TIMEOUT
    
    def fetch_page(self, url: str, wait_for_element: Optional[str] = None) -> DOMFetchResult:
        """
        Fetch DOM content from a URL
        
        Args:
            url: URL to fetch
            wait_for_element: CSS selector to wait for before extracting content
            
        Returns:
            DOMFetchResult with page content and metadata
        """
        if not validators.url(url):
            return DOMFetchResult(
                url=url, 
                html="", 
                success=False, 
                error="Invalid URL format"
            )
        
        logger.info(f"Fetching DOM for URL: {url}")
        start_time = time.time()
        
        driver = None
        try:
            # Get WebDriver instance
            driver = self.driver_manager.get_driver()
            
            # Navigate to page
            driver.get(url)
            
            # Wait for specific element if requested
            if wait_for_element:
                try:
                    WebDriverWait(driver, self.timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_element))
                    )
                    logger.debug(f"Found expected element: {wait_for_element}")
                except TimeoutException:
                    logger.warning(f"Timeout waiting for element: {wait_for_element}")
            
            # Give the page a moment to fully render
            time.sleep(2)
            
            # Get page source and metadata
            html = driver.page_source
            final_url = driver.current_url
            load_time = time.time() - start_time
            
            logger.info(f"Successfully fetched {len(html)} characters in {load_time:.2f}s")
            
            return DOMFetchResult(
                url=url,
                html=html,
                success=True,
                final_url=final_url,
                load_time=load_time
            )
            
        except TimeoutException as e:
            error_msg = f"Page load timeout after {self.timeout}s"
            logger.error(f"{error_msg}: {e}")
            return DOMFetchResult(
                url=url,
                html="",
                success=False,
                error=error_msg
            )
            
        except WebDriverException as e:
            error_msg = f"WebDriver error: {str(e)}"
            logger.error(error_msg)
            return DOMFetchResult(
                url=url,
                html="",
                success=False,
                error=error_msg
            )
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return DOMFetchResult(
                url=url,
                html="",
                success=False,
                error=error_msg
            )
    
    def fetch_multiple(self, urls: list[str]) -> Dict[str, DOMFetchResult]:
        """
        Fetch multiple URLs efficiently
        
        Args:
            urls: List of URLs to fetch
            
        Returns:
            Dictionary mapping URLs to DOMFetchResult objects
        """
        results = {}
        
        for url in urls:
            try:
                result = self.fetch_page(url)
                results[url] = result
                
                if not result.success:
                    logger.warning(f"Failed to fetch {url}: {result.error}")
                    
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                results[url] = DOMFetchResult(
                    url=url,
                    html="",
                    success=False,
                    error=str(e)
                )
        
        return results
    
    def detect_page_type(self, html: str) -> Dict[str, Any]:
        """
        Detect page type and characteristics from HTML content
        
        Args:
            html: HTML content to analyze
            
        Returns:
            Dictionary with page characteristics
        """
        html_lower = html.lower()
        
        characteristics = {
            'is_listing': False,
            'is_error': False,
            'has_vehicle_data': False,
            'domain_indicators': []
        }
        
        # Check for vehicle listing indicators
        vehicle_indicators = [
            'vin', 'mileage', 'miles', 'price', 'dealer',
            'make', 'model', 'year', 'vehicle', 'car'
        ]
        
        for indicator in vehicle_indicators:
            if indicator in html_lower:
                characteristics['has_vehicle_data'] = True
                break
        
        # Check for specific domains
        domain_patterns = {
            'cars.com': ['cars.com', 'cars-photos'],
            'carfax.com': ['carfax', 'vehicle history'],
            'autotrader.com': ['autotrader', 'at-listing'],
            'capitalone.com': ['capital one auto']
        }
        
        for domain, patterns in domain_patterns.items():
            if any(pattern in html_lower for pattern in patterns):
                characteristics['domain_indicators'].append(domain)
        
        # Check if it's a valid listing page
        if characteristics['has_vehicle_data'] and not characteristics['is_error']:
            characteristics['is_listing'] = True
        
        return characteristics
    
    def cleanup(self):
        """Clean up WebDriver resources"""
        self.driver_manager.quit_driver()
        logger.info("DOM Fetcher cleanup completed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        self.cleanup()


# Convenience functions
def fetch_dom(url: str) -> DOMFetchResult:
    """Convenience function for single URL fetch"""
    fetcher = DOMFetcherService()
    try:
        return fetcher.fetch_page(url)
    finally:
        fetcher.cleanup()


def fetch_multiple_doms(urls: list[str]) -> Dict[str, DOMFetchResult]:
    """Convenience function for multiple URL fetch"""
    fetcher = DOMFetcherService()
    try:
        return fetcher.fetch_multiple(urls)
    finally:
        fetcher.cleanup() 