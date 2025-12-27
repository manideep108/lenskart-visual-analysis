import asyncio
import logging
import re

logger = logging.getLogger(__name__)


async def retry_with_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0
):
    """
    Retry async function with exponential backoff.
    Parses retry_after from rate limit errors.
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
        max_delay: Maximum delay cap in seconds
        
    Returns:
        Result from successful function call
        
    Raises:
        Exception: If all retries exhausted
    """
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            error_str = str(e).lower()
            
            if "429" in str(e) or "rate" in error_str or "quota" in error_str:
                # Parse retry_after from error message if available
                delay = parse_retry_delay(str(e), default=base_delay * (2 ** attempt))
                delay = min(delay, max_delay)
                
                if attempt < max_retries:
                    logger.warning(
                        f"Rate limited. Retry {attempt + 1}/{max_retries} in {delay:.1f}s. "
                        f"Error: {str(e)[:100]}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Max retries ({max_retries}) exhausted for rate limit")
                    raise
            else:
                # Non-rate-limit error, don't retry
                raise


def parse_retry_delay(error_message: str, default: float = 2.0) -> float:
    """
    Extract retry delay from error message.
    
    Examples:
        "Please retry in 37.395680969s" -> 37.4
        "retry after 60 seconds" -> 60.0
        
    Args:
        error_message: Error message from API
        default: Default delay if parsing fails
        
    Returns:
        Delay in seconds
    """
    # Try to extract seconds from error message
    # Pattern 1: "retry in 37.395680969s" or "retry in 37s"
    match = re.search(r"retry in ([\d.]+)s?", error_message, re.IGNORECASE)
    if match:
        return float(match.group(1))
    
    # Pattern 2: "retry after 60 seconds"
    match = re.search(r"retry after ([\d.]+)\s*seconds?", error_message, re.IGNORECASE)
    if match:
        return float(match.group(1))
    
    # Could not parse, use default
    logger.debug(f"Could not parse retry delay from: {error_message[:100]}")
    return default
