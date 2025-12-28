from __future__ import annotations

import json
import re
import logging
from typing import Optional, Any, Dict
from dataclasses import dataclass

from src.schema.output_schema import (
    VisualDimensions,
    ObservableAttributes,
    VisualMetadata,
    DominantColor,
    VisualDimension,
)


logger = logging.getLogger(__name__)


# Valid enum values for validation
VALID_FRAME_GEOMETRY = ["rectangular", "round", "oval", "aviator", "cat-eye", "geometric", "irregular", "unknown"]
VALID_TRANSPARENCY = ["opaque", "semi-transparent", "transparent", "mixed"]
VALID_SURFACE_TEXTURE = ["smooth", "matte", "glossy", "textured", "patterned", "metallic"]
VALID_FRAME_MATERIAL = ["metal", "plastic", "acetate", "titanium", "wood", "mixed", "indeterminate"]
VALID_LENS_TINT = ["clear", "tinted", "gradient", "mirrored", "photochromic", "gray", "brown", "green", "blue", "indeterminate"]
VALID_TEMPLE_STYLE = ["standard", "spring-hinge", "cable", "skull", "indeterminate"]


@dataclass
class ParsedImageAnalysis:
    visual_dimensions: VisualDimensions
    observable_attributes: ObservableAttributes
    visual_metadata: VisualMetadata


def clean_json_string(raw_text: str) -> str:
    """Extract JSON from raw text, handling markdown code blocks."""
    markdown_pattern = r"```json\s*(\{.*?\})\s*```"
    match = re.search(markdown_pattern, raw_text, re.DOTALL)
    if match:
        return match.group(1)
    
    json_pattern = r"\{.*\}"
    match = re.search(json_pattern, raw_text, re.DOTALL)
    if match:
        return match.group(0)
    
    raise ValueError("No valid JSON object found in raw text")


def safe_get_value(data: Dict[str, Any], key: str, default: Any = None, valid_values: list = None) -> Any:
    """Safely extract a value from data with fallback and validation."""
    try:
        raw_value = data.get(key, default)
        
        # Handle dict format (e.g., {"value": "something"})
        if isinstance(raw_value, dict):
            raw_value = raw_value.get("value") or raw_value.get("detected") or raw_value.get("assessment") or default
        
        # Validate against allowed values
        if valid_values and raw_value not in valid_values:
            logger.warning(f"Invalid value '{raw_value}' for '{key}', using default: {default}")
            return default
        
        return raw_value
    except Exception as e:
        logger.warning(f"Error extracting '{key}': {e}, using default: {default}")
        return default


def safe_get_dimension(data: Dict[str, Any], key: str) -> Dict[str, float]:
    """Safely extract a visual dimension with defaults."""
    try:
        dim_data = data.get(key, {})
        if isinstance(dim_data, dict):
            score = float(dim_data.get("score", 0.0))
            confidence = float(dim_data.get("confidence", 0.5))
            # Clamp values
            score = max(-5.0, min(5.0, score))
            confidence = max(0.0, min(1.0, confidence))
            return {"score": score, "confidence": confidence}
        return {"score": 0.0, "confidence": 0.5}
    except Exception as e:
        logger.warning(f"Error extracting dimension '{key}': {e}")
        return {"score": 0.0, "confidence": 0.5}


def safe_get_colors(data: Dict[str, Any]) -> list:
    """Safely extract dominant colors with defaults."""
    try:
        colors_raw = data.get("dominant_colors", [])
        if not isinstance(colors_raw, list):
            return [{"color": "unknown", "hex_approximation": "#808080", "coverage_percentage": 100.0}]
        
        colors = []
        for color in colors_raw[:3]:  # Max 3 colors
            if isinstance(color, dict):
                colors.append({
                    "color": str(color.get("color", "unknown")),
                    "hex_approximation": str(color.get("hex_approximation", "#808080")),
                    "coverage_percentage": float(color.get("coverage_percentage", 33.0))
                })
        
        if not colors:
            return [{"color": "unknown", "hex_approximation": "#808080", "coverage_percentage": 100.0}]
        
        return colors
    except Exception as e:
        logger.warning(f"Error extracting colors: {e}")
        return [{"color": "unknown", "hex_approximation": "#808080", "coverage_percentage": 100.0}]


def parse_vision_response(raw_text: str) -> ParsedImageAnalysis | None:
    """Parse Gemini vision response with comprehensive error recovery."""
    try:
        cleaned = clean_json_string(raw_text)
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing failed: {e}")
        # Try to extract visual_dimensions section only
        try:
            dim_pattern = r'"gender_expression"\s*:\s*\{[^}]+\}'
            if re.search(dim_pattern, raw_text):
                logger.warning("Attempting partial JSON recovery...")
                # Create minimal valid structure
                data = _attempt_partial_recovery(raw_text)
                if data is None:
                    return None
            else:
                return None
        except Exception:
            return None
    except ValueError as e:
        logger.error(f"Failed to parse vision response: {e}")
        return None
    
    try:
        # Parse visual dimensions with error recovery
        visual_dimensions = VisualDimensions(
            gender_expression=VisualDimension(**safe_get_dimension(data, "gender_expression")),
            visual_weight=VisualDimension(**safe_get_dimension(data, "visual_weight")),
            embellishment=VisualDimension(**safe_get_dimension(data, "embellishment")),
            unconventionality=VisualDimension(**safe_get_dimension(data, "unconventionality")),
            formality=VisualDimension(**safe_get_dimension(data, "formality")),
        )
        
        # Parse observable attributes with validation
        observable_attributes = ObservableAttributes(
            wirecore_visible=safe_get_value(data, "wirecore_visible", False),
            frame_geometry=safe_get_value(data, "frame_geometry", "unknown", VALID_FRAME_GEOMETRY),
            transparency=safe_get_value(data, "transparency", "opaque", VALID_TRANSPARENCY),
            dominant_colors=[DominantColor(**color) for color in safe_get_colors(data)],
            surface_texture=safe_get_value(data, "surface_texture", "smooth", VALID_SURFACE_TEXTURE),
            suitable_for_kids=safe_get_value(data, "suitable_for_kids", False),
        )
        
        # Parse visual metadata with validation
        visual_metadata = VisualMetadata(
            frame_material_apparent=safe_get_value(data, "frame_material_apparent", "indeterminate", VALID_FRAME_MATERIAL),
            lens_tint=safe_get_value(data, "lens_tint", "indeterminate", VALID_LENS_TINT),
            has_nose_pads=safe_get_value(data, "has_nose_pads", False),
            temple_style=safe_get_value(data, "temple_style", "indeterminate", VALID_TEMPLE_STYLE),
        )
        
        return ParsedImageAnalysis(
            visual_dimensions=visual_dimensions,
            observable_attributes=observable_attributes,
            visual_metadata=visual_metadata,
        )
    
    except Exception as e:
        logger.error(f"Failed to construct parsed analysis: {e}")
        return None


def _attempt_partial_recovery(raw_text: str) -> Optional[Dict[str, Any]]:
    """Attempt to recover partial data from malformed JSON."""
    try:
        # Try to find and extract key sections
        data = {}
        
        # Extract dimensions using regex
        dim_keys = ["gender_expression", "visual_weight", "embellishment", "unconventionality", "formality"]
        for key in dim_keys:
            pattern = rf'"{key}"\s*:\s*\{{\s*"score"\s*:\s*([-\d.]+)\s*,\s*"confidence"\s*:\s*([\d.]+)\s*\}}'
            match = re.search(pattern, raw_text)
            if match:
                data[key] = {"score": float(match.group(1)), "confidence": float(match.group(2))}
            else:
                data[key] = {"score": 0.0, "confidence": 0.5}
        
        # Set defaults for other fields
        data.setdefault("wirecore_visible", False)
        data.setdefault("frame_geometry", "unknown")
        data.setdefault("transparency", "opaque")
        data.setdefault("dominant_colors", [{"color": "unknown", "hex_approximation": "#808080", "coverage_percentage": 100.0}])
        data.setdefault("surface_texture", "smooth")
        data.setdefault("suitable_for_kids", False)
        data.setdefault("frame_material_apparent", "indeterminate")
        data.setdefault("lens_tint", "indeterminate")
        data.setdefault("has_nose_pads", False)
        data.setdefault("temple_style", "indeterminate")
        
        logger.info("Partial recovery successful with defaults")
        return data
    except Exception as e:
        logger.error(f"Partial recovery failed: {e}")
        return None
