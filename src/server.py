from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import List
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.vision.gemini_client import GeminiVisionClient
from src.loader.image_loader import ImageLoader
from src.aggregation.aggregator import Aggregator
from src.pipeline.processor import ProductProcessor
from src.schema.input_schema import ProductInput
from src.schema.output_schema import ProductMeasurement


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Lenskart Visual Measurement API",
    description="AI-powered visual product measurement system",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (frontend)
try:
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    if os.path.exists(frontend_path):
        app.mount("/static", StaticFiles(directory=frontend_path), name="static")
        logger.info(f"Frontend mounted from: {frontend_path}")
except Exception as e:
    logger.warning(f"Could not mount frontend: {e}")



class AnalyzeRequest(BaseModel):
    product_id: str
    image_urls: List[str]


processor: ProductProcessor = None


@app.on_event("startup")
async def startup_event():
    global processor
    
    logger.info("Initializing pipeline components...")
    
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY is not set. Please set the environment variable.")
        sys.exit(1)
    
    vision_client = GeminiVisionClient()
    image_loader = ImageLoader()
    aggregator = Aggregator()
    processor = ProductProcessor(vision_client, image_loader, aggregator)
    
    logger.info("Pipeline initialized successfully")


@app.post("/analyze", response_model=ProductMeasurement)
async def analyze(request: AnalyzeRequest) -> ProductMeasurement:
    """
    Analyze product images and return visual measurements.
    
    Includes production improvements:
    - Rate limiting to prevent API throttling
    - Structured error types for debugging
    - Image count capping (max 5 images)
    - Processing time tracking
    - Quality flags for reliability assessment
    
    Args:
        request: AnalyzeRequest containing product_id and image_urls
        
    Returns:
        ProductMeasurement with:
        - Visual dimensions and attributes
        - Performance metrics (processing_time_ms, per_image_time_ms)
        - Quality flags (low_confidence, high_variance, etc.)
        - Error information if processing failed
        - API and schema version info
    """
    if processor is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    
    if not request.image_urls:
        raise HTTPException(status_code=400, detail="At least one image URL is required")
    
    try:
        product_input = ProductInput(
            product_id=request.product_id,
            image_urls=request.image_urls
        )
        
        result = await processor.process_product(product_input)
        
        return result
    
    except Exception as e:
        logger.exception(f"Error processing product {request.product_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process product: {str(e)}")


@app.post("/analyze-batch", response_model=List[ProductMeasurement])
async def analyze_batch(requests: List[AnalyzeRequest]) -> List[ProductMeasurement]:
    """
    Analyze multiple products in batch with rate limiting.
    
    Features:
    - Sequential processing to prevent API throttling
    - 1-second delay between products (automatic rate limiting)
    - Individual error tracking per product
    - Continues processing even if individual products fail
    
    Args:
        requests: List of AnalyzeRequest objects, each containing product_id and image_urls
        
    Returns:
        List of ProductMeasurement results with complete metadata
    """
    if processor is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    
    if not requests:
        raise HTTPException(status_code=400, detail="At least one product is required")
    
    results = []
    
    for i, request in enumerate(requests):
        try:
            product_input = ProductInput(
                product_id=request.product_id,
                image_urls=request.image_urls
            )
            
            # Process product (rate limiting handled internally by processor)
            result = await processor.process_product(product_input)
            results.append(result)
            
            logger.info(
                f"Batch progress: {i+1}/{len(requests)} - "
                f"Product {request.product_id} processed in {result.processing_time_ms}ms"
            )
            
        except Exception as e:
            logger.error(f"Error processing product {request.product_id}: {e}")
            
            # Create failed measurement using processor's method
            from src.schema.enums import ProcessingStatus
            from src.schema.output_schema import VisualDimensions, VisualDimension, ObservableAttributes, VisualMetadata, QualityFlags
            
            failed_result = ProductMeasurement(
                product_id=request.product_id,
                processing_status=ProcessingStatus.failed,
                visual_dimensions=VisualDimensions(
                    gender_expression=VisualDimension(score=0.0, confidence=0.0),
                    visual_weight=VisualDimension(score=0.0, confidence=0.0),
                    embellishment=VisualDimension(score=0.0, confidence=0.0),
                    unconventionality=VisualDimension(score=0.0, confidence=0.0),
                    formality=VisualDimension(score=0.0, confidence=0.0),
                ),
                observable_attributes=ObservableAttributes(
                    wirecore_visible=False,
                    frame_geometry="unknown",
                    transparency="opaque",
                    dominant_colors=[],
                    surface_texture="smooth",
                    suitable_for_kids=False,
                ),
                visual_metadata=VisualMetadata(
                    frame_material_apparent="indeterminate",
                    lens_tint="indeterminate",
                    has_nose_pads=False,
                    temple_style="indeterminate",
                ),
                aggregate_confidence=0.0,
                schema_version="1.0",
                api_version="1.0",
                error_type="unknown_error",
                images_capped=False,
                total_images_provided=len(request.image_urls),
                images_successfully_analyzed=0,
                processing_time_ms=0,
                per_image_time_ms=[],
                quality_flags=QualityFlags(
                    low_confidence=True,
                    high_variance=False,
                    single_image_only=False,
                    partial_analysis=True
                )
            )
            results.append(failed_result)
    
    logger.info(f"Batch complete: {len(results)} products processed")
    
    return results


@app.get("/")
async def root():
    """
    Serve the frontend application.
    """
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    else:
        return {
            "message": "Lenskart Visual Measurement API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health"
        }


@app.get("/health")
async def health():
    """
    Health check endpoint with system status.
    
    Returns:
        System health status, configuration, and component states
    """
    gemini_configured = bool(os.getenv("GEMINI_API_KEY"))
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "components": {
            "api": "operational",
            "gemini_configured": gemini_configured,
            "pipeline_initialized": processor is not None
        },
        "features": {
            "rate_limiting": True,
            "max_images_per_product": 5,
            "structured_errors": True,
            "performance_tracking": True,
            "quality_flags": True,
            "url_validation": True,
            "per_image_analysis": True,
            "variance_metrics": True
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
