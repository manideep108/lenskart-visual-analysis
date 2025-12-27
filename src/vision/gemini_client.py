from __future__ import annotations

import os
import asyncio
import base64
import logging
import google.generativeai as genai

from src.vision.client import VisionClient
from src.vision.prompts import CANONICAL_SYSTEM_PROMPT, build_user_prompt
from src.config.settings import settings


logger = logging.getLogger(__name__)


class GeminiVisionClient(VisionClient):
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        genai.configure(api_key=api_key)
        
        # Use configurable model from settings
        self.current_model_name = settings.GEMINI_MODEL
        self.fallback_models = settings.FALLBACK_MODELS
        self.model = genai.GenerativeModel(
            f"models/{self.current_model_name}",
            generation_config=genai.GenerationConfig(
                temperature=0.0,
                max_output_tokens=1500,
            )
        )
        
        logger.info(f"Initialized Gemini client with primary model: {self.current_model_name}")
        logger.info(f"Fallback models: {', '.join(self.fallback_models)}")
    
    async def analyze_image_with_fallback(self, image_data: bytes) -> str:
        """
        Try to analyze image with primary model, fallback to alternatives if rate limited.
        
        Args:
            image_data: Image bytes to analyze
            
        Returns:
            JSON string with analysis results
            
        Raises:
            Exception: If all models are rate limited or other error occurs
        """
        last_error = None
        
        for model_name in self.fallback_models:
            try:
                # Switch to this model if different from current
                if model_name != self.current_model_name:
                    logger.info(f"Switching to fallback model: {model_name}")
                    self.model = genai.GenerativeModel(
                        f"models/{model_name}",
                        generation_config=genai.GenerationConfig(
                            temperature=0.0,
                            max_output_tokens=1500,
                        )
                    )
                    self.current_model_name = model_name
                
                # Try to analyze with this model
                logger.info(f"Attempting analysis with {model_name}...")
                result = await self.analyze_image(image_data)
                
                logger.info(f"✅ Analysis successful with {model_name}")
                return result
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a rate limit error
                if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                    logger.warning(f"⚠️ Model {model_name} is rate limited: {error_str[:100]}")
                    last_error = e
                    # Try next model in fallback list
                    continue
                else:
                    # Non-rate-limit error, raise immediately
                    logger.error(f"❌ Model {model_name} failed with non-rate-limit error: {error_str[:100]}")
                    raise
        
        # All models exhausted
        logger.error("❌ All models are rate limited!")
        raise Exception(f"All models rate limited. Last error: {last_error}")

    async def analyze_image(self, image_data: bytes) -> str:
        """
        Analyze image using Gemini Vision API with timeout handling.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            JSON string with analysis results
            
        Raises:
            TimeoutError: If API call exceeds configured timeout
            Exception: If API call fails for other reasons
        """
        try:
            # Prepare the image part for Gemini
            image_part = {
                "mime_type": "image/jpeg",
                "data": image_data
            }
            
            # Build the complete prompt with system instructions and user prompt
            full_prompt = f"{CANONICAL_SYSTEM_PROMPT}\n\n{build_user_prompt()}"
            
            # Call Gemini Vision API with timeout handling
            def sync_call():
                return self.model.generate_content([
                    full_prompt,
                    image_part
                ])
            
            # Apply timeout to prevent hanging requests
            response = await asyncio.wait_for(
                asyncio.to_thread(sync_call),
                timeout=settings.GEMINI_API_TIMEOUT
            )
            
            return response.text
        
        except asyncio.TimeoutError:
            logger.error(f"Gemini API call timed out after {settings.GEMINI_API_TIMEOUT}s")
            raise TimeoutError(f"Gemini Vision API call exceeded timeout of {settings.GEMINI_API_TIMEOUT}s")
        
        except Exception as e:
            logger.error(f"Gemini Vision API call failed: {e}")
            raise Exception(f"Failed to analyze image with Gemini: {e}") from e
