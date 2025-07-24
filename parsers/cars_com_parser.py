"""
Cars.com Parser

Extracts structured vehicle data from Cars.com listing pages.
Handles various page layouts and data formats specific to Cars.com.
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin
from decimal import Decimal

from bs4 import BeautifulSoup, Tag

from models import VehicleData

logger = logging.getLogger(__name__)


class CarsComParser:
    """Parser for Cars.com listing pages"""
    
    def __init__(self):
        self.domain = 'cars.com'
        
    def parse(self, html: str, url: str) -> Optional[VehicleData]:
        """
        Parse Cars.com HTML to extract vehicle data
        
        Args:
            html: HTML content from Cars.com page
            url: Original URL for context
            
        Returns:
            VehicleData object or None if parsing fails
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Initialize data dictionary
            data = {}
            
            # Extract basic vehicle information
            data.update(self._extract_basic_info(soup))
            
            # Extract pricing information
            data.update(self._extract_pricing(soup))
            
            # Extract vehicle details
            data.update(self._extract_details(soup))
            
            # Extract dealer information
            data.update(self._extract_dealer_info(soup))
            
            # Extract features and images
            data.update(self._extract_features(soup))
            data.update(self._extract_images(soup, url))
            
            # Extract additional metadata
            data.update(self._extract_metadata(soup))
            
            # Create and validate VehicleData object
            vehicle_data = VehicleData(**data)
            
            logger.info(f"Successfully parsed Cars.com listing: {vehicle_data.vin or 'Unknown VIN'}")
            return vehicle_data
            
        except Exception as e:
            logger.error(f"Error parsing Cars.com page: {e}")
            return None
    
    def _extract_basic_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract basic vehicle information"""
        data = {}
        
        # Try to find the main heading
        title_element = soup.find('h1', class_='listing-title')
        if not title_element:
            title_element = soup.find('h1', {'data-qa': 'vdp-vehicle-title'})
        
        if title_element:
            title_text = title_element.get_text(strip=True)
            data['listing_title'] = title_text
            
            # Extract year, make, model from title
            # Example: "2021 Toyota Camry LE"
            title_parts = title_text.split()
            if len(title_parts) >= 3:
                try:
                    year = int(title_parts[0])
                    if 1900 <= year <= 2030:
                        data['year'] = year
                        data['make'] = title_parts[1]
                        data['model'] = ' '.join(title_parts[2:])
                except (ValueError, IndexError):
                    pass
        
        # Try alternative selectors for year, make, model
        for selector, key in [
            ('[data-qa="vehicle-year"]', 'year'),
            ('[data-qa="vehicle-make"]', 'make'), 
            ('[data-qa="vehicle-model"]', 'model')
        ]:
            element = soup.select_one(selector)
            if element and key not in data:
                text = element.get_text(strip=True)
                if key == 'year':
                    try:
                        data[key] = int(text)
                    except ValueError:
                        pass
                else:
                    data[key] = text
        
        return data
    
    def _extract_pricing(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract pricing information"""
        data = {}
        
        # Try multiple price selectors
        price_selectors = [
            '.price-section .primary-price',
            '[data-qa="price-container"] .primary-price',
            '.vdp-price .primary-price',
            '.price-display .primary-price',
            '.listing-price'
        ]
        
        for selector in price_selectors:
            price_element = soup.select_one(selector)
            if price_element:
                price_text = price_element.get_text(strip=True)
                price = self._parse_price(price_text)
                if price:
                    data['price'] = price
                    break
        
        return data
    
    def _extract_details(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract vehicle details like mileage, color, transmission"""
        data = {}
        
        # Extract mileage
        mileage_element = soup.select_one('[data-qa="mileage-value"]')
        if not mileage_element:
            # Try alternative selectors
            mileage_element = soup.find(text=re.compile(r'\d+,?\d*\s+miles?', re.I))
            if mileage_element:
                mileage_element = mileage_element.parent
        
        if mileage_element:
            mileage_text = mileage_element.get_text(strip=True)
            mileage = self._parse_mileage(mileage_text)
            if mileage is not None:
                data['mileage'] = mileage
        
        # Extract VIN
        vin_element = soup.select_one('[data-qa="vin-value"]')
        if not vin_element:
            vin_element = soup.find(text=re.compile(r'VIN:?\s*([A-HJ-NPR-Z0-9]{17})', re.I))
            if vin_element:
                vin_match = re.search(r'([A-HJ-NPR-Z0-9]{17})', vin_element, re.I)
                if vin_match:
                    data['vin'] = vin_match.group(1).upper()
        elif vin_element:
            vin_text = vin_element.get_text(strip=True)
            if re.match(r'^[A-HJ-NPR-Z0-9]{17}$', vin_text, re.I):
                data['vin'] = vin_text.upper()
        
        # Extract vehicle details from key-value pairs
        details_section = soup.select_one('.vehicle-details')
        if details_section:
            details = self._extract_key_value_pairs(details_section)
            data.update(details)
        
        return data
    
    def _extract_dealer_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract dealer information"""
        data = {}
        
        # Dealer name
        dealer_element = soup.select_one('[data-qa="dealer-name"]')
        if not dealer_element:
            dealer_element = soup.select_one('.dealer-name')
        
        if dealer_element:
            data['dealer_name'] = dealer_element.get_text(strip=True)
        
        # Dealer phone
        phone_element = soup.select_one('[data-qa="dealer-phone"]')
        if not phone_element:
            phone_element = soup.find('a', href=re.compile(r'^tel:'))
        
        if phone_element:
            phone = phone_element.get_text(strip=True)
            # Clean phone number
            phone = re.sub(r'[^\d()-]', '', phone)
            data['dealer_phone'] = phone
        
        # Dealer address
        address_element = soup.select_one('[data-qa="dealer-address"]')
        if not address_element:
            address_element = soup.select_one('.dealer-address')
        
        if address_element:
            data['dealer_address'] = address_element.get_text(strip=True)
            # Extract location (city, state)
            address_text = address_element.get_text()
            location_match = re.search(r'([A-Za-z\s]+,\s*[A-Z]{2})', address_text)
            if location_match:
                data['location'] = location_match.group(1)
        
        return data
    
    def _extract_features(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract vehicle features"""
        data = {'features': []}
        
        # Try multiple feature selectors
        features_selectors = [
            '.vehicle-features li',
            '.features-list li',
            '[data-qa="vehicle-features"] li'
        ]
        
        for selector in features_selectors:
            feature_elements = soup.select(selector)
            if feature_elements:
                features = [elem.get_text(strip=True) for elem in feature_elements]
                data['features'].extend(features)
                break
        
        return data
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> Dict[str, Any]:
        """Extract vehicle images"""
        data = {'images': []}
        
        # Try multiple image selectors
        img_selectors = [
            '.vehicle-photos img',
            '.photo-gallery img',
            '.listing-images img'
        ]
        
        for selector in img_selectors:
            img_elements = soup.select(selector)
            if img_elements:
                for img in img_elements:
                    src = img.get('src') or img.get('data-src')
                    if src:
                        # Convert relative URLs to absolute
                        full_url = urljoin(base_url, src)
                        if full_url not in data['images']:
                            data['images'].append(full_url)
                break
        
        return data
    
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract additional metadata"""
        data = {}
        
        # Try to extract accident information
        accident_element = soup.find(text=re.compile(r'accident', re.I))
        if accident_element:
            accident_text = accident_element.get_text().lower()
            data['accidents'] = 'accident' in accident_text and 'no accident' not in accident_text
        
        return data
    
    def _extract_key_value_pairs(self, container: Tag) -> Dict[str, Any]:
        """Extract key-value pairs from a container element"""
        data = {}
        
        # Try different patterns for key-value pairs
        patterns = [
            ('dt', 'dd'),  # Definition lists
            ('.key', '.value'),  # Generic key-value classes
            ('.label', '.data')   # Label-data pattern
        ]
        
        for key_sel, val_sel in patterns:
            keys = container.select(key_sel)
            values = container.select(val_sel)
            
            if len(keys) == len(values):
                for key_elem, val_elem in zip(keys, values):
                    key = key_elem.get_text(strip=True).lower().replace(':', '')
                    value = val_elem.get_text(strip=True)
                    
                    # Map keys to standard names
                    key_mapping = {
                        'exterior color': 'color',
                        'color': 'color',
                        'transmission': 'transmission',
                        'engine': 'engine',
                        'fuel type': 'fuel_type',
                        'drivetrain': 'drivetrain',
                        'body style': 'body_style',
                        'body type': 'body_style'
                    }
                    
                    mapped_key = key_mapping.get(key)
                    if mapped_key and value:
                        data[mapped_key] = value
        
        return data
    
    def _parse_price(self, price_text: str) -> Optional[int]:
        """Parse price from text"""
        # Remove all non-digit characters except decimal points
        price_clean = re.sub(r'[^\d.]', '', price_text)
        
        try:
            price = float(price_clean)
            return int(price) if price > 0 else None
        except (ValueError, TypeError):
            return None
    
    def _parse_mileage(self, mileage_text: str) -> Optional[int]:
        """Parse mileage from text"""
        # Extract number from mileage text
        mileage_match = re.search(r'([\d,]+)', mileage_text.replace(',', ''))
        
        if mileage_match:
            try:
                return int(mileage_match.group(1).replace(',', ''))
            except ValueError:
                pass
        
        return None


# Convenience function
def parse_cars_com(html: str, url: str) -> Optional[VehicleData]:
    """Convenience function to parse Cars.com HTML"""
    parser = CarsComParser()
    return parser.parse(html, url) 