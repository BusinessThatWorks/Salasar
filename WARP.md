# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Architecture Overview

Policy Reader is a **Frappe ERPNext application** that processes insurance policy documents using OCR and AI to extract structured data. The system supports both Motor and Health insurance policies with dual processing modes (local OCR + RunPod API) and background job processing.

### Core Components

**DocTypes (Database Models):**

- **Policy Document** - Main entity storing uploaded PDFs, processing status, and extracted fields
- **Policy Reader Settings** - System configuration including API keys, RunPod settings, and processing parameters

**Service Layer:**

- **ProcessingService** - Orchestrates document processing, choosing between RunPod API and local OCR
- **RunPodService** - Manages RunPod API integration with health checking and failover
- **ExtractionService** - Handles field extraction from text using Claude API with prompts from Policy Reader Settings

**Background Processing:**

- Async processing via `frappe.enqueue()` with real-time status updates
- Scheduled tasks for monitoring stuck documents and RunPod health
- Comprehensive error handling with automatic retries

### Processing Architecture

The system follows a **hybrid processing approach**:

1. **Text Extraction** - RunPod API (primary) with local OCR fallback
2. **Field Extraction** - Claude API processes extracted text into structured fields
3. **Data Storage** - Both JSON blob and individual database fields for reporting
4. **User Experience** - Real-time updates, manual field editing, visual processing indicators

## Development Commands

### Frappe Bench Commands

Since this is a Frappe application, all development happens within the **bench** environment:

```bash
# Navigate to the bench directory (parent of apps/policy_reader)
cd /path/to/your/bench

# Install the app
bench get-app https://github.com/your-repo/policy_reader --branch develop
bench install-app policy_reader

# Development workflow
bench migrate                    # Apply database changes
bench clear-cache               # Clear Frappe cache after code changes
bench restart                   # Restart all services
bench start                     # Start development server

# Run specific site
bench --site [site-name] migrate
bench --site [site-name] console  # Python console with Frappe context
```

### Code Quality & Testing

```bash
# Pre-commit setup (run once)
cd apps/policy_reader
pre-commit install

# Manual code quality checks
pre-commit run --all-files      # Run all pre-commit hooks
ruff check .                    # Lint Python code
ruff format .                   # Format Python code
```

### Testing Commands

```bash
# Run tests
bench --site [site-name] run-tests --app policy_reader

# Run specific test
bench --site [site-name] run-tests --app policy_reader --doctype "Policy Document"

# RunPod integration testing
python3 -c "from policy_reader.policy_reader.services.runpod_service import RunPodService; service = RunPodService(); print(service.check_health())"
```

### Development Environment Setup

```bash
# Install dependencies in Frappe environment
./env/bin/pip install paddlepaddle paddleocr requests

# Set API keys (choose one method)
export ANTHROPIC_API_KEY="sk-ant-..."

# Or add to site_config.json
echo '{"anthropic_api_key": "sk-ant-..."}' >> sites/[site]/site_config.json
```

## Key Development Patterns

### Frappe Framework Usage

**Always use Frappe's built-in utilities:**

- **File handling**: `frappe.get_doc("File", file_name)`, `file_doc.get_full_path()`
- **Configuration**: `frappe.conf.get()`, `frappe.get_single()`
- **Database**: `frappe.get_doc()`, `frappe.get_all()`, `frappe.db.commit()`
- **Error handling**: `frappe.throw()`, `frappe.log_error()`
- **JSON operations**: `frappe.parse_json()`, `frappe.as_json()`
- **Background jobs**: `frappe.enqueue(method, queue='short', timeout=180)`
- **Real-time updates**: `frappe.publish_realtime(event, message, user)`

### Background Processing Pattern

```python
# Enqueue background job
frappe.enqueue(
    method="policy_reader.policy_reader.doctype.policy_document.policy_document.process_policy_background",
    queue='short',
    timeout=180,
    job_name=f"policy_reader_{doc.name}_{timestamp}",
    doc_name=doc.name
)

# Real-time updates
frappe.publish_realtime(
    event="policy_processing_complete",
    message={"doc_name": doc.name, "status": "Completed"},
    user=doc.owner
)
```

### Service Integration Pattern

```python
# Service instantiation with dependency injection
processing_service = ProcessingService(policy_document=self)
result = processing_service.choose_processing_method(settings)

# Error handling with proper logging
try:
    result = service_method()
    if not result.get("success"):
        frappe.log_error(f"Service failed: {result.get('error')}", "Service Error")
except Exception as e:
    frappe.log_error(f"System error: {str(e)}", "System Error")
    frappe.throw(f"Operation failed: {str(e)}")
```

## Configuration & Deployment

### Required Environment Variables

```bash
# API Keys
ANTHROPIC_API_KEY="sk-ant-..."        # Claude API for field extraction

# RunPod Configuration (optional)
RUNPOD_POD_ID="pod-id"               # RunPod instance ID
RUNPOD_PORT="8000"                   # RunPod service port
RUNPOD_API_SECRET="secret"           # RunPod API authentication
```

### Settings Configuration

Access **Policy Reader Settings** via Frappe UI for:

- Anthropic API key management
- RunPod endpoint configuration
- Processing parameters (timeout, confidence threshold, max pages)
- Field mapping synchronization

### Scheduled Tasks

The system runs automated maintenance tasks:

- **Every 3 minutes**: Monitor and retry stuck policy documents
- **Every 10 minutes**: Check RunPod API health status

## Important Context for AI Development

### Critical Implementation Notes

1. **Phase-based Development**: This is a mature implementation with background processing, RunPod integration, and comprehensive error handling. Refer to `policy_reader/claude-docs/CLAUDE.md` for the complete implementation context.

2. **Dual Processing Architecture**: The system intelligently chooses between RunPod API and local OCR based on health checks and response times, with automatic fallback.

3. **Field Storage Strategy**: Extracted data is stored both as JSON (for backward compatibility) and as individual database fields (for reporting and queries).

4. **Real-time User Experience**: Background processing with real-time status updates, visual indicators for field states, and comprehensive error feedback.

### Development Guidelines

- **Never reinvent Frappe functionality** - always use framework utilities
- **Follow service-oriented architecture** - keep business logic in service classes
- **Maintain backward compatibility** when adding new features
- **Use proper error handling** with both system logging and user-friendly messages
- **Test both processing methods** - RunPod API and local OCR fallback
- **Validate file access** before processing to prevent background job failures

### Files to Reference

- `policy_reader/claude-docs/CLAUDE.md` - Complete implementation guide and context
- `policy_reader/claude-docs/fixes.md` - Known issues and their resolutions
- `policy_reader/policy_reader/doctype/policy_document/policy_document.py` - Main document controller
- `policy_reader/policy_reader/services/` - Service layer implementations

This codebase represents a production-ready Frappe application with sophisticated document processing capabilities, background job management, and dual-mode API integration.

## Recent Updates (January 2025)

### Motor Policy DocType - SAIBA ERP Integration

**Changes Made:**

- **Updated Motor Policy DocType structure** with 37 fields organized into 4 sections for SAIBA ERP compatibility
- **Added 21 new fields** including customer codes, business information, and enhanced vehicle data
- **Updated field mapping service** to handle new field structure with proper data type mappings
- **Successfully migrated database** using `bench migrate` - all new fields are live

**New Field Categories:**

1. **Business Information (7 fields)** - Manual entry fields for ERP integration:

   - Customer Code, PolicyBiz Type, Insurer Branch Code, New/Renewal
   - Payment Mode, Bank Name, Payment Transaction No

2. **Enhanced Policy Information (11 fields)** - OCR extracted with proper datetime/numeric types:

   - Policy dates, financial amounts (Sum Insured, Net/OD Premium, TP Premium, GST, NCB)

3. **Detailed Vehicle Information (16 fields)** - Complete vehicle specification capture:
   - Make/Model (separate fields), Year of Manufacture, Engine details, RTO Code, Vehicle Category

**Data Source Mapping:**

- **Manual Entry**: Business codes and payment information (not in policy copy)
- **OCR Extracted**: All policy and vehicle details from document processing

**Migration Status:**

- ✅ DocType structure updated and migrated to database
- ✅ Field mapping service updated for new structure
- ✅ Backward compatibility maintained
- ⚠️ **Missing**: Customer information fields (Name, Address, Contact details) - need to be added

**Usage:**

- OCR processing automatically populates extractable fields
- Users manually enter business/administrative information
- Ready for SAIBA ERP API integration (future development)
