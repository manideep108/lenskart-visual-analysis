from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Optional, Tuple

from src.schema.input_schema import ProductInput
from src.schema.output_schema import (
    ProductMeasurement,
    VisualDimensions,
    VisualDimension,
    ObservableAttributes,
    VisualMetadata,
    QualityFlags,
    TimingBreakdown,
)
from src.schema.enums import ProcessingStatus
from src.vision.client import VisionClient
from src.vision.response_parser import parse_vision_response, ParsedImageAnalysis
from src.loader.image_loader import ImageLoader
from src.aggregation.aggregator import Aggregator
from src.config.settings import settings
from src.utils.retry import retry_with_backoff


logger = logging.getLogger(__name__)


class ProductProcessor:
    def __init__(
        self,
        vision_client: VisionClient,
        image_loader: ImageLoader,
        aggregator: Aggregator
    ):
        self.vision_client = vision_client
        self.image_loader = image_loader
        self.aggregator = aggregator
        self._last_product_time = 0.0
    
    async def process_product(
        self,
        product: ProductInput
    ) -> ProductMeasurement:
        """
        Process a single product with rate limiting, error handling, and performance tracking.
        """
        start_time = time.perf_counter()
        
        # Rate limiting between products
        await self._apply_product_rate_limit()
        self._last_product_time = time.perf_counter()
        
        # Initialize validation variable outside try block to preserve it for error responses
        image_validation = None
        
        # Track timing for each step
        timing = {"url_validation_ms": 0, "image_fetch_ms": 0, "gemini_api_ms": 0, "aggregation_ms": 0}
        
        try:
            # ASSIGNMENT REQUIREMENT: Validate URLs before processing
            from src.utils.url_validator import validate_image_urls
            from src.schema.output_schema import ImageValidation, InvalidUrl
            
            logger.info(f"Request received: product_id={product.product_id}, url_count={len(product.image_urls)}")
            
            # URL validation with timing
            validation_start = time.perf_counter()
            validation_result = await validate_image_urls(
                product.image_urls, 
                timeout=settings.URL_VALIDATION_TIMEOUT
            )
            timing["url_validation_ms"] = int((time.perf_counter() - validation_start) * 1000)
            
            # Create validation metadata
            image_validation = ImageValidation(
                total_provided=validation_result['total'],
                valid_count=validation_result['valid_count'],
                invalid_count=validation_result['invalid_count'],
                invalid_urls=[
                    InvalidUrl(
                        url=inv['url'],
                        error_type=inv['error_type'],
                        error_message=inv['error_message']
                    ) for inv in validation_result['invalid_urls']
                ]
            )
            
            logger.info(
                f"URL validation complete: valid={validation_result['valid_count']}, "
                f"invalid={validation_result['invalid_count']}, time_ms={timing['url_validation_ms']}"
            )
            
            # Use only valid URLs for processing
            valid_urls = validation_result['valid_urls']
            
            if not valid_urls:
                # All URLs are invalid - skip processing immediately
                logger.warning(f"All URLs invalid for product {product.product_id}")
                return self._create_failed_measurement(
                    product.product_id,
                    error_type="all_urls_invalid",
                    total_images=len(product.image_urls),
                    images_capped=False,
                    processing_time_ms=int((time.perf_counter() - start_time) * 1000),
                    image_validation=image_validation,
                    timing_breakdown=TimingBreakdown(**timing)
                )
            
            
            # Image count cap (use valid URLs)
            original_image_count = len(product.image_urls)
            capped_urls = valid_urls[:settings.MAX_IMAGES_PER_PRODUCT]
            images_capped = len(valid_urls) > settings.MAX_IMAGES_PER_PRODUCT
            
            if images_capped:
                logger.warning(
                    f"Product {product.product_id}: Capped from {len(valid_urls)} to "
                    f"{settings.MAX_IMAGES_PER_PRODUCT} images"
                )
            
            
            # Load images concurrently with timing
            fetch_start = time.perf_counter()
            image_results, load_error = await self._load_images_with_tracking(capped_urls)
            timing["image_fetch_ms"] = int((time.perf_counter() - fetch_start) * 1000)
            
            if load_error:
                return self._create_failed_measurement(
                    product.product_id,
                    error_type="image_download_failed",
                    total_images=original_image_count,
                    images_capped=images_capped,
                    processing_time_ms=int((time.perf_counter() - start_time) * 1000),
                    timing_breakdown=TimingBreakdown(**timing)
                )
            
            
            valid_images = [img for img in image_results if img is not None]
            
            logger.info(f"Image fetch complete: {len(valid_images)} images loaded, time_ms={timing['image_fetch_ms']}")
            
            if not valid_images:
                return self._create_failed_measurement(
                    product.product_id,
                    error_type="invalid_image_format",
                    total_images=original_image_count,
                    images_capped=images_capped,
                    processing_time_ms=int((time.perf_counter() - start_time) * 1000),
                    timing_breakdown=TimingBreakdown(**timing)
                )
            
            
            # Analyze images with Gemini API - includes timing and retry logic
            gemini_start = time.perf_counter()
            analysis_results, per_image_times, vision_error = await self._analyze_images_with_tracking(valid_images)
            timing["gemini_api_ms"] = int((time.perf_counter() - gemini_start) * 1000)
            
            if vision_error:
                logger.error(f"Vision analysis failed: {vision_error}, time_ms={timing['gemini_api_ms']}")
                return self._create_failed_measurement(
                    product.product_id,
                    error_type=vision_error,
                    total_images=original_image_count,
                    images_capped=images_capped,
                    processing_time_ms=int((time.perf_counter() - start_time) * 1000),
                    per_image_times=per_image_times,
                    timing_breakdown=TimingBreakdown(**timing)
                )
            
            
            logger.info(f"Gemini API complete: {len(analysis_results)} responses, time_ms={timing['gemini_api_ms']}")
            
            # Parse responses with quality filtering
            parsed_results = []
            per_image_analysis = []
            rejected_low_confidence = 0
            
            for i, raw in enumerate(analysis_results):
                try:
                    parsed = parse_vision_response(raw)
                    if parsed:
                        # Quality filtering: reject low confidence results
                        avg_confidence = sum([
                            parsed.visual_dimensions.gender_expression.confidence,
                            parsed.visual_dimensions.visual_weight.confidence,
                            parsed.visual_dimensions.embellishment.confidence,
                            parsed.visual_dimensions.unconventionality.confidence,
                            parsed.visual_dimensions.formality.confidence
                        ]) / 5
                        
                        if avg_confidence < settings.MIN_CONFIDENCE_THRESHOLD:
                            logger.warning(
                                f"Rejected image {i} due to low confidence: {avg_confidence:.2f} < {settings.MIN_CONFIDENCE_THRESHOLD}"
                            )
                            rejected_low_confidence += 1
                            continue
                        
                        parsed_results.append(parsed)
                        
                        # Store per-image analysis
                        from src.schema.output_schema import PerImageAnalysis
                        per_image_analysis.append(PerImageAnalysis(
                            image_url=capped_urls[i] if i < len(capped_urls) else f"image_{i}",
                            visual_dimensions=parsed.visual_dimensions,
                            processing_time_ms=per_image_times[i] if i < len(per_image_times) else 0
                        ))
                        
                        logger.debug(f"Image {i}: confidence={avg_confidence:.2f}, time_ms={per_image_times[i] if i < len(per_image_times) else 0}")
                except Exception as e:
                    logger.error(f"Parse error for image {i} in product {product.product_id}: {e}")
            
            
            if not parsed_results:
                logger.error(f"No valid results after parsing and quality filtering (rejected {rejected_low_confidence} low confidence)")
                return self._create_failed_measurement(
                    product.product_id,
                    error_type="parse_error",
                    total_images=original_image_count,
                    images_capped=images_capped,
                    processing_time_ms=int((time.perf_counter() - start_time) * 1000),
                    per_image_times=per_image_times,
                    timing_breakdown=TimingBreakdown(**timing)
                )
            
            
            # Aggregate results with timing
            aggregation_start = time.perf_counter()
            measurement = self.aggregator.aggregate(product.product_id, parsed_results)
            timing["aggregation_ms"] = int((time.perf_counter() - aggregation_start) * 1000)
            
            # Calculate variance metrics
            variance_metrics = self._calculate_variance_metrics(parsed_results)
            
            # Calculate quality flags
            quality_flags = self._calculate_quality_flags(
                measurement,
                parsed_results,
                len(valid_images),
                original_image_count
            )
            
            # Calculate quality score (0.0 to 1.0 based on confidence and variance)
            max_variance = max([
                variance_metrics.gender_expression,
                variance_metrics.visual_weight,
                variance_metrics.embellishment,
                variance_metrics.unconventionality,
                variance_metrics.formality
            ]) if variance_metrics else 0.0
            
            variance_penalty = min(max_variance / settings.HIGH_VARIANCE_THRESHOLD, 1.0)
            quality_score = measurement.aggregate_confidence * (1.0 - 0.3 * variance_penalty)
            
            # Complete timing breakdown
            timing["total_ms"] = int((time.perf_counter() - start_time) * 1000)
            
            # Add all metadata to measurement
            measurement.schema_version = "1.0"
            measurement.api_version = "1.0"
            measurement.images_capped = images_capped
            measurement.total_images_provided = original_image_count
            measurement.images_successfully_analyzed = len(parsed_results)
            measurement.processing_time_ms = timing["total_ms"]
            measurement.per_image_time_ms = per_image_times
            measurement.quality_flags = quality_flags
            measurement.error_type = None
            measurement.image_validation = image_validation
            measurement.per_image_analysis = per_image_analysis
            measurement.variance_metrics = variance_metrics
            measurement.aggregation_method = "confidence_weighted_average"
            measurement.timing_breakdown = TimingBreakdown(**timing)
            measurement.quality_score = quality_score
            measurement.retry_count = 0
            measurement.model_used = self.vision_client.current_model_name if hasattr(self.vision_client, 'current_model_name') else "unknown"
            
            
            logger.info(
                f"Request complete: product_id={product.product_id}, status=success, "
                f"total_time_ms={timing['total_ms']}, "
                f"breakdown=(validation:{timing['url_validation_ms']}ms, "
                f"fetch:{timing['image_fetch_ms']}ms, "
                f"gemini:{timing['gemini_api_ms']}ms, "
                f"aggregation:{timing['aggregation_ms']}ms), "
                f"images={len(parsed_results)}/{original_image_count}, "
                f"quality_score={quality_score:.2f}"
            )
            
            return measurement
        
        except Exception as e:
            logger.exception(f"Unexpected error processing product {product.product_id}: {e}")
            
            # Check if this is a rate limit error
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "rate" in error_str:
                # Parse retry delay from error message
                retry_seconds = self._parse_retry_delay(str(e))
                
                return self._create_failed_measurement(
                    product.product_id,
                    error_type="rate_limited",
                    error_message=f"API quota exceeded. Please retry in {retry_seconds} seconds or use a fresh API key.",
                    total_images=len(product.image_urls),
                    images_capped=False,
                    processing_time_ms=int((time.perf_counter() - start_time) * 1000),
                    retry_after_seconds=retry_seconds,
                    rate_limit_info={
                        "limit": "20 requests/day (free tier)",
                        "reset_time": "Daily at midnight UTC",
                        "suggestions": [
                            "Wait for the specified retry delay",
                            "Create a new Gemini API key for fresh quota",
                            "Upgrade to paid tier for higher limits (1500 RPM)"
                        ]
                    },
                    image_validation=image_validation  # Preserve real validation results
                )
            
            # Generic error
            return self._create_failed_measurement(
                product.product_id,
                error_type="unknown_error",
                error_message=f"Processing failed: {str(e)}",
                total_images=len(product.image_urls),
                processing_time_ms=int((time.perf_counter() - start_time) * 1000)
            )
    
    def _parse_retry_delay(self, error_message: str) -> int:
        """Extract retry delay from Gemini error message"""
        import re
        
        # Try to extract seconds from error message
        # Example: "Please retry in 37.395680969s" or "retry in 37s"
        match = re.search(r"retry in (\d+)", error_message, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # Default to 60 seconds if we can't parse
        return 60
    
    async def _apply_product_rate_limit(self):
        """Apply rate limiting between products to prevent API throttling"""
        if self._last_product_time > 0:
            elapsed = time.perf_counter() - self._last_product_time
            if elapsed < settings.API_CALL_DELAY_SECONDS:
                await asyncio.sleep(settings.API_CALL_DELAY_SECONDS - elapsed)
    
    async def _load_images_with_tracking(
        self, 
        urls: List[str]
    ) -> Tuple[List[Optional[bytes]], Optional[str]]:
        """Load images and track errors"""
        try:
            image_load_tasks = [self.image_loader.load(url) for url in urls]
            image_bytes_list = await asyncio.gather(*image_load_tasks, return_exceptions=True)
            
            # Check for exceptions
            for result in image_bytes_list:
                if isinstance(result, Exception):
                    logger.error(f"Image load exception: {result}")
                    return [], "image_download_failed"
            
            return image_bytes_list, None
        except Exception as e:
            logger.error(f"Image loading failed: {e}")
            return [], "image_download_failed"
    
    async def _analyze_images_with_tracking(
        self,
        images: List[bytes]
    ) -> Tuple[List[str], List[int], Optional[str]]:
        """Analyze images with rate limiting, timing, and error tracking"""
        results = []
        timings = []
        
        for i, img_bytes in enumerate(images):
            # IMPROVEMENT 1: Rate limiting between images
            if i > 0:
                await asyncio.sleep(settings.API_CALL_DELAY_SECONDS)
            
            img_start = time.perf_counter()
            
            try:
                response = await self.vision_client.analyze_image_with_fallback(img_bytes)
                results.append(response)
                img_time_ms = int((time.perf_counter() - img_start) * 1000)
                timings.append(img_time_ms)
                
            except Exception as e:
                error_msg = str(e).lower()
                if "rate" in error_msg or "quota" in error_msg or "limit" in error_msg:
                    logger.error(f"Rate limit hit: {e}")
                    return results, timings, "rate_limited"
                else:
                    logger.error(f"Vision model error: {e}")
                    return results, timings, "vision_model_error"
        
        return results, timings, None
    
    def _calculate_variance_metrics(self, parsed_results: List[ParsedImageAnalysis]):
        """Calculate variance across images for each dimension (ASSIGNMENT REQUIREMENT)"""
        from src.schema.output_schema import VarianceMetrics
        import statistics
        
        if len(parsed_results) < 2:
            # No variance with single image
            return VarianceMetrics()
        
        # Collect scores for each dimension
        dimension_scores = {
            'gender_expression': [],
            'visual_weight': [],
            'embellishment': [],
            'unconventionality': [],
            'formality': []
        }
        
        for result in parsed_results:
            for dim_name in dimension_scores.keys():
                score = getattr(result.visual_dimensions, dim_name).score
                dimension_scores[dim_name].append(score)
        
        # Calculate variance (using standard deviation)
        variances = {}
        for dim_name, scores in dimension_scores.items():
            if len(scores) > 1:
                variances[dim_name] = statistics.stdev(scores)
            else:
                variances[dim_name] = 0.0
        
        return VarianceMetrics(**variances)
    
    def _calculate_quality_flags(
        self,
        measurement: ProductMeasurement,
        parsed_results: List[ParsedImageAnalysis],
        successful_images: int,
        total_images: int
    ) -> QualityFlags:
        """Calculate quality flags for the measurement"""
        
        # Low confidence check
        low_confidence = measurement.aggregate_confidence < 0.5
        
        # High variance check - check if scores vary > 2.0 across images
        high_variance = False
        if len(parsed_results) > 1:
            all_scores = []
            for result in parsed_results:
                all_scores.extend([
                    result.visual_dimensions.gender_expression.score,
                    result.visual_dimensions.visual_weight.score,
                    result.visual_dimensions.embellishment.score,
                    result.visual_dimensions.unconventionality.score,
                    result.visual_dimensions.formality.score,
                ])
            if all_scores:
                score_range = max(all_scores) - min(all_scores)
                high_variance = score_range > 2.0
        
        # Single image check
        single_image_only = successful_images == 1
        
        # Partial analysis check
        partial_analysis = successful_images < total_images
        
        return QualityFlags(
            low_confidence=low_confidence,
            high_variance=high_variance,
            single_image_only=single_image_only,
            partial_analysis=partial_analysis
        )
    
    def _create_failed_measurement(
        self,
        product_id: str,
        error_type: str = "unknown_error",
        error_message: str = None,
        total_images: int = 0,
        images_capped: bool = False,
        processing_time_ms: int = 0,
        per_image_times: List[int] = None,
        image_validation = None,
        retry_after_seconds: int = None,
        rate_limit_info: dict = None,
        timing_breakdown: TimingBreakdown = None
    ) -> ProductMeasurement:
        """Create a failed measurement with proper error metadata"""
        return ProductMeasurement(
            product_id=product_id,
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
            error_type=error_type,
            error_message=error_message,
            retry_after_seconds=retry_after_seconds,
            rate_limit_info=rate_limit_info,
            images_capped=images_capped,
            total_images_provided=total_images,
            images_successfully_analyzed=0,
            processing_time_ms=processing_time_ms,
            per_image_time_ms=per_image_times or [],
            quality_flags=QualityFlags(
                low_confidence=True,
                high_variance=False,
                single_image_only=False,
                partial_analysis=total_images > 0
            ),
            image_validation=image_validation,
            timing_breakdown=timing_breakdown
        )
