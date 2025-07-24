"""
Shared Data Models for RanomEngine

Contains Pydantic models for structured vehicle data and parsing results.
Used across all parsers to ensure consistent data format.
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from pydantic import BaseModel, Field, validator


class VehicleData(BaseModel):
    """Structured vehicle data model"""
    
    # Core vehicle identification
    vin: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    
    # Pricing and condition
    price: Optional[int] = None
    mileage: Optional[int] = None
    
    # Physical characteristics
    color: Optional[str] = None
    body_style: Optional[str] = None
    
    # Mechanical specs
    transmission: Optional[str] = None
    engine: Optional[str] = None
    fuel_type: Optional[str] = None
    drivetrain: Optional[str] = None
    
    # Features and media
    features: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    
    # Dealer information
    dealer_name: Optional[str] = None
    dealer_phone: Optional[str] = None
    dealer_address: Optional[str] = None
    dealer_rating: Optional[float] = None
    
    # Location and metadata
    location: Optional[str] = None
    listing_title: Optional[str] = None
    
    # History and condition
    accidents: Optional[bool] = None
    owners: Optional[int] = None
    
    @validator('price')
    def validate_price(cls, v):
        if v is not None and v <= 0:
            return None
        return v
    
    @validator('year')
    def validate_year(cls, v):
        if v is not None and (v < 1900 or v > 2030):
            return None
        return v
    
    @validator('mileage')
    def validate_mileage(cls, v):
        if v is not None and v < 0:
            return None
        return v
    
    @validator('dealer_rating')
    def validate_rating(cls, v):
        if v is not None and (v < 0 or v > 5):
            return None
        return v
    
    def to_goal_json(self) -> Dict[str, Any]:
        """Convert to goal.json format for case creation"""
        goal_data = {
            "vin": self.vin,
            "goal": self._generate_goal_text(),
            "price": self.price,
            "dealer": {
                "name": self.dealer_name,
                "phone": self.dealer_phone,
                "address": self.dealer_address
            } if self.dealer_name else None,
            "location": self.location,
            "features": self.features,
            "color": self.color,
            "mileage": self.mileage,
            "accidents": self.accidents,
            "dealer_rating": self.dealer_rating,
            "make": self.make,
            "model": self.model,
            "year": self.year,
            "body_style": self.body_style,
            "transmission": self.transmission,
            "engine": self.engine,
            "fuel_type": self.fuel_type,
            "drivetrain": self.drivetrain,
            "images": self.images[:5] if self.images else [],  # Limit to 5 images
            "listing_title": self.listing_title
        }
        
        # Remove None values
        return {k: v for k, v in goal_data.items() if v is not None}
    
    def _generate_goal_text(self) -> str:
        """Generate a natural language goal description"""
        parts = []
        
        if self.year and self.make and self.model:
            parts.append(f"{self.year} {self.make} {self.model}")
        elif self.make and self.model:
            parts.append(f"{self.make} {self.model}")
        elif self.listing_title:
            parts.append(self.listing_title)
        else:
            parts.append("vehicle")
        
        # Add condition context
        if self.mileage:
            if self.mileage < 30000:
                parts.insert(-1, "low-mileage")
            elif self.mileage > 100000:
                parts.insert(-1, "high-mileage")
        
        if self.accidents is False:
            parts.insert(-1, "clean")
        
        goal_text = f"Buy a {' '.join(parts)}"
        
        if self.price:
            goal_text += f" for ${self.price:,}"
        
        return goal_text


class ParseResult(BaseModel):
    """Result of parsing operation"""
    
    success: bool
    vehicle_data: Optional[VehicleData] = None
    error: Optional[str] = None
    parser_used: Optional[str] = None
    parse_time: Optional[float] = None
    confidence_score: Optional[float] = None
    
    # Source information
    source_url: Optional[str] = None
    domain: Optional[str] = None
    
    # Raw data for debugging
    raw_extracted_data: Optional[Dict[str, Any]] = None
    
    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        vin = self.vehicle_data.vin if self.vehicle_data else "N/A"
        return f"ParseResult({status}, VIN={vin}, parser={self.parser_used})"


class SearchTrace(BaseModel):
    """Trace information for search and parsing process"""
    
    # Input information
    input_type: str  # 'vin' or 'url'
    input_value: str
    
    # Search results (if applicable)
    search_results: List[Dict[str, Any]] = Field(default_factory=list)
    selected_url: Optional[str] = None
    
    # Parsing information
    fetch_success: bool = False
    fetch_error: Optional[str] = None
    parse_result: Optional[ParseResult] = None
    
    # Timing information
    total_time: Optional[float] = None
    search_time: Optional[float] = None
    fetch_time: Optional[float] = None
    parse_time: Optional[float] = None
    
    # Final result
    final_goal: Optional[Dict[str, Any]] = None
    
    timestamp: datetime = Field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage"""
        return self.dict()


class AIExtractionResult(BaseModel):
    """Result from AI-powered extraction"""
    
    success: bool
    extracted_data: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    error: Optional[str] = None
    
    # Processing metadata
    prompt_template: Optional[str] = None
    processing_time: Optional[float] = None
    
    def to_vehicle_data(self) -> Optional[VehicleData]:
        """Convert extracted data to VehicleData"""
        if not self.success or not self.extracted_data:
            return None
            
        try:
            return VehicleData(**self.extracted_data)
        except Exception:
            return None 