#!/usr/bin/env python3
"""
RanomMappingStudio - API Endpoints

FastAPI endpoints for the visual DOM-to-Goal mapping studio.
Provides API access to AI suggestions, mapping preview, and comparison functionality.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from services.dom_fetcher import DOMFetcherService
from mappingstudio.services.ai_suggester import AISuggester, SuggestionResult
from mappingstudio.services.mapper import StudioMapper, PreviewResult
from mappingstudio.services.comparator import ResultComparator, ComparisonResult

logger = logging.getLogger(__name__)

# Create router for mapping studio endpoints
router = APIRouter(prefix="/mappingstudio", tags=["Mapping Studio"])

# Global service instances
ai_suggester = None
studio_mapper = None
result_comparator = None
dom_fetcher_service = None


# Request/Response Models
class PreviewRequest(BaseModel):
    """Request for mapping preview"""
    url: Optional[str] = Field(default=None, description="URL to fetch and preview")
    html: Optional[str] = Field(default=None, description="HTML content to preview")
    mapping_config: Dict[str, Any] = Field(..., description="Mapping configuration")


class SuggestRequest(BaseModel):
    """Request for AI selector suggestions"""
    url: Optional[str] = Field(default=None, description="URL to fetch and analyze")
    html: Optional[str] = Field(default=None, description="HTML content to analyze")
    priority_fields: Optional[List[str]] = Field(default=None, description="Fields to prioritize")


class CompareRequest(BaseModel):
    """Request for mapping vs AI comparison"""
    url: Optional[str] = Field(default=None, description="URL to fetch and compare")
    html: Optional[str] = Field(default=None, description="HTML content to compare")
    mapping_config: Dict[str, Any] = Field(..., description="Mapping configuration")


class SchemaRequest(BaseModel):
    """Request for schema management"""
    site_id: str = Field(..., description="Site identifier")
    schema_data: Dict[str, Any] = Field(..., description="Schema configuration")
    created_by: Optional[str] = Field(default="anonymous", description="Creator identifier")


class TestRequest(BaseModel):
    """Request for testing mapping configuration"""
    site_id: str = Field(..., description="Site identifier")
    test_urls: List[str] = Field(..., description="URLs to test against")


class SelectorTestRequest(BaseModel):
    """Request for testing individual selectors"""
    html: str = Field(..., description="HTML content to test against")
    selector: str = Field(..., description="CSS selector or XPath to test")
    selector_type: str = Field(default="css", description="Selector type: css or xpath")


# Response Models
class PreviewResponse(BaseModel):
    """Response for mapping preview"""
    success: bool
    extracted_data: Optional[Dict[str, Any]] = None
    field_results: Optional[Dict[str, Dict[str, Any]]] = None
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    processing_time: float
    total_fields: int
    successful_fields: int
    confidence: float
    goal_json: Optional[Dict[str, Any]] = None


class SuggestResponse(BaseModel):
    """Response for AI suggestions"""
    success: bool
    suggestions: List[Dict[str, Any]]
    coverage: Optional[float] = None
    processing_time: float
    error: Optional[str] = None


class CompareResponse(BaseModel):
    """Response for mapping comparison"""
    success: bool
    overall_similarity: Optional[float] = None
    field_comparisons: Optional[List[Dict[str, Any]]] = None
    mapping_coverage: Optional[float] = None
    ai_coverage: Optional[float] = None
    recommendations: Optional[List[str]] = None
    processing_time: float
    error: Optional[str] = None


# Dependency functions
def get_ai_suggester() -> AISuggester:
    """Get AI suggester service"""
    global ai_suggester
    if ai_suggester is None:
        ai_suggester = AISuggester()
    return ai_suggester


def get_studio_mapper() -> StudioMapper:
    """Get studio mapper service"""
    global studio_mapper
    if studio_mapper is None:
        studio_mapper = StudioMapper()
    return studio_mapper


def get_result_comparator() -> ResultComparator:
    """Get result comparator service"""
    global result_comparator
    if result_comparator is None:
        result_comparator = ResultComparator()
    return result_comparator


def get_dom_fetcher() -> DOMFetcherService:
    """Get DOM fetcher service"""
    global dom_fetcher_service
    if dom_fetcher_service is None:
        dom_fetcher_service = DOMFetcherService()
    return dom_fetcher_service


# Helper function
def get_html_content(url: Optional[str], html: Optional[str], 
                    fetcher: DOMFetcherService) -> tuple[str, str]:
    """Get HTML content from URL or direct input"""
    if not url and not html:
        raise HTTPException(status_code=400, detail="Must provide either url or html")
        
    if url and html:
        raise HTTPException(status_code=400, detail="Cannot provide both url and html")
    
    if url:
        logger.info(f"Fetching URL for studio: {url}")
        fetch_result = fetcher.fetch_page(url)
        
        if not fetch_result.success:
            raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {fetch_result.error}")
        
        return fetch_result.html, url
    else:
        return html, ""


# Endpoints
@router.post("/preview", response_model=PreviewResponse)
async def preview_mapping(
    request: PreviewRequest,
    background_tasks: BackgroundTasks,
    mapper: StudioMapper = Depends(get_studio_mapper),
    fetcher: DOMFetcherService = Depends(get_dom_fetcher)
):
    """Preview mapping extraction results with detailed field analysis"""
    try:
        logger.info("Mapping studio preview requested")
        
        # Get HTML content
        html_content, source_url = get_html_content(request.url, request.html, fetcher)
        
        # Preview mapping
        result = mapper.preview_mapping(html_content, request.mapping_config, source_url)
        
        # Generate goal JSON if successful
        goal_json = None
        if result.success and result.extracted_data:
            goal_json = mapper.generate_goal_json(result.extracted_data)
        
        return PreviewResponse(
            success=result.success,
            extracted_data=result.extracted_data,
            field_results=result.field_results,
            errors=result.errors,
            warnings=result.warnings,
            processing_time=result.processing_time,
            total_fields=result.total_fields,
            successful_fields=result.successful_fields,
            confidence=result.confidence,
            goal_json=goal_json
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview mapping failed: {e}")
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


@router.post("/suggest", response_model=SuggestResponse)
async def suggest_selectors(
    request: SuggestRequest,
    background_tasks: BackgroundTasks,
    suggester: AISuggester = Depends(get_ai_suggester),
    fetcher: DOMFetcherService = Depends(get_dom_fetcher)
):
    """Get AI-powered selector suggestions for goal.json fields"""
    try:
        logger.info("AI selector suggestions requested")
        
        # Get HTML content
        html_content, source_url = get_html_content(request.url, request.html, fetcher)
        
        # Get AI suggestions
        result = suggester.suggest_selectors(
            html_content, source_url, request.priority_fields
        )
        
        if result.success:
            # Convert suggestions to dict format
            suggestions_data = []
            for suggestion in result.suggestions:
                suggestions_data.append({
                    "field_name": suggestion.field_name,
                    "selector": suggestion.selector,
                    "selector_type": suggestion.selector_type,
                    "confidence": suggestion.confidence,
                    "extracted_value": suggestion.extracted_value,
                    "reasoning": suggestion.reasoning
                })
            
            return SuggestResponse(
                success=True,
                suggestions=suggestions_data,
                coverage=result.coverage,
                processing_time=result.processing_time
            )
        else:
            return SuggestResponse(
                success=False,
                suggestions=[],
                processing_time=result.processing_time,
                error=result.error
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Selector suggestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Suggestion failed: {str(e)}")


@router.post("/compare", response_model=CompareResponse)
async def compare_mapping_with_ai(
    request: CompareRequest,
    background_tasks: BackgroundTasks,
    comparator: ResultComparator = Depends(get_result_comparator),
    fetcher: DOMFetcherService = Depends(get_dom_fetcher)
):
    """Compare mapping results with AI extraction"""
    try:
        logger.info("Mapping vs AI comparison requested")
        
        # Get HTML content
        html_content, source_url = get_html_content(request.url, request.html, fetcher)
        
        # Perform comparison
        result = comparator.compare_results(html_content, request.mapping_config, source_url)
        
        if result.success:
            # Convert field comparisons to dict format
            field_comparisons_data = []
            for comparison in result.field_comparisons:
                field_comparisons_data.append({
                    "field_name": comparison.field_name,
                    "mapping_value": comparison.mapping_value,
                    "ai_value": comparison.ai_value,
                    "match": comparison.match,
                    "similarity": comparison.similarity,
                    "difference_type": comparison.difference_type,
                    "suggestion": comparison.suggestion,
                    "confidence": comparison.confidence
                })
            
            return CompareResponse(
                success=True,
                overall_similarity=result.overall_similarity,
                field_comparisons=field_comparisons_data,
                mapping_coverage=result.mapping_coverage,
                ai_coverage=result.ai_coverage,
                recommendations=result.recommendations,
                processing_time=result.processing_time
            )
        else:
            return CompareResponse(
                success=False,
                processing_time=result.processing_time,
                error=result.error
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mapping comparison failed: {e}")
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


@router.get("/list")
async def list_schemas():
    """List all available mapping schemas"""
    try:
        schemas_dir = Path("mappingstudio/mappings")
        schemas = []
        
        if schemas_dir.exists():
            for schema_file in schemas_dir.glob("*.json"):
                try:
                    with open(schema_file, 'r') as f:
                        schema_data = json.load(f)
                        
                        schemas.append({
                            "site_id": schema_file.stem,
                            "metadata": schema_data.get("_metadata", {}),
                            "field_count": len([k for k in schema_data.keys() if not k.startswith('_')]),
                            "file_path": str(schema_file)
                        })
                except Exception as e:
                    logger.warning(f"Failed to load schema {schema_file}: {e}")
        
        return {
            "success": True,
            "schemas": schemas,
            "total_count": len(schemas)
        }
        
    except Exception as e:
        logger.error(f"Failed to list schemas: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list schemas: {str(e)}")


@router.get("/schema/{site_id}")
async def get_schema(site_id: str):
    """Get a specific mapping schema"""
    try:
        schema_file = Path(f"mappingstudio/mappings/{site_id}.json")
        
        if not schema_file.exists():
            raise HTTPException(status_code=404, detail=f"Schema not found: {site_id}")
        
        with open(schema_file, 'r') as f:
            schema_data = json.load(f)
        
        return {
            "success": True,
            "site_id": site_id,
            "schema": schema_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get schema {site_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get schema: {str(e)}")


@router.post("/schema/{site_id}")
async def create_schema(site_id: str, request: SchemaRequest):
    """Create a new mapping schema"""
    try:
        schemas_dir = Path("mappingstudio/mappings")
        schemas_dir.mkdir(parents=True, exist_ok=True)
        
        schema_file = schemas_dir / f"{site_id}.json"
        
        if schema_file.exists():
            raise HTTPException(status_code=409, detail=f"Schema already exists: {site_id}")
        
        # Add metadata
        schema_data = request.schema_data.copy()
        if "_metadata" not in schema_data:
            schema_data["_metadata"] = {}
        
        schema_data["_metadata"].update({
            "site_id": site_id,
            "created_by": request.created_by,
            "created_at": str(time.time()),
            "version": "1.0.0"
        })
        
        # Validate schema
        mapper = get_studio_mapper()
        validation = mapper.validate_mapping_config(schema_data)
        
        if not validation["valid"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid schema: {', '.join(validation['errors'])}"
            )
        
        # Save schema
        with open(schema_file, 'w') as f:
            json.dump(schema_data, f, indent=2)
        
        return {
            "success": True,
            "site_id": site_id,
            "message": "Schema created successfully",
            "validation": validation
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create schema {site_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create schema: {str(e)}")


@router.put("/schema/{site_id}")
async def update_schema(site_id: str, request: SchemaRequest):
    """Update an existing mapping schema"""
    try:
        schema_file = Path(f"mappingstudio/mappings/{site_id}.json")
        
        if not schema_file.exists():
            raise HTTPException(status_code=404, detail=f"Schema not found: {site_id}")
        
        # Load existing schema
        with open(schema_file, 'r') as f:
            existing_schema = json.load(f)
        
        # Update schema data
        schema_data = request.schema_data.copy()
        if "_metadata" not in schema_data:
            schema_data["_metadata"] = existing_schema.get("_metadata", {})
        
        schema_data["_metadata"].update({
            "site_id": site_id,
            "updated_by": request.created_by,
            "updated_at": str(time.time()),
            "version": existing_schema.get("_metadata", {}).get("version", "1.0.0")
        })
        
        # Validate schema
        mapper = get_studio_mapper()
        validation = mapper.validate_mapping_config(schema_data)
        
        if not validation["valid"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid schema: {', '.join(validation['errors'])}"
            )
        
        # Save updated schema
        with open(schema_file, 'w') as f:
            json.dump(schema_data, f, indent=2)
        
        return {
            "success": True,
            "site_id": site_id,
            "message": "Schema updated successfully",
            "validation": validation
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update schema {site_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update schema: {str(e)}")


@router.post("/test/{site_id}")
async def test_schema(site_id: str, request: TestRequest):
    """Test a mapping schema against multiple URLs"""
    try:
        # Load schema
        schema_file = Path(f"mappingstudio/mappings/{site_id}.json")
        
        if not schema_file.exists():
            raise HTTPException(status_code=404, detail=f"Schema not found: {site_id}")
        
        with open(schema_file, 'r') as f:
            schema_data = json.load(f)
        
        # Test against each URL
        results = []
        mapper = get_studio_mapper()
        fetcher = get_dom_fetcher()
        
        for test_url in request.test_urls[:5]:  # Limit to 5 URLs
            try:
                logger.info(f"Testing schema {site_id} against {test_url}")
                
                # Fetch page
                fetch_result = fetcher.fetch_page(test_url)
                
                if fetch_result.success:
                    # Test mapping
                    preview_result = mapper.preview_mapping(
                        fetch_result.html, schema_data, test_url
                    )
                    
                    results.append({
                        "url": test_url,
                        "success": preview_result.success,
                        "fields_extracted": preview_result.successful_fields,
                        "total_fields": preview_result.total_fields,
                        "confidence": preview_result.confidence,
                        "errors": preview_result.errors[:3],  # Limit errors
                        "processing_time": preview_result.processing_time
                    })
                else:
                    results.append({
                        "url": test_url,
                        "success": False,
                        "error": f"Failed to fetch: {fetch_result.error}"
                    })
                    
            except Exception as e:
                results.append({
                    "url": test_url,
                    "success": False,
                    "error": str(e)
                })
        
        # Calculate overall success rate
        successful_tests = sum(1 for r in results if r.get("success", False))
        success_rate = successful_tests / len(results) if results else 0.0
        
        return {
            "success": True,
            "site_id": site_id,
            "test_results": results,
            "success_rate": success_rate,
            "total_tests": len(results)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test schema {site_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Schema test failed: {str(e)}")


@router.get("/fields")
async def get_field_schema():
    """Get the base goal.json field schema"""
    try:
        suggester = get_ai_suggester()
        field_schema = suggester.get_field_schema()
        
        return {
            "success": True,
            "fields": field_schema,
            "field_count": len(field_schema)
        }
        
    except Exception as e:
        logger.error(f"Failed to get field schema: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get field schema: {str(e)}")


@router.post("/test-selector")
async def test_selector(
    request: SelectorTestRequest,
    mapper: StudioMapper = Depends(get_studio_mapper)
):
    """Test a single selector against HTML content"""
    try:
        result = mapper.test_selector(
            request.html, 
            request.selector, 
            request.selector_type
        )
        
        return {
            "success": True,
            "test_result": result
        }
        
    except Exception as e:
        logger.error(f"Selector test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Selector test failed: {str(e)}")


# Import time for metadata
import time


@router.get("/editor", response_class=HTMLResponse)
async def get_visual_editor():
    """Serve the visual mapping editor HTML interface"""
    try:
        editor_path = Path(__file__).parent.parent / "ui" / "editor.html"
        
        if not editor_path.exists():
            raise HTTPException(status_code=404, detail="Visual editor not found")
        
        with open(editor_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"Failed to serve visual editor: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load editor: {str(e)}") 