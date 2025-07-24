"""
AI Goal Extractor

Uses Ollama or OpenAI GPT to extract structured vehicle data from HTML content.
Provides fallback AI-assisted workflow for sites with unknown structure.
"""

import json
import time
import logging
from typing import Dict, Any, Optional, List
import re

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from config import config
from models import VehicleData, AIExtractionResult

logger = logging.getLogger(__name__)


class AIGoalExtractor:
    """AI-powered vehicle data extractor"""
    
    def __init__(self):
        self.model_type = config.AI_MODEL
        self._setup_clients()
    
    def _setup_clients(self):
        """Setup AI model clients based on configuration"""
        if self.model_type == 'openai' and OPENAI_AVAILABLE:
            if not config.OPENAI_API_KEY:
                raise ValueError("OpenAI API key is required but not provided")
            openai.api_key = config.OPENAI_API_KEY
            self.openai_model = config.OPENAI_MODEL
            logger.info(f"Initialized OpenAI client with model: {self.openai_model}")
            
        elif self.model_type == 'ollama' and OLLAMA_AVAILABLE:
            self.ollama_client = ollama.Client(host=config.OLLAMA_BASE_URL)
            self.ollama_model = config.OLLAMA_MODEL
            logger.info(f"Initialized Ollama client with model: {self.ollama_model}")
            
        else:
            available_models = []
            if OPENAI_AVAILABLE:
                available_models.append('openai')
            if OLLAMA_AVAILABLE:
                available_models.append('ollama')
            
            raise ValueError(
                f"AI model '{self.model_type}' not available. "
                f"Available models: {available_models}"
            )
    
    def extract_from_html(self, html_content: str, url: str, 
                         existing_data: Optional[Dict[str, Any]] = None) -> AIExtractionResult:
        """
        Extract vehicle data from HTML using AI
        
        Args:
            html_content: Cleaned HTML content
            url: Source URL for context
            existing_data: Any data already extracted by generic parser
            
        Returns:
            AIExtractionResult with extracted vehicle data
        """
        start_time = time.time()
        
        try:
            # Build extraction prompt
            prompt = self._build_extraction_prompt(html_content, url, existing_data)
            
            # Extract using appropriate AI model
            if self.model_type == 'openai':
                result = self._extract_with_openai(prompt)
            else:
                result = self._extract_with_ollama(prompt)
            
            processing_time = time.time() - start_time
            result.processing_time = processing_time
            
            logger.info(f"AI extraction completed in {processing_time:.2f}s with confidence {result.confidence or 0:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"AI extraction failed: {e}")
            return AIExtractionResult(
                success=False,
                error=str(e),
                model_used=self.model_type,
                processing_time=time.time() - start_time
            )
    
    def _extract_with_openai(self, prompt: str) -> AIExtractionResult:
        """Extract data using OpenAI GPT"""
        try:
            response = openai.ChatCompletion.create(
                model=self.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at extracting structured vehicle data from web pages. Always respond with valid JSON."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            
            # Parse JSON response
            extracted_data = self._parse_ai_response(content)
            
            if extracted_data:
                confidence = self._calculate_ai_confidence(extracted_data)
                return AIExtractionResult(
                    success=True,
                    extracted_data=extracted_data,
                    confidence=confidence,
                    model_used=f"openai-{self.openai_model}",
                    tokens_used=tokens_used
                )
            else:
                return AIExtractionResult(
                    success=False,
                    error="Failed to parse AI response as valid JSON",
                    model_used=f"openai-{self.openai_model}",
                    tokens_used=tokens_used
                )
                
        except Exception as e:
            logger.error(f"OpenAI extraction error: {e}")
            return AIExtractionResult(
                success=False,
                error=str(e),
                model_used=f"openai-{self.openai_model}"
            )
    
    def _extract_with_ollama(self, prompt: str) -> AIExtractionResult:
        """Extract data using Ollama"""
        try:
            response = self.ollama_client.chat(
                model=self.ollama_model,
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are an expert at extracting structured vehicle data from web pages. Always respond with valid JSON only, no explanations.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                options={
                    'temperature': 0.1,
                    'top_p': 0.9
                }
            )
            
            content = response['message']['content']
            
            # Parse JSON response
            extracted_data = self._parse_ai_response(content)
            
            if extracted_data:
                confidence = self._calculate_ai_confidence(extracted_data)
                return AIExtractionResult(
                    success=True,
                    extracted_data=extracted_data,
                    confidence=confidence,
                    model_used=f"ollama-{self.ollama_model}"
                )
            else:
                return AIExtractionResult(
                    success=False,
                    error="Failed to parse AI response as valid JSON",
                    model_used=f"ollama-{self.ollama_model}"
                )
                
        except Exception as e:
            logger.error(f"Ollama extraction error: {e}")
            return AIExtractionResult(
                success=False,
                error=str(e),
                model_used=f"ollama-{self.ollama_model}"
            )
    
    def _build_extraction_prompt(self, html_content: str, url: str, 
                               existing_data: Optional[Dict[str, Any]] = None) -> str:
        """Build extraction prompt for AI model"""
        
        prompt = f"""
Extract vehicle information from this car listing webpage content and return it as JSON.

URL: {url}

Webpage Content:
{html_content}

"""
        
        if existing_data:
            prompt += f"\nAlready extracted data (verify and enhance):\n{json.dumps(existing_data, indent=2)}\n"
        
        prompt += """
Please extract the following vehicle information and return ONLY a valid JSON object:

{
  "vin": "17-character VIN number if found",
  "make": "Vehicle manufacturer (e.g., Toyota, Honda)",
  "model": "Vehicle model (e.g., Camry, Accord)",
  "year": "Model year as integer",
  "price": "Selling price as integer (no commas or currency symbols)",
  "mileage": "Odometer reading as integer",
  "color": "Exterior color",
  "body_style": "Body type (Sedan, SUV, Truck, etc.)",
  "transmission": "Transmission type",
  "engine": "Engine description",
  "fuel_type": "Fuel type (Gas, Hybrid, Electric, etc.)",
  "drivetrain": "Drive type (FWD, AWD, RWD, etc.)",
  "features": ["Array", "of", "vehicle", "features"],
  "images": ["Array", "of", "image", "URLs"],
  "dealer_name": "Dealer or seller name",
  "dealer_phone": "Contact phone number",
  "dealer_address": "Dealer address",
  "location": "City, State where vehicle is located",
  "listing_title": "The main title/heading of the listing",
  "accidents": "true/false if accident history is mentioned",
  "owners": "Number of previous owners as integer"
}

Rules:
- Only include fields where you found actual data
- Use null for missing data, don't make up information
- For price and mileage, extract numbers only (remove commas, dollar signs)
- For features, include only specific vehicle features, not general text
- For images, include only actual vehicle photo URLs
- Ensure all extracted data is accurate and found in the content
- Return ONLY the JSON object, no additional text or explanations
"""
        
        return prompt
    
    def _parse_ai_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse AI response and extract JSON"""
        try:
            # Try to find JSON in the response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed_data = json.loads(json_str)
                
                # Validate and clean the data
                return self._clean_extracted_data(parsed_data)
            
            # If no JSON found, try parsing the entire content
            parsed_data = json.loads(content.strip())
            return self._clean_extracted_data(parsed_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"AI response content: {content[:500]}...")
            return None
        except Exception as e:
            logger.error(f"Error processing AI response: {e}")
            return None
    
    def _clean_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate extracted data"""
        cleaned = {}
        
        # String fields
        string_fields = ['vin', 'make', 'model', 'color', 'body_style', 'transmission', 
                        'engine', 'fuel_type', 'drivetrain', 'dealer_name', 'dealer_phone',
                        'dealer_address', 'location', 'listing_title']
        
        for field in string_fields:
            value = data.get(field)
            if value and isinstance(value, str) and value.strip():
                cleaned[field] = value.strip()
        
        # Integer fields
        int_fields = ['year', 'price', 'mileage', 'owners']
        for field in int_fields:
            value = data.get(field)
            if value is not None:
                try:
                    if isinstance(value, str):
                        # Clean string numbers
                        value = re.sub(r'[^\d]', '', value)
                        if value:
                            cleaned[field] = int(value)
                    elif isinstance(value, (int, float)):
                        cleaned[field] = int(value)
                except (ValueError, TypeError):
                    pass
        
        # Boolean fields
        if 'accidents' in data:
            accidents = data['accidents']
            if isinstance(accidents, bool):
                cleaned['accidents'] = accidents
            elif isinstance(accidents, str):
                cleaned['accidents'] = accidents.lower() in ['true', 'yes', '1']
        
        # Array fields
        array_fields = ['features', 'images']
        for field in array_fields:
            value = data.get(field)
            if value and isinstance(value, list):
                # Filter out empty strings and ensure all items are strings
                cleaned_array = [str(item).strip() for item in value if item and str(item).strip()]
                if cleaned_array:
                    cleaned[field] = cleaned_array
        
        return cleaned
    
    def _calculate_ai_confidence(self, data: Dict[str, Any]) -> float:
        """Calculate confidence score for AI-extracted data"""
        score = 0.0
        total_fields = 0
        
        # Core vehicle identification (high value)
        core_fields = ['vin', 'make', 'model', 'year', 'price']
        for field in core_fields:
            total_fields += 1
            if data.get(field):
                score += 0.15  # Each core field worth 15%
        
        # Important details (medium value)
        important_fields = ['mileage', 'dealer_name', 'location']
        for field in important_fields:
            total_fields += 1
            if data.get(field):
                score += 0.1   # Each important field worth 10%
        
        # Additional details (lower value)
        detail_fields = ['color', 'transmission', 'features', 'images']
        for field in detail_fields:
            total_fields += 1
            if data.get(field):
                score += 0.05  # Each detail field worth 5%
        
        return min(score, 1.0)
    
    def create_goal_from_extraction(self, extraction_result: AIExtractionResult) -> Optional[Dict[str, Any]]:
        """Create goal.json from AI extraction result"""
        if not extraction_result.success or not extraction_result.extracted_data:
            return None
        
        try:
            vehicle_data = VehicleData(**extraction_result.extracted_data)
            goal_json = vehicle_data.to_goal_json()
            
            # Add AI extraction metadata
            goal_json['_metadata'] = {
                'extraction_method': 'ai',
                'ai_model': extraction_result.model_used,
                'confidence': extraction_result.confidence,
                'tokens_used': extraction_result.tokens_used,
                'processing_time': extraction_result.processing_time
            }
            
            return goal_json
            
        except Exception as e:
            logger.error(f"Failed to create goal from AI extraction: {e}")
            return None


# Convenience functions
def extract_with_ai(html_content: str, url: str, 
                   existing_data: Optional[Dict[str, Any]] = None) -> AIExtractionResult:
    """Convenience function for AI extraction"""
    extractor = AIGoalExtractor()
    return extractor.extract_from_html(html_content, url, existing_data)


def create_goal_from_html(html_content: str, url: str) -> Optional[Dict[str, Any]]:
    """Convenience function to create goal.json from HTML"""
    extractor = AIGoalExtractor()
    extraction_result = extractor.extract_from_html(html_content, url)
    
    if extraction_result.success:
        return extractor.create_goal_from_extraction(extraction_result)
    
    return None 