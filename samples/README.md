# Sample Files

This folder contains example inputs and outputs for testing the Lenskart Visual Measurement System.

## Files

### `sample_products.csv`
CSV file with 3 test products demonstrating different scenarios:
- **LK-231031**: 3 valid image URLs (full success)
- **LK-TEST02**: 1 valid image URL (single image)
- **LK-TEST03**: 1 invalid + 1 valid URL (partial failure)

### `sample_response_success.json`
Example of a fully successful API response showing:
- All 5 visual dimensions with scores and confidence
- Complete observable attributes (geometry, colors, texture, etc.)
- Per-image analysis for 3 images
- Variance metrics showing consistency
- All URLs validated successfully
- Quality flags all false (high quality analysis)

### `sample_response_partial.json`
Example of partial success where:
- 1 URL was invalid (404 error)
- Analysis completed with 1 valid image
- `quality_flags.single_image_only`: true
- `quality_flags.partial_analysis`: true
- Invalid URL details in `image_validation.invalid_urls`

### `sample_response_error.json`
Example of complete failure where:
- All 3 URLs were invalid (various error types)
- `error_type`: "all_urls_invalid"
- `processing_status`: "failed"
- All dimension scores are 0
- Detailed error information for each invalid URL

## Usage

### Testing with CSV

```bash
# Use the sample CSV for batch processing testing
# Upload via the web UI or process programmatically
```

### Understanding Response Formats

These JSON samples show the complete response structure including:
- **Assignment requirement 1**: Per-image analysis (non-deterministic AI handling)
- **Assignment requirement 2**: URL validation with specific error types
- **Production features**: Processing time, variance metrics, quality flags

### Error Types Demonstrated

- `not_found`: HTTP 404
- `timeout`: Request timeout
- `not_an_image`: Wrong content-type
