from __future__ import annotations

import json
import re
import logging
from typing import Optional
from dataclasses import dataclass

from src.schema.output_schema import (
    VisualDimensions,
    ObservableAttributes,
    VisualMetadata,
    DominantColor,
)


logger = logging.getLogger(__name__)


@dataclass
class ParsedImageAnalysis:
    visual_dimensions: VisualDimensions
    observable_attributes: ObservableAttributes
    visual_metadata: VisualMetadata


def clean_json_string(raw_text: str) -> str:
    markdown_pattern = r"```json\s*(\{.*?\})\s*```"
    match = re.search(markdown_pattern, raw_text, re.DOTALL)
    if match:
        return match.group(1)
    
    json_pattern = r"\{.*\}"
    match = re.search(json_pattern, raw_text, re.DOTALL)
    if match:
        return match.group(0)
    
    raise ValueError("No valid JSON object found in raw text")


def parse_vision_response(raw_text: str) -> ParsedImageAnalysis | None:
    try:
        cleaned = clean_json_string(raw_text)
        data = json.loads(cleaned)
        
        visual_dimensions = VisualDimensions(
            gender_expression=data["gender_expression"],
            visual_weight=data["visual_weight"],
            embellishment=data["embellishment"],
            unconventionality=data["unconventionality"],
            formality=data["formality"],
        )
        
        wirecore_visible_raw = data["wirecore_visible"]
        if isinstance(wirecore_visible_raw, dict):
            wirecore_visible = wirecore_visible_raw["detected"]
        else:
            wirecore_visible = wirecore_visible_raw
        
        frame_geometry_raw = data["frame_geometry"]
        if isinstance(frame_geometry_raw, dict):
            frame_geometry = frame_geometry_raw["value"]
        else:
            frame_geometry = frame_geometry_raw
        
        transparency_raw = data["transparency"]
        if isinstance(transparency_raw, dict):
            transparency = transparency_raw["value"]
        else:
            transparency = transparency_raw
        
        surface_texture_raw = data["surface_texture"]
        if isinstance(surface_texture_raw, dict):
            surface_texture = surface_texture_raw["value"]
        else:
            surface_texture = surface_texture_raw
        
        suitable_for_kids_raw = data["suitable_for_kids"]
        if isinstance(suitable_for_kids_raw, dict):
            suitable_for_kids = suitable_for_kids_raw["assessment"]
        else:
            suitable_for_kids = suitable_for_kids_raw
        
        observable_attributes = ObservableAttributes(
            wirecore_visible=wirecore_visible,
            frame_geometry=frame_geometry,
            transparency=transparency,
            dominant_colors=[DominantColor(**color) for color in data["dominant_colors"]],
            surface_texture=surface_texture,
            suitable_for_kids=suitable_for_kids,
        )
        
        frame_material_raw = data["frame_material_apparent"]
        if isinstance(frame_material_raw, dict):
            frame_material_apparent = frame_material_raw["value"]
        else:
            frame_material_apparent = frame_material_raw
        
        lens_tint_raw = data["lens_tint"]
        if isinstance(lens_tint_raw, dict):
            lens_tint = lens_tint_raw["value"]
        else:
            lens_tint = lens_tint_raw
        
        temple_style_raw = data["temple_style"]
        if isinstance(temple_style_raw, dict):
            temple_style = temple_style_raw["value"]
        else:
            temple_style = temple_style_raw
        
        has_nose_pads_raw = data["has_nose_pads"]
        if isinstance(has_nose_pads_raw, dict):
            has_nose_pads = has_nose_pads_raw["detected"]
        else:
            has_nose_pads = has_nose_pads_raw
        
        visual_metadata = VisualMetadata(
            frame_material_apparent=frame_material_apparent,
            lens_tint=lens_tint,
            has_nose_pads=has_nose_pads,
            temple_style=temple_style,
        )
        
        return ParsedImageAnalysis(
            visual_dimensions=visual_dimensions,
            observable_attributes=observable_attributes,
            visual_metadata=visual_metadata,
        )
    
    except Exception as e:
        logger.error(f"Failed to parse vision response: {e}")
        return None
