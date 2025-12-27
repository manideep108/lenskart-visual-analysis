from __future__ import annotations

import abc
import os
import base64
import logging
from openai import AsyncOpenAI

from src.vision.prompts import CANONICAL_SYSTEM_PROMPT, build_user_prompt


logger = logging.getLogger(__name__)


class VisionClient(abc.ABC):
    @abc.abstractmethod
    async def analyze_image(self, image_data: bytes) -> str:
        ...


class OpenAIVisionClient(VisionClient):
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.client = AsyncOpenAI(api_key=api_key)

    async def analyze_image(self, image_data: bytes) -> str:
        try:
            base64_image = base64.b64encode(image_data).decode("utf-8")
            
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": CANONICAL_SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": build_user_prompt()},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    }
                ]
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Vision API call failed: {e}")
            raise Exception(f"Failed to analyze image: {e}") from e
