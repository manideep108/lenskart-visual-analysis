from __future__ import annotations

from typing import List
from collections import defaultdict, Counter
import statistics

from src.schema.output_schema import (
    ProductMeasurement,
    VisualDimensions,
    VisualDimension,
    ObservableAttributes,
    VisualMetadata,
    DominantColor,
    QualityFlags,
)
from src.schema.enums import ProcessingStatus
from src.vision.response_parser import ParsedImageAnalysis


class Aggregator:
    def aggregate(
        self,
        product_id: str,
        results: List[ParsedImageAnalysis]
    ) -> ProductMeasurement:
        if not results:
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
                quality_flags=QualityFlags(
                    low_confidence=True,
                    high_variance=False,
                    single_image_only=False,
                    partial_analysis=False
                )
            )
        
        visual_dimensions = self._aggregate_visual_dimensions(results)
        observable_attributes = self._aggregate_observable_attributes(results)
        visual_metadata = self._aggregate_visual_metadata(results)
        
        all_confidences = [
            visual_dimensions.gender_expression.confidence,
            visual_dimensions.visual_weight.confidence,
            visual_dimensions.embellishment.confidence,
            visual_dimensions.unconventionality.confidence,
            visual_dimensions.formality.confidence,
        ]
        aggregate_confidence = statistics.mean(all_confidences)
        
        # Calculate quality flags
        quality_flags = self._calculate_quality_flags(
            results=results,
            aggregate_confidence=aggregate_confidence,
            visual_dimensions=visual_dimensions
        )
        
        return ProductMeasurement(
            product_id=product_id,
            processing_status=ProcessingStatus.success,
            visual_dimensions=visual_dimensions,
            observable_attributes=observable_attributes,
            visual_metadata=visual_metadata,
            aggregate_confidence=aggregate_confidence,
            quality_flags=quality_flags
        )
    
    def _calculate_quality_flags(
        self,
        results: List[ParsedImageAnalysis],
        aggregate_confidence: float,
        visual_dimensions: VisualDimensions
    ) -> QualityFlags:
        """Calculate quality flags based on aggregation results"""
        
        # Low confidence check
        low_confidence = aggregate_confidence < 0.5
        
        # High variance check - check if scores vary significantly across images
        high_variance = False
        if len(results) > 1:
            # Calculate variance for each dimension
            for dim_name in ['gender_expression', 'visual_weight', 'embellishment', 
                            'unconventionality', 'formality']:
                scores = [getattr(r.visual_dimensions, dim_name).score for r in results]
                score_range = max(scores) - min(scores)
                if score_range > 2.0:
                    high_variance = True
                    break
        
        # Single image check
        single_image_only = len(results) == 1
        
        # Partial analysis - we don't have info about total images in aggregator
        # This will be set to False here, processor handles this
        partial_analysis = False
        
        return QualityFlags(
            low_confidence=low_confidence,
            high_variance=high_variance,
            single_image_only=single_image_only,
            partial_analysis=partial_analysis
        )
    
    def _aggregate_visual_dimensions(self, results: List[ParsedImageAnalysis]) -> VisualDimensions:
        dimension_names = [
            "gender_expression",
            "visual_weight",
            "embellishment",
            "unconventionality",
            "formality",
        ]
        
        aggregated = {}
        for dim_name in dimension_names:
            scores = []
            confidences = []
            
            for result in results:
                dim = getattr(result.visual_dimensions, dim_name)
                scores.append(dim.score)
                confidences.append(dim.confidence)
            
            total_confidence = sum(confidences)
            if total_confidence > 0:
                weighted_score = sum(s * c for s, c in zip(scores, confidences)) / total_confidence
            else:
                weighted_score = 0.0
            
            avg_confidence = statistics.mean(confidences)
            
            aggregated[dim_name] = VisualDimension(
                score=weighted_score,
                confidence=avg_confidence,
            )
        
        return VisualDimensions(**aggregated)
    
    def _aggregate_observable_attributes(self, results: List[ParsedImageAnalysis]) -> ObservableAttributes:
        wirecore_visible = self._aggregate_boolean_field(results, "wirecore_visible")
        frame_geometry = self._aggregate_enum_field(results, "frame_geometry")
        transparency = self._aggregate_enum_field(results, "transparency")
        surface_texture = self._aggregate_enum_field(results, "surface_texture")
        suitable_for_kids = self._aggregate_boolean_field(results, "suitable_for_kids")
        
        # Collect all colors from all images
        all_colors = []
        for result in results:
            all_colors.extend(result.observable_attributes.dominant_colors)
        
        # Deduplicate similar colors
        dominant_colors = self._deduplicate_colors(all_colors)
        
        return ObservableAttributes(
            wirecore_visible=wirecore_visible,
            frame_geometry=frame_geometry,
            transparency=transparency,
            dominant_colors=dominant_colors,
            surface_texture=surface_texture,
            suitable_for_kids=suitable_for_kids,
        )
    
    def _deduplicate_colors(self, all_colors: List[DominantColor]) -> List[DominantColor]:
        """
        Deduplicate colors by merging similar names and hex values.
        
        Strategy:
        1. Group colors by similarity (name or hex distance)
        2. Merge groups by averaging hex and summing coverage
        3. Return top 3 by coverage
        """
        if not all_colors:
            return []
        
        # Helper: Convert hex to RGB
        def hex_to_rgb(hex_str: str) -> tuple:
            hex_str = hex_str.lstrip('#')
            return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
        
        # Helper: Calculate RGB distance
        def rgb_distance(rgb1: tuple, rgb2: tuple) -> float:
            return ((rgb1[0] - rgb2[0])**2 + 
                    (rgb1[1] - rgb2[1])**2 + 
                    (rgb1[2] - rgb2[2])**2) ** 0.5
        
        # Helper: Average hex colors
        def average_hex(hex_list: List[str]) -> str:
            rgbs = [hex_to_rgb(h) for h in hex_list]
            avg_r = int(sum(r for r, g, b in rgbs) / len(rgbs))
            avg_g = int(sum(g for r, g, b in rgbs) / len(rgbs))
            avg_b = int(sum(b for r, g, b in rgbs) / len(rgbs))
            return f"#{avg_r:02X}{avg_g:02X}{avg_b:02X}"
        
        # Group similar colors
        color_groups = []
        
        for color in all_colors:
            # Find existing group to merge with
            merged = False
            
            for group in color_groups:
                # Check if color name matches (case-insensitive)
                if color.color.lower() == group[0].color.lower():
                    group.append(color)
                    merged = True
                    break
                
                # Check if hex is similar (RGB distance < 50)
                try:
                    color_rgb = hex_to_rgb(color.hex_approximation)
                    group_rgb = hex_to_rgb(group[0].hex_approximation)
                    
                    if rgb_distance(color_rgb, group_rgb) < 50:
                        group.append(color)
                        merged = True
                        break
                except:
                    # If hex parsing fails, skip similarity check
                    pass
            
            # If no similar group found, create new group
            if not merged:
                color_groups.append([color])
        
        # Merge each group into a single color
        merged_colors = []
        for group in color_groups:
            # Use color name from highest coverage in group
            group_sorted = sorted(group, key=lambda c: c.coverage_percentage, reverse=True)
            merged_name = group_sorted[0].color
            
            # Average hex values
            hex_values = [c.hex_approximation for c in group]
            merged_hex = average_hex(hex_values)
            
            # Sum coverage (cap at 100)
            merged_coverage = min(100.0, sum(c.coverage_percentage for c in group))
            
            merged_colors.append(DominantColor(
                color=merged_name,
                hex_approximation=merged_hex,
                coverage_percentage=merged_coverage
            ))
        
        # Sort by coverage and take top 3
        merged_colors.sort(key=lambda c: c.coverage_percentage, reverse=True)
        return merged_colors[:3]
    
    def _aggregate_visual_metadata(self, results: List[ParsedImageAnalysis]) -> VisualMetadata:
        frame_material_apparent = self._aggregate_metadata_field(results, "frame_material_apparent", "indeterminate")
        lens_tint = self._aggregate_metadata_field(results, "lens_tint", "indeterminate")
        temple_style = self._aggregate_metadata_field(results, "temple_style", "indeterminate")
        has_nose_pads = self._aggregate_metadata_boolean_field(results, "has_nose_pads")
        
        return VisualMetadata(
            frame_material_apparent=frame_material_apparent,
            lens_tint=lens_tint,
            has_nose_pads=has_nose_pads,
            temple_style=temple_style,
        )
    
    def _aggregate_boolean_field(self, results: List[ParsedImageAnalysis], field_name: str) -> bool:
        votes = defaultdict(float)
        for result in results:
            value = getattr(result.observable_attributes, field_name)
            votes[value] += 1.0
        
        if not votes:
            return False
        
        winner = max(votes.items(), key=lambda x: x[1])[0]
        return winner
    
    def _aggregate_enum_field(self, results: List[ParsedImageAnalysis], field_name: str) -> str:
        votes = defaultdict(float)
        for result in results:
            value = getattr(result.observable_attributes, field_name)
            votes[value] += 1.0
        
        if not votes:
            if field_name == "frame_geometry":
                return "unknown"
            elif field_name == "transparency":
                return "opaque"
            elif field_name == "surface_texture":
                return "smooth"
            else:
                return "unknown"
        
        winner = max(votes.items(), key=lambda x: x[1])[0]
        return winner
    
    def _aggregate_metadata_field(self, results: List[ParsedImageAnalysis], field_name: str, default: str) -> str:
        votes = defaultdict(float)
        for result in results:
            value = getattr(result.visual_metadata, field_name)
            votes[value] += 1.0
        
        if not votes:
            return default
        
        winner = max(votes.items(), key=lambda x: x[1])[0]
        return winner
    
    def _aggregate_metadata_boolean_field(self, results: List[ParsedImageAnalysis], field_name: str) -> bool:
        votes = defaultdict(float)
        for result in results:
            value = getattr(result.visual_metadata, field_name)
            votes[value] += 1.0
        
        if not votes:
            return False
        
        winner = max(votes.items(), key=lambda x: x[1])[0]
        return winner
