# Lenskart Visual Measurement System

AI-powered visual product measurement system that analyzes eyewear images and outputs structured, machine-readable measurements of observable visual properties.

## Features

- **AI Vision Analysis**: Uses Google Gemini Vision API for accurate product analysis
- **Model Fallback System**: Automatically switches between 3 Gemini models when rate limits are hit
- **5 Visual Dimensions**: Gender Expression, Visual Weight, Embellishment, Unconventionality, Formality
- **Observable Attributes**: Frame geometry, transparency, colors, texture, etc.
- **Batch Processing**: Upload Excel files with multiple products
- **Advanced URL Validation**: 8 validation checks including timeout detection and incomplete URL handling
- **Timing Breakdown**: Detailed performance metrics for each processing step
- **Quality Score Calculation**: 0.0-1.0 metric based on confidence and variance
- **Per-Image Analysis**: Shows individual results before aggregation
- **Variance Tracking**: Demonstrates handling of non-deterministic AI outputs
- **Rate Limit Handling**: Smart retry button with countdown timer
- **Demo Mode**: Test with realistic simulated data when rate limited
- **Interactive UI**: Web interface with high-visibility radar charts, image previews, and export options

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:

```
GEMINI_API_KEY=your_actual_api_key_here
```

Get a free API key from: https://ai.google.dev/

### 3. Run the Server

```bash
uvicorn src.server:app --reload
```

Server runs at: http://localhost:8000

## API Quota Limits (Free Tier)

The free tier has strict limits:
- **20 requests per day (RPD) per model**
- **5 requests per minute (RPM)**

### Model Fallback System

To maximize uptime, the system automatically switches between models:
1. **Primary**: `gemini-2.5-flash` (fast, efficient)
2. **Fallback 1**: `gemini-2.5-flash-lite` (lighter, faster)
3. **Fallback 2**: `gemini-3-flash-preview` (preview model)

Each model has its own 20 RPD quota, effectively tripling your daily capacity.

### Default Settings

Optimized for free tier:
- 15 second delay between API calls
- Maximum 3 images per product
- 2 retry attempts maximum

To change these, update your `.env` file.

## Usage

### Web Interface

1. Open http://localhost:8000 in your browser
2. Enter Product ID and image URLs (one per line)
3. Click "Analyze Product"
4. View results: dimensions, confidence, per-image analysis, variance metrics
5. Export to CSV or JSON

### API Endpoint

**Single Product Analysis:**

```bash
POST /analyze
Content-Type: application/json

{
  "product_id": "231031",
  "image_urls": [
    "https://example.com/image1.jpg",
    "https://example.com/image2.jpg"
  ]
}
```

**Batch Processing:**

```bash
POST /analyze-batch
Content-Type: application/json

[
  {
    "product_id": "231031",
    "image_urls": ["https://..."]
}
```

## Sample Input/Output

### Sample Input

**Product ID**: `LK-231031`

**Image URLs** (from `samples/sample_products.csv`):
```
https://static5.lenskart.com/media/catalog/product/pro/1/thumbnail/1325x636/9df78eab33525d08d6e5fb8d27136e95/l/i/lenskart-lk-e17572me-c2-s55-golden-brown-eyeglasses_dsc1526_09_11_2024.jpg
https://static5.lenskart.com/media/catalog/product/pro/1/thumbnail/1325x636/9df78eab33525d08d6e5fb8d27136e95/l/i/lenskart-lk-e17572me-c2-s55-golden-brown-eyeglasses_dsc1527_09_11_2024.jpg
https://static5.lenskart.com/media/catalog/product/pro/1/thumbnail/1325x636/9df78eab33525d08d6e5fb8d27136e95/l/i/lenskart-lk-e17572me-c2-s55-golden-brown-eyeglasses_dsc1525_09_11_2024.jpg
```

### Sample Output

See complete examples in `samples/` folder:
- `sample_response_success.json` - Successful 3-image analysis
- `sample_response_partial.json` - Partial success (1 invalid URL)
- `sample_response_error.json` - Rate limit error with retry suggestions
  },
  {
    "product_id": "231032",
    "image_urls": ["https://..."]
  }
]
```

## Response Schema

```json
{
  "product_id": "231031",
  "processing_status": "success",
  "visual_dimensions": {
    "gender_expression": {"score": 2.5, "confidence": 0.89},
    "visual_weight": {"score": -1.0, "confidence": 0.85},
    ...
  },
  "aggregate_confidence": 0.87,
  "quality_score": 0.82,
  "image_validation": {
    "total_provided": 3,
    "valid_count": 3,
    "invalid_count": 0,
    "invalid_urls": []
  },
  "variance_metrics": {
    "gender_expression": 0.23,
    "visual_weight": 0.45,
    ...
  },
  "per_image_analysis": [
    {
      "image_url": "https://...",
      "visual_dimensions": {...},
      "processing_time_ms": 2340
    }
  ],
  "quality_flags": {
    "low_confidence": false,
    "high_variance": false,
    "single_image_only": false,
    "partial_analysis": false
  },
  "timing_breakdown": {
    "url_validation_ms": 245,
    "image_fetch_ms": 1820,
    "gemini_api_ms": 4560,
    "aggregation_ms": 12,
    "total_ms": 6637
  },
  "model_used": "gemini-2.5-flash"
}
```

## Assignment Requirements Addressed

### ✅ Non-Deterministic AI Handling
- Per-image analysis stored before aggregation
- Variance metrics calculated across images
- Confidence-weighted averaging

### ✅ Invalid URL Handling
- Pre-validation with 8 comprehensive checks
- Detects incomplete URLs, timeouts, DNS errors, wrong content types
- Specific error types: `invalid_format`, `not_found`, `timeout`, `not_an_image`, `dns_error`
- Graceful fallback - continues with valid URLs

### ✅ Production-Ready Features
- Model fallback system (3 models, auto-switching)
- Rate limiting with retry UI (prevents API throttling)
- Error handling (6 structured error types)
- Image capping (max 3 images per product for free tier)
- Comprehensive timing breakdown (5 metrics)
- Quality score calculation
- Processing time tracking
- Schema versioning
- Color deduplication

## Limitations

### Free Tier Constraints
- **20 requests/day per model** (60 total with 3-model fallback)
- **5 requests/minute** rate limit
- 15-second delays between calls impact speed
- Maximum 3 images per product to conserve quota

### Technical Limitations
- **AI Non-Determinism**: Same image may produce slightly different scores (variance tracking mitigates this)
- **Image Quality Dependent**: Blurry, small, or poorly lit images reduce accuracy
- **URL Validation Timeout**: 3-second timeout may miss slow servers
- **No Real-Time Analysis**: Sequential processing means batch jobs take time

### Scope Limitations
- **Eyewear Only**: Optimized for glasses/sunglasses, not other products
- **Visual Analysis Only**: Cannot measure physical dimensions (mm/cm)
- **No Brand Recognition**: Focuses on visual properties, not brand identification
- **No Model Comparison**: Results from different Gemini models may vary slightly

## Future Improvements

### High Priority
1. **Result Caching**
   - Cache analysis by image URL hash (MD5)
   - 24-hour TTL with smart invalidation
   - Impact: 90% latency reduction on repeated requests

2. **Paid API Tier**
   - Upgrade to Gemini Pro for higher quotas (1500 RPD)
   - Faster analysis without long delays
   - Impact: Better user experience, higher throughput

3. **Comprehensive Testing**
   - Unit tests for each module (pytest)
   - Integration tests for full pipeline
   - Snapshot tests for prompt engineering
   - Impact: Confidence in code changes

### Medium Priority
4. **Image Preprocessing**
   - Resize to standard dimensions
   - Auto-enhance low-quality images
   - Impact: 10-15% consistency improvement

5. **Advanced Analytics**
   - Store analysis history in database
   - Trend analysis across products
   - A/B testing different prompts
   - Impact: Continuous improvement insights

6. **Multi-Provider Ensemble**
   - Combine Gemini + GPT-4V + Claude
   - Average predictions for better accuracy
   - Impact: 20-30% accuracy improvement (3x cost)

### Low Priority
7. **Parallel Processing**
   - Analyze multiple images concurrently
   - Requires paid tier to avoid rate limits
   - Impact: 3x speed improvement

8. **Advanced Error Recovery**
   - Exponential backoff with jitter
   - Circuit breaker pattern
   - Impact: Better resilience under load

## Project Structure

```
lenskart/
├── src/
│   ├── pipeline/          # Core processing pipeline
│   ├── vision/            # AI vision clients
│   ├── schema/            # Data models
│   ├── utils/             # URL validation, etc.
│   ├── aggregation/       # Result aggregation
│   ├── loader/            # Image loading
│   └── server.py          # FastAPI server
├── frontend/
│   └── index.html         # Web UI
├── requirements.txt
├── .env.example
└── README.md
```

## Technology Stack

- **Backend**: FastAPI, Python 3.8+
- **AI**: Google Gemini 2.5 Flash Vision API
- **Frontend**: HTML, Tailwind CSS, Chart.js
- **Data**: Pydantic for validation, openpyxl for Excel

## License

MIT
