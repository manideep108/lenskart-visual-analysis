from __future__ import annotations

import asyncio
import argparse
import logging
import json
import os
import sys

from src.loader.dataset_loader import DatasetLoader
from src.loader.image_loader import ImageLoader
from src.vision.gemini_client import GeminiVisionClient
from src.aggregation.aggregator import Aggregator
from src.pipeline.processor import ProductProcessor


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    
    parser = argparse.ArgumentParser(
        description="Lenskart Visual Measurement System"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="data/input/products.csv",
        help="Path to input CSV file"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/output/results.json",
        help="Path to output JSON file"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of products to process"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Gemini API Key (overrides environment variable)"
    )
    
    args = parser.parse_args()
    
    if args.api_key:
        os.environ["GEMINI_API_KEY"] = args.api_key
    
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY is not set. Please provide it via --api-key or environment variable.")
        sys.exit(1)
    
    vision_client = GeminiVisionClient()
    
    dataset_loader = DatasetLoader()
    image_loader = ImageLoader()
    aggregator = Aggregator()
    processor = ProductProcessor(vision_client, image_loader, aggregator)
    
    results = []
    count = 0
    
    for product in dataset_loader.load_products(args.input):
        if args.limit and count >= args.limit:
            break
        
        logger.info(f"Processing Product ID: {product.product_id}")
        
        result = await processor.process_product(product)
        results.append(result.model_dump())
        
        count += 1
        logger.info(f"Completed {count} products")
    
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Processing complete. Results saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
