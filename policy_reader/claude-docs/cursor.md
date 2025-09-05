# Policy Reader - Current Architecture & Future Policy Creation Service

## Overview

This document provides context for the current Policy Reader architecture and outlines the plan for building a separate Policy Creation Service.

## Current Architecture (Post-Refactoring)

### Core Components

#### 1. Policy Document (Simplified)

**Location**: `policy_reader/doctype/policy_document/`
**Purpose**: Document processing and field extraction only
**Key Methods**:

- `process_policy()` - Enqueues background processing
- `process_policy_internal()` - Main processing workflow
- `extract_fields_with_claude()` - Uses ExtractionService for AI extraction
- `ai_extract_fields_from_ocr()` - Rerun extraction on stored OCR text

**Fields** (Organized in Tabs):

**Document Information Tab**:

- `title` - Document title
- `policy_file` - PDF file attachment
- `policy_type` - Motor/Health selection
- `status` - Processing status
- `processing_method` - RunPod/Local OCR method
- `processing_time` - Processing duration
- `ocr_confidence` - OCR confidence score
- `manual_review_recommended` - Quality flag
- `enhancement_applied` - Image enhancement flag

**Extraction Results Tab**:

- `extracted_fields` (JSON) - Raw extracted data
- `raw_ocr_text` - OCR text for re-extraction
- `used_prompt` - Prompt used for extraction

**Technical Details Tab**:

- `error_message` - Processing errors
- `confidence_data` (JSON) - Detailed confidence metrics

**Removed**: All policy creation logic, motor_policy/health_policy link fields

#### 2. ExtractionService

**Location**: `policy_reader/services/extraction_service.py`
**Purpose**: Handles AI-powered field extraction
**Key Methods**:

- `extract_fields_from_text()` - Main extraction method
- `_get_extraction_prompt()` - Gets prompts from Policy Reader Settings
- `_call_claude_api()` - Makes Claude API calls
- `_process_claude_response()` - Processes API responses
- `get_field_mapping_for_policy_type()` - Backward compatibility

#### 3. Policy Reader Settings

**Location**: `policy_reader/doctype/policy_reader_settings/`
**Purpose**: Configuration and prompt generation
**Key Features**:

- API configuration (Anthropic, RunPod)
- Dynamic prompt generation from DocType fields
- Field mapping caching
- Processing settings (timeout, confidence, etc.)

**Prompt Generation Methods**:

- `build_dynamic_extraction_prompt()` - Builds prompts from DocType
- `_build_motor_extraction_prompt()` - Motor-specific prompts
- `_build_health_extraction_prompt()` - Health-specific prompts
- `get_cached_extraction_prompt()` - Cached prompt retrieval

#### 4. ProcessingService

**Location**: `policy_reader/services/processing_service.py`
**Purpose**: Orchestrates document processing (OCR)
**Key Methods**:

- `choose_processing_method()` - RunPod vs Local
- `extract_text_with_runpod()` - RunPod API processing
- `extract_text_with_local()` - Local OCR processing

#### 5. RunPodService

**Location**: `policy_reader/services/runpod_service.py`
**Purpose**: RunPod API integration
**Key Methods**:

- `check_health()` - Health monitoring
- `extract_text()` - Text extraction via RunPod

### Current Data Flow

```
1. User uploads PDF → Policy Document
2. Policy Document → ProcessingService (OCR)
3. ProcessingService → RunPodService OR Local OCR
4. Policy Document → ExtractionService (Field extraction)
5. ExtractionService → Policy Reader Settings (Get prompt)
6. ExtractionService → Claude API (Extract fields)
7. Policy Document stores extracted_fields (JSON)
```

### Removed Components

#### Deleted Services

- **FieldMappingService** - Functionality moved to ExtractionService
- **TemplateService** - Unused insurer-specific template system
- **policy_reader_templates module** - Entire module removed

#### Removed Policy Creation Logic

- `populate_individual_fields()` - Policy record creation orchestrator
- `create_motor_policy_record()` - Motor policy creation (~200 lines)
- `create_health_policy_record()` - Health policy creation (~80 lines)
- `create_policy_record()` - Manual policy creation method
- Field conversion methods (`_convert_field_value`, `_normalize_select_value`, etc.)
- Policy validation methods (`_pre_validate_policy_fields`, `_analyze_field_mismatch`)

## Future Policy Creation Service

### Planned Architecture

#### Policy Creation Service

**Purpose**: Create actual Motor/Health Policy records from extracted fields
**Location**: `policy_reader/services/policy_creation_service.py` (to be created)

**Key Responsibilities**:

1. **Field Mapping**: Map extracted fields to policy DocType fields
2. **Data Validation**: Validate extracted data against policy requirements
3. **Type Conversion**: Convert extracted strings to appropriate field types
4. **Policy Creation**: Create and save Motor/Health Policy records
5. **Error Handling**: Handle validation errors and field mismatches

**Key Methods** (to be implemented):

- `create_policy_from_extraction(policy_document, policy_type)`
- `map_extracted_fields(extracted_data, policy_type)`
- `validate_policy_data(policy_data, policy_type)`
- `convert_field_values(policy_data, policy_type)`
- `create_motor_policy(extracted_data, policy_document)`
- `create_health_policy(extracted_data, policy_document)`

#### Integration Points

**From Policy Document**:

```python
# In Policy Document
@frappe.whitelist()
def create_policy_record(self):
    """Create policy record from extracted fields"""
    from policy_reader.services.policy_creation_service import PolicyCreationService

    creation_service = PolicyCreationService()
    return creation_service.create_policy_from_extraction(self, self.policy_type)
```

**Field Mapping Strategy**:

- Use Policy Reader Settings cached field mappings
- Handle field aliases and variations
- Support insurer-specific mappings (if needed)
- Validate field types and constraints

**Data Flow** (Future):

```
Policy Document (with extracted_fields)
    ↓
Policy Creation Service
    ↓
Field Mapping & Validation
    ↓
Type Conversion
    ↓
Motor/Health Policy Record Creation
    ↓
Link back to Policy Document
```

### Key Considerations for Policy Creation Service

#### 1. Field Mapping

- **Source**: Policy Reader Settings cached mappings
- **Strategy**: Label → fieldname mapping with aliases
- **Validation**: Ensure all required fields are present
- **Flexibility**: Support for field variations and insurer-specific mappings

#### 2. Data Validation

- **Required Fields**: Validate against DocType requirements
- **Field Types**: Ensure proper data types (Date, Currency, Select, etc.)
- **Business Rules**: Validate against policy-specific business logic
- **Error Handling**: Graceful handling of validation failures

#### 3. Type Conversion

- **Dates**: DD/MM/YYYY format conversion
- **Currency**: Remove symbols, convert to float
- **Select Fields**: Normalize to exact option values
- **Numbers**: Extract digits, handle descriptive text

#### 4. Error Handling

- **Partial Success**: Create policy with available fields
- **Validation Errors**: Clear error messages for missing/invalid fields
- **Field Mismatches**: Log and handle unmapped fields
- **Rollback**: Proper cleanup on creation failures

#### 5. Integration

- **Policy Document**: Link created policy back to document
- **User Feedback**: Clear success/error messages
- **Logging**: Comprehensive logging for debugging
- **Background Processing**: Support for async policy creation

### Benefits of Separate Service

1. **Single Responsibility**: Policy Document focuses on extraction, Creation Service on policy creation
2. **Reusability**: Creation service can be used by other parts of the system
3. **Testability**: Easier to test policy creation logic in isolation
4. **Maintainability**: Clear separation of concerns
5. **Flexibility**: Easy to modify creation logic without affecting extraction

### Migration Notes

- **Field Mappings**: Already available in Policy Reader Settings
- **Extraction Logic**: Fully functional and tested
- **Policy DocTypes**: Motor Policy and Health Policy exist and are ready
- **Validation Logic**: Can be extracted from removed methods if needed
- **Type Conversion**: Can be recreated based on DocType field types

## Current Status

✅ **Completed**:

- Policy Document simplified to focus on extraction only
- ExtractionService created and integrated
- FieldMappingService and TemplateService removed
- Policy Reader Settings enhanced with prompt generation
- Migration completed successfully

🔄 **Next Steps**:

- Create Policy Creation Service
- Implement field mapping and validation
- Add policy creation methods to Policy Document
- Test end-to-end workflow
- Add user interface for policy creation

## Files Modified in Refactoring

### Created

- `policy_reader/services/extraction_service.py`

### Modified

- `policy_reader/doctype/policy_document/policy_document.py` (simplified)
- `policy_reader/doctype/policy_document/policy_document.json` (removed policy fields)
- `policy_reader/doctype/policy_document/policy_document.js` (cleaned up)
- `policy_reader/doctype/policy_reader_settings/policy_reader_settings.py` (added field aliases)
- `policy_reader/utils.py` (updated imports)
- `policy_reader/modules.txt` (removed policy_reader_templates)
- `WARP.md` (updated documentation)

### Deleted

- `policy_reader/services/field_mapping_service.py`
- `policy_reader/services/template_service.py`
- `policy_reader/policy_reader_templates/` (entire module)

This architecture provides a clean foundation for building the Policy Creation Service while maintaining the robust document processing and field extraction capabilities.
