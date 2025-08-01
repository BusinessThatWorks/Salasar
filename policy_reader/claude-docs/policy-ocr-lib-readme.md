# Policy OCR Library

A simple, efficient Python library for extracting structured data from insurance policy documents using OCR and AI-powered field extraction.

## Features

- **High-performance OCR**: Uses PaddleOCR with optimizations for document processing
- **AI-powered extraction**: Leverages Anthropic's Claude for intelligent field extraction
- **Parallel processing**: Processes multiple pages concurrently for speed
- **Smart optimization**: Early termination, fast mode, and configurable limits
- **Multiple policy types**: Support for motor, health, and custom policy types
- **Progress tracking**: Real-time callbacks for processing status
- **Easy configuration**: Environment variables or programmatic configuration

## Installation

```bash
pip install policy-ocr
```

## Quick Start

### Basic Usage

```python
from policy_ocr import PolicyProcessor

# Initialize processor
processor = PolicyProcessor(claude_api_key="your-api-key")

# Process a policy document
result = processor.process_policy(
    file_path="path/to/policy.pdf",
    policy_type="motor"
)

if result["success"]:
    print("Extracted fields:", result["extracted_fields"])
    print("Processing time:", result["processing_time"])
else:
    print("Error:", result["error"])
```

### Advanced Configuration

```python
from policy_ocr import PolicyProcessor, OCRConfig

# Create custom configuration
config = OCRConfig(
    claude_api_key="your-api-key",
    fast_mode=True,           # Process only first 3 pages
    max_pages=5,              # Limit to 5 pages
    parallel_processing=True,  # Enable parallel processing
    confidence_threshold=0.7   # Higher confidence threshold
)

processor = PolicyProcessor(config)

# Process with progress callback
def progress_callback(status):
    print(f"Status: {status['status']}, Message: {status['message']}")

result = processor.process_policy(
    file_path="policy.pdf",
    policy_type="motor",
    progress_callback=progress_callback
)
```

### Environment Configuration

Set environment variables instead of passing API keys in code:

```bash
export ANTHROPIC_API_KEY="your-api-key"
export CLAUDE_MODEL="claude-sonnet-4-20250514"  # Optional: specify Claude model
export OCR_FAST_MODE="true"
export OCR_MAX_PAGES="3"
```

```python
from policy_ocr import PolicyProcessor, OCRConfig

# Load configuration from environment
config = OCRConfig.from_env()
processor = PolicyProcessor(config)
```

## Supported Policy Types

- **Motor Insurance**: Extracts policy number, vehicle details, coverage dates, etc.
- **Health Insurance**: Extracts policy number, insured details, coverage amounts, etc.
- **Custom Types**: Add your own policy types with custom field definitions

## Performance Optimizations

- **Fast Mode**: Process only first 3 pages (good for motor policies)
- **Parallel Processing**: Process multiple pages simultaneously
- **Early Termination**: Stop when enough fields are found
- **Image Optimization**: Optimized image resolution and compression
- **Model Persistence**: Reuse OCR models across multiple documents

## API Reference

### PolicyProcessor

Main class for processing policy documents.

```python
PolicyProcessor(config: Optional[OCRConfig] = None)
```

#### Methods

- `process_policy(file_path, policy_type="motor", progress_callback=None)`: Process a policy document

### OCRConfig

Configuration class for OCR processing.

```python
OCRConfig(
    claude_api_key: Optional[str] = None,
    claude_model: str = "claude-sonnet-4-20250514",
    fast_mode: bool = False,
    max_pages: Optional[int] = None,
    parallel_processing: bool = True,
    image_resolution_scale: float = 1.2,
    image_quality: int = 85,
    confidence_threshold: float = 0.5,
    early_termination: bool = True,
    enable_logging: bool = True
)
```

#### Class Methods

- `OCRConfig.from_env()`: Create configuration from environment variables
- `OCRConfig.from_dict(config_dict)`: Create configuration from dictionary

## Field Extraction

### Motor Insurance Fields

- Policy Number
- Insured Name
- Vehicle Number
- Chassis Number
- Engine Number
- From (Start Date)
- To (End Date)
- Premium Amount
- Sum Insured
- Make / Model

### Health Insurance Fields

- Policy Number
- Insured Name
- Sum Insured
- Policy Start Date
- Policy End Date

## Error Handling

The library returns structured results with success/error status:

```python
{
    "success": True/False,
    "extracted_fields": {...},
    "processing_time": 45.2,
    "pages_processed": 3,
    "error": None or "error message"
}
```

## Requirements

- Python 3.8+
- Anthropic API key for Claude
- See `requirements.txt` for full dependencies

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## Support

For issues and questions, please open an issue on GitHub.