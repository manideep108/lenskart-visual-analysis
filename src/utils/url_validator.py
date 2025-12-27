from __future__ import annotations

import asyncio
import re
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

import httpx


logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of URL validation"""
    url: str
    is_valid: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None


# URL format regex (basic check for http/https URLs)
URL_PATTERN = re.compile(
    r'^https?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
    r'localhost|'  # localhost
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)


def is_valid_image_url(url: str) -> tuple[bool, str]:
    """
    Validate if URL is a proper image URL with stricter format checks.
    
    Returns:
        (is_valid, error_message)
    """
    from urllib.parse import urlparse
    
    # Check 1: URL not empty
    if not url or not url.strip():
        return False, "URL is empty"
    
    url = url.strip()
    
    # Check 2: URL length (too short = incomplete)
    if len(url) < 20:
        return False, "URL too short - appears incomplete"
    
    # Check 3: Valid URL format
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False, "Invalid URL format"
    except Exception:
        return False, "Could not parse URL"
    
    # Check 4: Must be http or https
    if parsed.scheme not in ['http', 'https']:
        return False, f"Invalid scheme: {parsed.scheme}"
    
    # Check 5: Must have proper domain
    if '.' not in parsed.netloc:
        return False, "Invalid domain"
    
    # Check 6: Path should not be too short for an image
    if len(parsed.path) < 5:
        return False, "URL path too short - likely incomplete"
    
    # Check 7: Should end with image extension OR have image-like path
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
    has_image_extension = any(url.lower().endswith(ext) for ext in image_extensions)
    
    # Also accept URLs with image keywords in path (for CDN URLs)
    image_keywords = ['image', 'img', 'photo', 'thumbnail', 'media', 'catalog', 'product']
    has_image_keyword = any(keyword in url.lower() for keyword in image_keywords)
    
    if not has_image_extension and not has_image_keyword:
        return False, "URL does not appear to be an image"
    
    # Check 8: Should not end with just a folder path
    if parsed.path.endswith('/') or len(parsed.path.split('/')[-1]) < 3:
        return False, "URL appears incomplete - ends with folder path"
    
    return True, ""


async def validate_image_url(url: str, timeout: int = 5) -> ValidationResult:
    """
    Validate image URL with multiple checks:
    1. Format check (strict validation)
    2. Reachability check (HEAD request)
    3. Content-type check (must be image/*)
    
    Args:
        url: URL to validate
        timeout: Request timeout in seconds
        
    Returns:
        ValidationResult with validation status and error details
    """
    
    # 1. Quick format validation (no network request)
    is_valid_format, format_error = is_valid_image_url(url)
    if not is_valid_format:
        return ValidationResult(
            url=url,
            is_valid=False,
            error_type="invalid_format",
            error_message=format_error
        )
    
    # 2. Reachability and content-type check
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # Use HEAD request to check without downloading full image
            response = await client.head(url)
            
            # Check if URL is reachable
            if response.status_code == 404:
                return ValidationResult(
                    url=url,
                    is_valid=False,
                    error_type="not_found",
                    error_message=f"URL returned 404 Not Found"
                )
            
            if response.status_code == 403:
                return ValidationResult(
                    url=url,
                    is_valid=False,
                    error_type="forbidden",
                    error_message=f"URL returned 403 Forbidden (access denied)"
                )
            
            if response.status_code >= 400:
                return ValidationResult(
                    url=url,
                    is_valid=False,
                    error_type="http_error",
                    error_message=f"URL returned HTTP {response.status_code}"
                )
            
            # 3. Content-type validation
            content_type = response.headers.get('content-type', '').lower()
            
            # Some CDNs don't return content-type for HEAD, so only fail if explicitly not an image
            if content_type:
                if not content_type.startswith('image/'):
                    # Only fail if it's explicitly text/html or other non-image type
                    if any(t in content_type for t in ['text', 'html', 'json', 'xml']):
                        return ValidationResult(
                            url=url,
                            is_valid=False,
                            error_type="not_an_image",
                            error_message=f"Content-Type is '{content_type}', not an image"
                        )
            
            # All checks passed
            return ValidationResult(
                url=url,
                is_valid=True,
                error_type=None,
                error_message=None
            )
    
    except httpx.TimeoutException:
        return ValidationResult(
            url=url,
            is_valid=False,
            error_type="timeout",
            error_message=f"Request timed out after {timeout} seconds"
        )
    
    except httpx.ConnectError:
        return ValidationResult(
            url=url,
            is_valid=False,
            error_type="connection_error",
            error_message="Could not connect to URL (DNS resolution failed or host unreachable)"
        )
    
    except Exception as e:
        logger.error(f"Unexpected error validating URL {url}: {e}")
        return ValidationResult(
            url=url,
            is_valid=False,
            error_type="unknown_error",
            error_message=f"Validation failed: {str(e)}"
        )


async def validate_image_urls(urls: List[str], timeout: int = 5) -> Dict:
    """
    Validate multiple URLs concurrently.
    
    Args:
        urls: List of URLs to validate
        timeout: Request timeout in seconds per URL
        
    Returns:
        Dictionary with validation results:
        {
            "valid_urls": ["http://example.com/img1.jpg", ...],
            "invalid_urls": [
                {
                    "url": "http://example.com/notfound.jpg",
                    "error_type": "not_found",
                    "error_message": "URL returned 404 Not Found"
                },
                ...
            ],
            "total": 3,
            "valid_count": 2,
            "invalid_count": 1
        }
    """
    
    # Validate all URLs concurrently
    validation_tasks = [validate_image_url(url, timeout) for url in urls]
    results = await asyncio.gather(*validation_tasks)
    
    # Separate valid and invalid URLs
    valid_urls = []
    invalid_urls = []
    
    for result in results:
        if result.is_valid:
            valid_urls.append(result.url)
        else:
            invalid_urls.append({
                "url": result.url,
                "error_type": result.error_type,
                "error_message": result.error_message
            })
    
    return {
        "valid_urls": valid_urls,
        "invalid_urls": invalid_urls,
        "total": len(urls),
        "valid_count": len(valid_urls),
        "invalid_count": len(invalid_urls)
    }
