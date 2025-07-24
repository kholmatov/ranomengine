"""
Generic Parser for Unknown Domains

Handles vehicle listing pages from unknown or unsupported domains.
Extracts basic information and prepares content for AI-powered extraction.
"""

import re
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment
from models import VehicleData, ParseResult

logger = logging.getLogger(__name__)


class GenericParser:
    """Generic parser for unknown domain vehicle listings"""
    
    def __init__(self):
        self.domain = 'generic'
        
    def parse(self, html: str, url: str) -> ParseResult:
        """
        Parse HTML from unknown domain
        
        Args:
            html: HTML content from unknown domain
            url: Original URL for context
            
        Returns:
            ParseResult with extracted data or prepared for AI processing
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            domain = self._extract_domain(url)
            
            # Clean and prepare HTML for analysis
            cleaned_content = self._clean_html(soup)
            
            # Extract basic information using generic patterns
            extracted_data = self._extract_basic_patterns(soup, url)
            
            # Try to create VehicleData from extracted patterns
            vehicle_data = None
            confidence_score = 0.0
            
            if extracted_data and self._has_sufficient_data(extracted_data):
                try:
                    vehicle_data = VehicleData(**extracted_data)
                    confidence_score = self._calculate_confidence(extracted_data)
                    logger.info(f"Generic parser extracted data with confidence {confidence_score:.2f}")
                except Exception as e:
                    logger.warning(f"Failed to create VehicleData from generic extraction: {e}")
            
            # Prepare for AI if we don't have sufficient data
            if confidence_score < 0.7:
                logger.info("Generic extraction insufficient, preparing for AI processing")
                prepared_content = self._prepare_for_ai(soup, extracted_data)
                
                return ParseResult(
                    success=False,  # Indicates needs AI processing
                    vehicle_data=vehicle_data,
                    error="Insufficient data for confident parsing",
                    parser_used="generic",
                    confidence_score=confidence_score,
                    source_url=url,
                    domain=domain,
                    raw_extracted_data={
                        **extracted_data,
                        'cleaned_html': prepared_content,
                        'requires_ai': True
                    }
                )
            
            return ParseResult(
                success=True,
                vehicle_data=vehicle_data,
                parser_used="generic",
                confidence_score=confidence_score,
                source_url=url,
                domain=domain,
                raw_extracted_data=extracted_data
            )
            
        except Exception as e:
            logger.error(f"Error in generic parser: {e}")
            return ParseResult(
                success=False,
                error=str(e),
                parser_used="generic",
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
    
    def _clean_html(self, soup: BeautifulSoup) -> str:
        """Clean HTML content for better processing"""
        # Remove scripts, styles, comments
        for element in soup(['script', 'style', 'meta', 'link']):
            element.decompose()
        
        # Remove comments
        for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        # Get text content with some structure preserved
        return soup.get_text(separator='\n', strip=True)
    
    def _extract_basic_patterns(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract vehicle data using generic patterns"""
        data = {}
        
        # Extract VIN using regex patterns
        vin = self._extract_vin(soup)
        if vin:
            data['vin'] = vin
        
        # Extract price using common patterns
        price = self._extract_price(soup)
        if price:
            data['price'] = price
        
        # Extract mileage
        mileage = self._extract_mileage(soup)
        if mileage:
            data['mileage'] = mileage
        
        # Extract year, make, model from title or heading
        vehicle_info = self._extract_vehicle_info(soup)
        data.update(vehicle_info)
        
        # Extract dealer/seller info
        dealer_info = self._extract_dealer_info(soup)
        data.update(dealer_info)
        
        # Extract images
        images = self._extract_images(soup, url)
        if images:
            data['images'] = images
        
        # Extract features from lists
        features = self._extract_features(soup)
        if features:
            data['features'] = features
        
        return data
    
    def _extract_vin(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract VIN using pattern matching"""
        # Look for VIN in text content
        text = soup.get_text()
        vin_patterns = [
            r'VIN:?\s*([A-HJ-NPR-Z0-9]{17})',
            r'Vehicle\s*ID:?\s*([A-HJ-NPR-Z0-9]{17})',
            r'Stock:?\s*([A-HJ-NPR-Z0-9]{17})'
        ]
        
        for pattern in vin_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        
        # Look for standalone 17-character strings
        vin_match = re.search(r'\b([A-HJ-NPR-Z0-9]{17})\b', text, re.IGNORECASE)
        if vin_match:
            return vin_match.group(1).upper()
        
        return None
    
    def _extract_price(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract price using pattern matching"""
        text = soup.get_text()
        
        # Common price patterns
        price_patterns = [
            r'\$\s*([\d,]+)(?:\.\d{2})?',
            r'Price:?\s*\$?\s*([\d,]+)',
            r'MSRP:?\s*\$?\s*([\d,]+)',
            r'Sale:?\s*\$?\s*([\d,]+)'
        ]
        
        prices = []
        for pattern in price_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    price = int(match.replace(',', ''))
                    # Reasonable price range for vehicles
                    if 1000 <= price <= 200000:
                        prices.append(price)
                except ValueError:
                    continue
        
        # Return the most common price or the first reasonable one
        if prices:
            return max(set(prices), key=prices.count)
        
        return None
    
    def _extract_mileage(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract mileage using pattern matching"""
        text = soup.get_text()
        
        # Mileage patterns
        mileage_patterns = [
            r'([\d,]+)\s*miles?',
            r'Mileage:?\s*([\d,]+)',
            r'Miles:?\s*([\d,]+)'
        ]
        
        for pattern in mileage_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    mileage = int(match.group(1).replace(',', ''))
                    # Reasonable mileage range
                    if 0 <= mileage <= 500000:
                        return mileage
                except ValueError:
                    continue
        
        return None
    
    def _extract_vehicle_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract year, make, model from title or headings"""
        data = {}
        
        # Try to find main title/heading
        title_candidates = [
            soup.find('h1'),
            soup.find('title'),
            soup.find('h2'),
            soup.find('[class*="title"]'),
            soup.find('[class*="heading"]')
        ]
        
        for candidate in title_candidates:
            if candidate:
                title_text = candidate.get_text(strip=True)
                vehicle_info = self._parse_vehicle_title(title_text)
                if vehicle_info:
                    data.update(vehicle_info)
                    break
        
        return data
    
    def _parse_vehicle_title(self, title: str) -> Dict[str, Any]:
        """Parse vehicle information from title text"""
        data = {}
        
        # Pattern for year make model (e.g., "2021 Toyota Camry LE")
        pattern = r'(\d{4})\s+(\w+)\s+(.+)'
        match = re.search(pattern, title)
        
        if match:
            year_str, make, model = match.groups()
            try:
                year = int(year_str)
                if 1900 <= year <= 2030:
                    data['year'] = year
                    data['make'] = make
                    data['model'] = model.strip()
                    data['listing_title'] = title
            except ValueError:
                pass
        
        return data
    
    def _extract_dealer_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract dealer information"""
        data = {}
        
        # Look for phone numbers
        text = soup.get_text()
        phone_pattern = r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})'
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            data['dealer_phone'] = phone_match.group(1)
        
        # Look for dealer/seller name in common elements
        dealer_selectors = [
            '[class*="dealer"]',
            '[class*="seller"]',
            '[class*="contact"]'
        ]
        
        for selector in dealer_selectors:
            element = soup.select_one(selector)
            if element:
                dealer_text = element.get_text(strip=True)
                if len(dealer_text) < 100:  # Reasonable dealer name length
                    data['dealer_name'] = dealer_text
                    break
        
        return data
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract vehicle images"""
        images = []
        
        # Look for images with vehicle-related attributes
        img_elements = soup.find_all('img')
        
        for img in img_elements:
            src = img.get('src') or img.get('data-src')
            if src:
                # Skip small images (likely icons/logos)
                width = img.get('width')
                height = img.get('height')
                
                if width and height:
                    try:
                        if int(width) < 200 or int(height) < 150:
                            continue
                    except ValueError:
                        pass
                
                # Convert relative URLs
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    from urllib.parse import urljoin
                    src = urljoin(base_url, src)
                
                if src not in images:
                    images.append(src)
        
        return images[:10]  # Limit to reasonable number
    
    def _extract_features(self, soup: BeautifulSoup) -> List[str]:
        """Extract vehicle features from lists"""
        features = []
        
        # Look for lists that might contain features
        list_elements = soup.find_all(['ul', 'ol'])
        
        for ul in list_elements:
            list_items = ul.find_all('li')
            if 3 <= len(list_items) <= 20:  # Reasonable feature list size
                for li in list_items:
                    feature_text = li.get_text(strip=True)
                    if 5 <= len(feature_text) <= 50:  # Reasonable feature length
                        features.append(feature_text)
        
        return features[:15]  # Limit features
    
    def _has_sufficient_data(self, data: Dict[str, Any]) -> bool:
        """Check if extracted data is sufficient for creating VehicleData"""
        required_fields = ['vin', 'price', 'make']
        return sum(1 for field in required_fields if data.get(field)) >= 2
    
    def _calculate_confidence(self, data: Dict[str, Any]) -> float:
        """Calculate confidence score based on extracted data"""
        score = 0.0
        
        # VIN is highly valuable
        if data.get('vin'):
            score += 0.4
        
        # Price is important
        if data.get('price'):
            score += 0.3
        
        # Vehicle identification
        if data.get('make'):
            score += 0.1
        if data.get('model'):
            score += 0.1
        if data.get('year'):
            score += 0.1
        
        # Additional details
        if data.get('mileage'):
            score += 0.05
        if data.get('dealer_name'):
            score += 0.05
        if data.get('images'):
            score += 0.05
        
        return min(score, 1.0)
    
    def _prepare_for_ai(self, soup: BeautifulSoup, extracted_data: Dict[str, Any]) -> str:
        """Prepare cleaned content for AI processing"""
        # Remove navigation, footer, sidebar content
        for element in soup.find_all(['nav', 'footer', 'aside', 'header']):
            element.decompose()
        
        # Focus on main content areas
        main_content = soup.find('main') or soup.find('[role="main"]')
        if main_content:
            content = main_content.get_text(separator='\n', strip=True)
        else:
            # Remove less relevant content
            for element in soup.find_all(['form', 'button', 'input']):
                element.decompose()
            content = soup.get_text(separator='\n', strip=True)
        
        # Limit content size for AI processing
        lines = content.split('\n')
        relevant_lines = []
        
        for line in lines:
            line = line.strip()
            if len(line) > 5 and not line.isdigit():  # Skip short lines and pure numbers
                relevant_lines.append(line)
        
        # Take first 100 lines to keep content manageable
        return '\n'.join(relevant_lines[:100])


# Convenience function
def parse_generic(html: str, url: str) -> ParseResult:
    """Convenience function for generic parsing"""
    parser = GenericParser()
    return parser.parse(html, url) 