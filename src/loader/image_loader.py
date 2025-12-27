from __future__ import annotations

import logging
import httpx


logger = logging.getLogger(__name__)


class ImageLoader:
    async def load(self, url: str) -> bytes | None:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                }
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    return response.content
                else:
                    logger.warning(f"Failed to load image from {url}: HTTP {response.status_code}")
                    return None
        except Exception as e:
            logger.warning(f"Failed to load image from {url}: {e}")
            return None
