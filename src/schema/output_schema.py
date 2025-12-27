from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, field_validator
from src.schema.enums import (
    ProcessingStatus,
    FrameGeometry,
    Transparency,
    SurfaceTexture,
    FrameMaterialApparent,
    LensTint,
    TempleStyle,
)


class VisualDimension(BaseModel):
    score: float
    confidence: float

    @field_validator("score")
    @classmethod
    def clamp_score(cls, v: float) -> float:
        return max(-5.0, min(5.0, v))

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v


class VisualDimensions(BaseModel):
    gender_expression: VisualDimension
    visual_weight: VisualDimension
    embellishment: VisualDimension
    unconventionality: VisualDimension
    formality: VisualDimension


class DominantColor(BaseModel):
    color: str
    hex_approximation: str
    coverage_percentage: float

    @field_validator("coverage_percentage")
    @classmethod
    def validate_coverage(cls, v: float) -> float:
        if not (0.0 <= v <= 100.0):
            raise ValueError("coverage_percentage must be between 0.0 and 100.0")
        return v


class ObservableAttributes(BaseModel):
    wirecore_visible: bool
    frame_geometry: FrameGeometry
    transparency: Transparency
    dominant_colors: List[DominantColor]
    surface_texture: SurfaceTexture
    suitable_for_kids: bool

    @field_validator("dominant_colors")
    @classmethod
    def validate_dominant_colors(cls, v: List[DominantColor]) -> List[DominantColor]:
        if len(v) > 3:
            raise ValueError("dominant_colors must not exceed 3 items")
        return v


class VisualMetadata(BaseModel):
    frame_material_apparent: FrameMaterialApparent
    lens_tint: LensTint
    has_nose_pads: bool
    temple_style: TempleStyle


class QualityFlags(BaseModel):
    """Quality and reliability indicators for the analysis"""
    low_confidence: bool  # aggregate_confidence < 0.5
    high_variance: bool  # scores vary > 2.0 across images
    single_image_only: bool  # only 1 image was analyzed
    partial_analysis: bool  # some images failed to process


class InvalidUrl(BaseModel):
    """Details about invalid URL"""
    url: str
    error_type: str
    error_message: str


class ImageValidation(BaseModel):
    """URL validation results"""
    total_provided: int
    valid_count: int
    invalid_count: int
    invalid_urls: List[InvalidUrl] = []


class PerImageAnalysis(BaseModel):
    """Individual image analysis result before aggregation"""
    image_url: str
    visual_dimensions: VisualDimensions
    processing_time_ms: int


class VarianceMetrics(BaseModel):
    """Variance across multiple images for each dimension"""
    gender_expression: float = 0.0
    visual_weight: float = 0.0
    embellishment: float = 0.0
    unconventionality: float = 0.0
    formality: float = 0.0


class TimingBreakdown(BaseModel):
    """Detailed timing breakdown for each processing step"""
    url_validation_ms: int = 0
    image_fetch_ms: int = 0
    gemini_api_ms: int = 0
    aggregation_ms: int = 0
    total_ms: int = 0


class ProductMeasurement(BaseModel):
    # Core identifiers
    product_id: str
    processing_status: ProcessingStatus
    
    # Analysis results
    visual_dimensions: VisualDimensions
    observable_attributes: ObservableAttributes
    visual_metadata: VisualMetadata
    aggregate_confidence: float
    
    # Production improvements
    schema_version: str = "1.0"
    api_version: str = "1.0"
    error_type: Optional[str] = None  # Specific error type if failed
    error_message: Optional[str] = None  # Human-readable error message
    
    # Rate limit information (when error_type = "rate_limited")
    retry_after_seconds: Optional[int] = None  # Seconds to wait before retry
    rate_limit_info: Optional[dict] = None  # Additional rate limit context
    
    # Image processing metadata
    images_capped: bool = False  # True if more than 5 images were capped
    total_images_provided: int = 0
    images_successfully_analyzed: int = 0
    
    # Performance metrics
    processing_time_ms: int = 0  # Total processing time
    per_image_time_ms: List[int] = []  # Time per image
    
    # Quality indicators
    quality_flags: QualityFlags
    
    # URL validation (ASSIGNMENT REQUIREMENT - handling invalid URLs)
    image_validation: Optional[ImageValidation] = None
    
    # Non-deterministic AI handling (ASSIGNMENT REQUIREMENT)
    per_image_analysis: List[PerImageAnalysis] = []  # Individual image results
    variance_metrics: Optional[VarianceMetrics] = None  # Score variance across images
    aggregation_method: str = "confidence_weighted_average"
    
    # Enhanced performance tracking
    timing_breakdown: Optional[TimingBreakdown] = None
    quality_score: Optional[float] = None  # 0.0 to 1.0 based on confidence + variance
    retry_count: int = 0
    
    # Model fallback tracking
    model_used: Optional[str] = None  # Which model succeeded
    models_attempted: Optional[List[str]] = []  # All models tried

    @field_validator("aggregate_confidence")
    @classmethod
    def validate_aggregate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("aggregate_confidence must be between 0.0 and 1.0")
        return v
