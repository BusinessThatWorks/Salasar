## Policy Reader - System Understanding (Frappe App)

### Purpose

- Read insurance PDF files, extract OCR text (RunPod or local), use Claude Sonnet to parse structured fields, then create Frappe DocTypes (`Motor Policy`, `Health Policy`) using dynamic field mappings configured/cached in `Policy Reader Settings`.

### High-level Flow

1. User uploads a file and selects `policy_type` on `Policy Document`.
2. User triggers processing → background job enqueued.
3. OCR text extraction:
   - Prefer RunPod OCR if configured and healthy; else fallback to local `document_reader`.
4. AI field extraction:
   - Build prompt from `Policy Reader Settings` (cached dynamic prompt per policy type or fallback); call Anthropic Claude; parse JSON from response.
5. Store results on `Policy Document`:
   - `status`, `extracted_fields` (JSON), `raw_ocr_text`, `processing_time`, `ocr_confidence`, flags, etc.
6. Optional: Create policy record (`Motor Policy` / `Health Policy`) mapped from extracted fields using cached field mapping from settings.

### Core Components

- `policy_reader/hooks.py`

  - `doc_events["DocType"].on_update`: `refresh_field_mappings_if_policy_doctype` auto-refreshes field-mapping cache when `Motor Policy` or `Health Policy` DocTypes change.
  - `patches`: runs `v1_0.migrate_motor_policy_schema` during installs/updates.
  - `scheduler_events (cron)`: every 3 minutes monitor stuck `Policy Document`; every 10 minutes check RunPod health.

- `Policy Document` (`policy_reader/doctype/policy_document/policy_document.py`)

  - Orchestrates processing.
  - `process_policy()` enqueues `process_policy_background` job.
  - `process_policy_internal()` executes:
    - Choose processing method (`RunPod` vs `local`).
    - Extract text.
    - Call Claude through `ExtractionService` to get structured fields.
    - Persist status, extracted fields, raw OCR text, processing time, confidence metrics, processing method; publish realtime events.
  - Utilities: file path resolution via Frappe `File`, reset stuck status, timeout detection, AI re-extract using stored OCR text, create policy entry, get creation status, check API key status (module-level).

- `ProcessingService` (`services/processing_service.py`)

  - Picks processing method based on `Policy Reader Settings` RunPod config and health/latency (<5s threshold).
  - `extract_text_with_runpod()` → delegates OCR-only to `RunPodService`.
  - `extract_text_with_local()` → uses `document_reader.extract_text_with_confidence` for OCR + confidence.
  - Validates uploaded file accessibility.

- `RunPodService` (`services/runpod_service.py`)

  - Computes base/health/extract/OCR URLs from settings.
  - `check_health()` and `update_health_status()` helpers.
  - `extract_document_text()` performs OCR-only POST; returns normalized `{ success, text, confidence_data, runpod_endpoint }`.

- `ExtractionService` (`services/extraction_service.py`)

  - Gets extraction prompt from settings: cached → dynamic → fallback.
  - Calls Anthropic Messages API (`make_post_request`) with model from settings (default `claude-sonnet-4-20250514`).
  - Parses response safely to JSON via `_extract_json_from_text` (handles raw JSON, code fences, trimming, general object regex).
  - Validates/canonicalizes extracted fields.
  - Exposes `get_field_mapping_for_policy_type()` for backward compatibility.

- `PolicyCreationService` (`services/policy_creation_service.py`)

  - Parses extracted JSON (flat or nested structures; robust parsing with `ast.literal_eval`/`frappe.parse_json`).
  - Dynamically maps extracted fields → target DocType fields using mapping cache from settings.
  - Converts values based on Frappe field metadata (Date/Float/Int/Check/Select, etc.).
  - Creates and inserts new `Motor Policy` or `Health Policy`, links back to `Policy Document`.

- `Policy Reader Settings` (`doctype/policy_reader_settings/policy_reader_settings.py`)

  - Validations: Anthropic key format (`sk-ant-`), RunPod config format/ranges, timeout range.
  - Test actions: API key format test; RunPod health check with persisted health fields.
  - RunPod helpers: build URLs, availability checks, scheduled health status update endpoint (`get_runpod_health_info`).
  - Field-mapping lifecycle:
    - `refresh_field_mappings()`: builds mapping from DocType metadata; stores JSON in `motor_policy_fields`/`health_policy_fields`.
    - `build_field_mapping_from_doctype(doctype)`: builds `{ label/aliases → fieldname }` skipping layout/system fields; adds alias sets for natural variants (e.g., `Policy Number`, `PolicyNumber`, etc.).
    - `get_cached_field_mapping(policy_type)` returns parsed JSON mapping.
  - Prompt lifecycle:
    - `refresh_extraction_prompts()`: builds dynamic prompts and caches them.
    - `get_cached_extraction_prompt(policy_type, text)` replaces a sample placeholder in cached prompt with current text; else builds dynamic.
    - Dynamic builders `_build_motor_extraction_prompt()` / `_build_health_extraction_prompt()` generate categorized instructions based on DocType fields with extraction rules and examples; fallback builders provided.

- `Motor Policy` (`policies/doctype/motor_policy/motor_policy.py`)

  - Validation: date sanity; required-field checks intentionally relaxed to permit AI-first creation.
  - Action: `populate_fields_from_policy_document(policy_document_name)` to fill fields in an existing policy by reusing `PolicyCreationService` and refreshed field mappings, including chassis/engine alias handling and mapping debug logs.

- `Health Policy` (`policies/doctype/health_policy/health_policy.py`)

  - Minimal controller; relies on mapping and creation service.

- Background Tasks (`policy_reader/tasks.py`)
  - `monitor_stuck_policy_documents()` finds processing docs older than 5 minutes → retries; 30+ minutes → mark failed; notifies user via realtime events.
  - `check_runpod_health()` every 10 minutes updates settings health fields using the same internal health method.
  - `cleanup_old_processing_jobs()` utility to mark abandoned jobs failed (>1 hour).

### Field Mapping Strategy

- Mapping keys are natural labels and alias variants; values are target DocType fieldnames.
- Built from DocType metadata to make the mapping resilient to label variations in OCR/AI output.
- Conversion respects Frappe field types and common canonicalization (dates to `DD/MM/YYYY`, numeric-only extraction for currency, select normalization).

### Prompt Strategy for Claude

- Cached prompts are generated from DocType definitions and categorized sections with explicit extraction rules and examples.
- Always require flat JSON output (no nested structures) to simplify mapping.
- Fallback prompt exists for each policy type and generic types.

### Error Handling & Observability

- Extensive `frappe.logger()` info/warning/error logs across services.
- `frappe.log_error()` with contextual titles for critical failures (Claude API, RunPod, parsing, timeouts).
- Realtime events published on completion/failure and on retries.
- Graceful fallbacks: RunPod → local, cached prompt → dynamic → fallback, health checks with persisted status.

### Configuration

- Anthropic API key precedence: Settings → `site_config.json` (`frappe.conf`) → `ANTHROPIC_API_KEY` env var.
- Claude model customizable via settings (`claude_model`), default `claude-sonnet-4-20250514`.
- RunPod: `runpod_pod_id`, `runpod_port`, `runpod_api_secret`, optional `runpod_endpoint`. Health status and response time stored and used for routing decisions.
- Background queues: `queue_type` and `timeout` from settings used during enqueue.

### Notable UX Behaviors

- `Policy Document.title` auto-derived from uploaded filename; cleaned and title-cased.
- Status lifecycle: Draft → Processing → Completed/Failed; reset available when stuck.
- Confidence data stored from OCR provider (avg confidence in percent; enhancement flags), with manual review recommendation when < 70%.

### Extensibility Notes

- New policy types can be supported by:
  - Adding a new policy DocType with fields.
  - Extending `Policy Reader Settings` prompt builders and field alias dictionary for that type.
  - Ensuring hooks refresh field mappings when the new DocType updates.
- External OCR providers can be added by implementing a new service analogous to `RunPodService` and extending `ProcessingService` selection logic.

### Known Trade-offs / Considerations

- JSON extraction from LLM responses uses tolerant regex/code-fence parsing; malformed outputs may still slip through as empty dicts.
- Value conversion relies on Frappe field metadata; select normalization attempts exact/case-insensitive/partial matching—may need insurer-specific canonicalization tables.
- `document_reader` is an external dependency for local OCR; ensure it’s available in the environment.

### Key Entry Points

- Process a document: `Policy Document.process_policy()`.
- Background execution: `process_policy_background(doc_name)`.
- Create mapped policy: `Policy Document.create_policy_entry()` or via `Motor Policy.populate_fields_from_policy_document()`.
- Refresh mappings/prompts: `Policy Reader Settings.refresh_field_mappings()` / `refresh_extraction_prompts()`.
