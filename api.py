#!/usr/bin/env python3
"""
RanomEngine REST API Server

FastAPI-based REST API for the VIN search and goal extraction system.
Provides endpoints for all major RanomEngine functionality.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from config import config
from services.vin_search import VINSearchService, VINValidator
from services.dom_fetcher import DOMFetcherService
from services.goal_builder import GoalBuilderService
from parsers.cars_com_parser import CarsComParser
from parsers.generic_parser import GenericParser
from ai.goal_extractor import AIGoalExtractor
from models import VehicleData, SearchTrace

# Set up logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress verbose loggers
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


# Request/Response Models
class VINSearchRequest(BaseModel):
    vin: str = Field(..., description="17-character VIN number")
    limit: int = Field(5, description="Maximum number of results", ge=1, le=20)
    prioritize_supported: bool = Field(True, description="Prioritize supported domains")


class URLFetchRequest(BaseModel):
    url: str = Field(..., description="URL to fetch")
    wait_for_element: Optional[str] = Field(None, description="CSS selector to wait for")
    save_html: bool = Field(False, description="Include HTML content in response")


class ParsePageRequest(BaseModel):
    url: str = Field(..., description="URL to parse")
    parser: str = Field("auto", description="Parser to use: auto, cars.com, generic")


class ProcessRequest(BaseModel):
    input_value: str = Field(..., description="VIN number or URL to process")
    input_type: Optional[str] = Field(None, description="Input type: vin, url, or auto-detect")
    create_case: bool = Field(True, description="Whether to create case via API")


class AIExtractionRequest(BaseModel):
    html_content: str = Field(..., description="HTML content to extract from")
    url: str = Field(..., description="Source URL for context")
    existing_data: Optional[Dict[str, Any]] = Field(None, description="Already extracted data")


class VINValidationRequest(BaseModel):
    vin: str = Field(..., description="VIN number to validate")


# Response Models
class APIResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None
    timestamp: str = Field(default_factory=lambda: str(time.time()))


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: str = Field(default_factory=lambda: str(time.time()))
    services: Dict[str, str] = {}


# Global service instances (managed by lifespan)
services = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    logger.info("Starting RanomEngine API server...")
    
    # Initialize services
    try:
        services["vin_search"] = VINSearchService()
        services["goal_builder"] = GoalBuilderService()
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Cleanup
    logger.info("Shutting down RanomEngine API server...")
    if "goal_builder" in services:
        services["goal_builder"].cleanup()


# FastAPI app
app = FastAPI(
    title="RanomEngine API",
    description="VIN Search & Smart Goal Builder - Automate car case creation from VIN or URL input",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency for services
def get_vin_search() -> VINSearchService:
    return services["vin_search"]


def get_goal_builder() -> GoalBuilderService:
    return services["goal_builder"]


# Endpoints
@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint"""
    service_status = {}
    
    try:
        # Test VIN validator
        VINValidator.is_valid_vin("1HGCM82633A123456")
        service_status["vin_validator"] = "healthy"
    except Exception:
        service_status["vin_validator"] = "unhealthy"
    
    try:
        # Test configuration
        config.validate()
        service_status["configuration"] = "healthy"
    except Exception:
        service_status["configuration"] = "unhealthy"
    
    return HealthResponse(services=service_status)


@app.get("/config", tags=["System"])
async def get_config():
    """Get current configuration (excluding sensitive data)"""
    return APIResponse(
        success=True,
        data={
            "ddgs_max_results": config.DDGS_MAX_RESULTS,
            "webdriver_headless": config.WEBDRIVER_HEADLESS,
            "ai_model": config.AI_MODEL,
            "supported_domains": config.SUPPORTED_DOMAINS,
            "log_level": config.LOG_LEVEL,
            "backend_url": config.BACKEND_URL
        }
    )


@app.post("/validate/vin", response_model=APIResponse, tags=["Validation"])
async def validate_vin(request: VINValidationRequest):
    """Validate VIN format"""
    start_time = time.time()
    
    try:
        is_valid = VINValidator.is_valid_vin(request.vin)
        cleaned_vin = VINValidator.clean_vin(request.vin)
        
        return APIResponse(
            success=True,
            data={
                "vin": request.vin,
                "cleaned_vin": cleaned_vin,
                "is_valid": is_valid,
                "message": "VIN is valid" if is_valid else "VIN is invalid"
            },
            processing_time=time.time() - start_time
        )
    except Exception as e:
        logger.error(f"VIN validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/search/vin", response_model=APIResponse, tags=["Search"])
async def search_vin(
    request: VINSearchRequest,
    vin_search: VINSearchService = Depends(get_vin_search)
):
    """Search for vehicle listings using VIN number"""
    start_time = time.time()
    
    try:
        logger.info(f"Searching for VIN: {request.vin}")
        
        results = vin_search.search_vin(
            request.vin, 
            prioritize_supported=request.prioritize_supported
        )
        
        # Limit results
        results = results[:request.limit]
        
        search_data = [
            {
                "title": result.title,
                "url": result.href,
                "domain": result.domain,
                "is_supported": result.is_supported,
                "snippet": result.snippet
            }
            for result in results
        ]
        
        return APIResponse(
            success=True,
            data={
                "vin": request.vin,
                "results_count": len(search_data),
                "results": search_data
            },
            processing_time=time.time() - start_time
        )
        
    except ValueError as e:
        logger.error(f"Invalid VIN: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/fetch/page", response_model=APIResponse, tags=["Fetching"])
async def fetch_page(request: URLFetchRequest):
    """Fetch webpage content using Selenium"""
    start_time = time.time()
    
    try:
        logger.info(f"Fetching page: {request.url}")
        
        with DOMFetcherService() as fetcher:
            result = fetcher.fetch_page(request.url, request.wait_for_element)
            
            if not result.success:
                raise HTTPException(status_code=400, detail=result.error)
            
            # Analyze page
            page_info = fetcher.detect_page_type(result.html)
            
            response_data = {
                "url": result.url,
                "final_url": result.final_url,
                "load_time": result.load_time,
                "html_size": len(result.html),
                "is_valid": result.is_valid,
                "page_analysis": page_info
            }
            
            # Include HTML if requested (be careful with large responses)
            if request.save_html:
                response_data["html_content"] = result.html[:50000]  # Limit to 50KB
            
            return APIResponse(
                success=True,
                data=response_data,
                processing_time=time.time() - start_time
            )
            
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/parse/page", response_model=APIResponse, tags=["Parsing"])
async def parse_page(request: ParsePageRequest):
    """Parse a vehicle listing page"""
    start_time = time.time()
    
    try:
        logger.info(f"Parsing page: {request.url}")
        
        # Fetch page first
        with DOMFetcherService() as fetcher:
            fetch_result = fetcher.fetch_page(request.url)
            
            if not fetch_result.success:
                raise HTTPException(status_code=400, detail=f"Failed to fetch page: {fetch_result.error}")
        
        # Determine parser
        if request.parser == "auto":
            if "cars.com" in request.url.lower():
                parser = CarsComParser()
                parser_name = "cars.com"
            else:
                parser = GenericParser()
                parser_name = "generic"
        elif request.parser == "cars.com":
            parser = CarsComParser()
            parser_name = "cars.com"
        else:
            parser = GenericParser()
            parser_name = "generic"
        
        # Parse the page
        if parser_name == "cars.com":
            vehicle_data = parser.parse(fetch_result.html, request.url)
            if vehicle_data:
                parse_data = {
                    "success": True,
                    "parser_used": parser_name,
                    "vehicle_data": vehicle_data.dict(),
                    "confidence_score": 0.9
                }
            else:
                parse_data = {"success": False, "error": "Failed to extract vehicle data"}
        else:
            # Generic parser returns ParseResult
            parse_result = parser.parse(fetch_result.html, request.url)
            parse_data = {
                "success": parse_result.success,
                "parser_used": parser_name,
                "vehicle_data": parse_result.vehicle_data.dict() if parse_result.vehicle_data else None,
                "error": parse_result.error,
                "confidence_score": parse_result.confidence_score,
                "requires_ai": parse_result.raw_extracted_data.get("requires_ai", False) if parse_result.raw_extracted_data else False
            }
        
        return APIResponse(
            success=parse_data["success"],
            data=parse_data,
            error=parse_data.get("error"),
            processing_time=time.time() - start_time
        )
        
    except Exception as e:
        logger.error(f"Parse error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract/ai", response_model=APIResponse, tags=["AI"])
async def extract_ai(request: AIExtractionRequest):
    """Extract vehicle data using AI"""
    start_time = time.time()
    
    try:
        logger.info(f"AI extraction for URL: {request.url}")
        
        extractor = AIGoalExtractor()
        result = extractor.extract_from_html(
            request.html_content, 
            request.url, 
            request.existing_data
        )
        
        if result.success:
            return APIResponse(
                success=True,
                data={
                    "extracted_data": result.extracted_data,
                    "confidence": result.confidence,
                    "model_used": result.model_used,
                    "tokens_used": result.tokens_used
                },
                processing_time=time.time() - start_time
            )
        else:
            return APIResponse(
                success=False,
                error=result.error,
                data={
                    "model_used": result.model_used,
                    "tokens_used": result.tokens_used
                },
                processing_time=time.time() - start_time
            )
            
    except Exception as e:
        logger.error(f"AI extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process/complete", response_model=APIResponse, tags=["Processing"])
async def process_complete(
    request: ProcessRequest,
    background_tasks: BackgroundTasks,
    goal_builder: GoalBuilderService = Depends(get_goal_builder)
):
    """Process VIN or URL through complete pipeline"""
    start_time = time.time()
    
    try:
        logger.info(f"Processing input: {request.input_value}")
        
        if request.create_case:
            # Full pipeline with case creation
            result = goal_builder.process_and_create_case(
                request.input_value, 
                request.input_type
            )
        else:
            # Just processing, no case creation
            trace = goal_builder.process_input(
                request.input_value, 
                request.input_type
            )
            result = {
                "input_value": request.input_value,
                "input_type": trace.input_type,
                "trace": trace.to_dict(),
                "case_creation": {"skipped": True}
            }
        
        return APIResponse(
            success=True,
            data=result,
            processing_time=time.time() - start_time
        )
        
    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Convenience endpoints
@app.post("/process/vin", response_model=APIResponse, tags=["Processing"])
async def process_vin(
    vin: str,
    create_case: bool = True,
    goal_builder: GoalBuilderService = Depends(get_goal_builder)
):
    """Process VIN through complete pipeline (convenience endpoint)"""
    request = ProcessRequest(
        input_value=vin,
        input_type="vin",
        create_case=create_case
    )
    return await process_complete(request, BackgroundTasks(), goal_builder)


@app.post("/process/url", response_model=APIResponse, tags=["Processing"])
async def process_url(
    url: str,
    create_case: bool = True,
    goal_builder: GoalBuilderService = Depends(get_goal_builder)
):
    """Process URL through complete pipeline (convenience endpoint)"""
    request = ProcessRequest(
        input_value=url,
        input_type="url",
        create_case=create_case
    )
    return await process_complete(request, BackgroundTasks(), goal_builder)


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"success": False, "error": "Endpoint not found"}
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"}
    )


# Main entry point
if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=config.LOG_LEVEL.lower()
    ) 