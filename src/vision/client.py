from __future__ import annotations

import abc


class VisionClient(abc.ABC):
    """Abstract base class for vision API clients."""
    
    @abc.abstractmethod
    async def analyze_image(self, image_data: bytes) -> str:
        """
        Analyze an image and return JSON response.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            JSON string with analysis results
        """
        ...

